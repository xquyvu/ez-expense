import base64
import io
import json
import logging
import os
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import List, Optional

import pdfplumber
from PIL import Image
from pydantic import BaseModel, Field

from config import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    AZURE_TENANT_ID,
    CURRENCY_SYMBOL_MAP,
    EXPENSE_CATEGORIES,
    INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
)
from resource_utils import load_env_file

logger = logging.getLogger(__name__)

# Load environment variables
load_env_file()

ValidExpenseCategories = Enum(
    "ValidExpenseCategories",
    ((x, x) for x in EXPENSE_CATEGORIES),
)


class InvoiceDetails(BaseModel):
    amount: float = Field(alias="Amount", description="Invoice amount")
    currency: str = Field(alias="Currency", description="Currency code (e.g., USD, GBP)")
    date: str = Field(alias="Date", description="Date in YYYY-MM-DD format")
    expense_category: ValidExpenseCategories = Field(alias="Expense category")
    merchant: str = Field(alias="Merchant", description="Merchant name")
    expense_description: str = Field(
        alias="Additional information",
        description="What the receipt is for, in no more than a few words",
    )
    is_refund: bool = Field(alias="is_refund", description="Indicates if the invoice is a refund")


IMAGE_RESOLUTION = 300  # DPI for image extraction from PDF


def _is_azure_configured() -> bool:
    """Check if Azure OpenAI environment variables are properly configured."""
    return bool(AZURE_OPENAI_ENDPOINT and INVOICE_DETAILS_EXTRACTOR_MODEL_NAME)


def _get_azure_client():
    """Lazily initialize and return the Azure OpenAI client."""
    from azure.identity import (
        AzureCliCredential,
        ChainedTokenCredential,
        DefaultAzureCredential,
        InteractiveBrowserCredential,
        get_bearer_token_provider,
    )
    from openai import AsyncAzureOpenAI

    if AZURE_TENANT_ID:
        credential = ChainedTokenCredential(
            AzureCliCredential(tenant_id=AZURE_TENANT_ID),
            InteractiveBrowserCredential(tenant_id=AZURE_TENANT_ID),
        )
    else:
        credential = DefaultAzureCredential()

    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AsyncAzureOpenAI(
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
    )


def pdf_to_images(pdf_path: str) -> List[Image.Image]:
    """
    Convert PDF to a list of PIL Images using pdfplumber.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of PIL Image objects, one for each page
    """
    try:
        images = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Convert page to image using pdfplumber
                page_image = page.to_image(resolution=IMAGE_RESOLUTION)
                # Convert PIL Image from pdfplumber to standard PIL Image
                pil_image = page_image.original
                images.append(pil_image)

        if not images:
            raise Exception("No pages found in PDF")

        return images
    except Exception as e:
        raise Exception(f"Failed to convert PDF to images: {str(e)}")


def image_to_base64(image: Image.Image) -> str:
    """
    Convert PIL Image to base64 string.

    Args:
        image: PIL Image object

    Returns:
        Base64 encoded string of the image
    """
    # Convert to RGB if not already
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Save image to bytes buffer
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)

    # Encode to base64
    image_bytes = buffer.getvalue()
    base64_string = base64.b64encode(image_bytes).decode("utf-8")

    return base64_string


def _build_extraction_prompt(ocr_text: str) -> str:
    """Build a compact extraction prompt for a small LLM."""
    # Keep a short representative sample of categories to save tokens
    sample_categories = EXPENSE_CATEGORIES[:10]
    categories_hint = ", ".join(f'"{c}"' for c in sample_categories) + ", ..."

    return dedent(f"""\
        Read the receipt text below carefully. Extract ONLY what is written in the receipt.
        Important: "Merchant" is the SELLER company, not the buyer/customer name.

        Return a JSON object with these fields:
        - "Amount": number (the total amount on the receipt)
        - "Currency": string (currency code like "GBP", "USD", "EUR" - look for $, £, € symbols)
        - "Date": string (YYYY-MM-DD format)
        - "Expense category": string (pick the best from: {categories_hint})
        - "Merchant": string (the seller/company name on the receipt)
        - "Additional information": string (what was purchased, in a few words)
        - "is_refund": boolean (true only if this is explicitly a refund)

        Example: {{"Amount": 9.99, "Currency": "EUR", "Date": "2025-03-15", "Expense category": "Office Supplies", "Merchant": "Staples", "Additional information": "Printer paper", "is_refund": false}}

        Receipt text:
        {ocr_text}

        JSON:""")


def _ocr_image(image: Image.Image) -> str:
    """Run OCR on a PIL Image and return extracted text."""
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()

    # Convert to RGB if needed
    if image.mode != "RGB":
        image = image.convert("RGB")

    import numpy as np

    img_array = np.array(image)
    result, _ = ocr(img_array)

    if not result:
        return ""

    # result is list of [bbox, text, confidence]
    return "\n".join(line[1] for line in result)


def _parse_local_llm_response(raw: str) -> dict:
    """Parse the JSON response from the local LLM, handling common quirks."""
    import re

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)

    # Normalize currency: convert symbols to codes
    currency = str(data.get("Currency", "")).strip()
    if currency in CURRENCY_SYMBOL_MAP:
        data["Currency"] = CURRENCY_SYMBOL_MAP[currency]

    # Validate expense_category against known categories
    cat_key = "Expense category"
    if cat_key in data:
        if data[cat_key] not in EXPENSE_CATEGORIES:
            # Try to find a close match
            cat_lower = data[cat_key].lower()
            for valid_cat in EXPENSE_CATEGORIES:
                if valid_cat.lower() == cat_lower:
                    data[cat_key] = valid_cat
                    break
            else:
                # Try substring match (e.g., "Misc" matches "Admin Services - Misc.")
                for valid_cat in EXPENSE_CATEGORIES:
                    if cat_lower in valid_cat.lower() or valid_cat.lower() in cat_lower:
                        data[cat_key] = valid_cat
                        break
                else:
                    data[cat_key] = EXPENSE_CATEGORIES[0]

    # Clean up "Additional information" - reject values that are clearly wrong
    info = str(data.get("Additional information", "")).strip()
    # Reject if it looks like an amount (just numbers, currency symbols, dots)
    if re.match(r"^[\d.,£$€¥\s]+$", info):
        info = ""
    # Reject if it's just a date or fulfillment status (allow OCR typos)
    if re.match(r"^(fulf[il]{0,2}led?|shipped|delivered|completed)\b", info, re.IGNORECASE):
        info = ""
    # Strip parenthesized date ranges like "(01/23/26 - 01/23/27)"
    info = re.sub(r"\s*\(\d{2}/\d{2}/\d{2}\s*-\s*\d{2}/\d{2}/\d{2}\)", "", info).strip()
    # Truncate if too long (small model sometimes dumps entire text)
    if len(info) > 60:
        info = info[:60].rsplit(" ", 1)[0]
    data["Additional information"] = info

    return data


async def _extract_with_azure(image_data: List[str]) -> dict:
    """Extract invoice details using Azure OpenAI (existing path)."""
    from openai.types.chat import (
        ChatCompletionContentPartImageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )

    client = _get_azure_client()

    messages = [
        ChatCompletionSystemMessageParam(
            role="system",
            content=dedent("""\
                Extract invoice/receipt details from the provided image to
                the provided output format. Be precise and only extract
                information that is clearly visible in the receipt."""),
        ),
        ChatCompletionUserMessageParam(
            role="user",
            content=[
                *[
                    ChatCompletionContentPartImageParam(
                        type="image_url",
                        image_url={"url": f"data:image/jpeg;base64,{image_base64}"},
                    )
                    for image_base64 in image_data
                ]
            ],
        ),
    ]

    completion = await client.beta.chat.completions.parse(
        model=INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
        messages=messages,
        response_format=InvoiceDetails,
        temperature=0.1,
    )

    invoice_details = completion.choices[0].message.parsed

    if invoice_details is None:
        raise Exception("Failed to parse invoice details from AI response")

    return {
        "Amount": invoice_details.amount * (-1 if invoice_details.is_refund else 1),
        "Currency": invoice_details.currency,
        "Date": invoice_details.date,
        "Expense category": invoice_details.expense_category.value,
        "Merchant": invoice_details.merchant,
        "Additional information": invoice_details.expense_description,
    }


async def _extract_with_local(file_path: str) -> dict:
    """Extract invoice details using local OCR + LLM pipeline."""
    import local_model_manager

    file_ext = Path(file_path).suffix.lower()

    # Get images from file
    images: List[Image.Image] = []
    if file_ext == ".pdf":
        images = pdf_to_images(file_path)
    elif file_ext in [".png", ".jpg", ".jpeg", ".gif"]:
        images = [Image.open(file_path)]
    else:
        raise Exception(f"Unsupported file type: {file_ext}")

    if not images:
        raise Exception("No images to process")

    # OCR all pages and combine text
    ocr_texts = []
    for image in images:
        text = _ocr_image(image)
        if text:
            ocr_texts.append(text)

    combined_text = "\n\n".join(ocr_texts)
    if not combined_text.strip():
        raise Exception("OCR extracted no text from the receipt")

    logger.info(f"OCR extracted {len(combined_text)} characters from {len(images)} page(s)")

    # Build prompt and run local LLM
    prompt = _build_extraction_prompt(combined_text)
    raw_response = local_model_manager.generate(prompt)

    logger.info(f"Local LLM response: {raw_response[:200]}...")

    # Parse the response
    data = _parse_local_llm_response(raw_response)

    # Apply refund sign if present
    amount = float(data.get("Amount", 0))
    is_refund = bool(data.get("is_refund", False))
    if is_refund:
        amount = -abs(amount)

    return {
        "Amount": amount,
        "Currency": data.get("Currency", "USD"),
        "Date": data.get("Date", ""),
        "Expense category": data.get("Expense category", EXPENSE_CATEGORIES[0]),
        "Merchant": data.get("Merchant", ""),
        "Additional information": data.get("Additional information", ""),
    }


async def extract_invoice_details(file_path: Optional[str] = None) -> dict:
    """
    Extract invoice details from a PDF or image file.

    Uses Azure OpenAI if configured, otherwise falls back to local OCR + LLM.

    Args:
        file_path: Path to the receipt file (PDF, PNG, JPG, etc.)

    Returns:
        Dictionary containing extracted invoice details
    """
    try:
        if file_path is None:
            raise FileNotFoundError("No file path provided")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if _is_azure_configured():
            logger.info("Using Azure OpenAI for invoice extraction")
            file_ext = Path(file_path).suffix.lower()
            image_data = []

            if file_ext == ".pdf":
                images = pdf_to_images(file_path)
                if not images:
                    raise Exception("No images extracted from PDF")
                for image in images:
                    image_data.append(image_to_base64(image))
            elif file_ext in [".png", ".jpg", ".jpeg", ".gif"]:
                image = Image.open(file_path)
                image_data.append(image_to_base64(image))
            else:
                raise Exception(f"Unsupported file type: {file_ext}")

            return await _extract_with_azure(image_data)
        else:
            logger.info("Using local OCR + LLM for invoice extraction")
            return await _extract_with_local(file_path)

    except Exception as e:
        logger.error(f"Error extracting invoice details: {str(e)}", exc_info=True)
        return {}
