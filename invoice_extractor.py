import base64
import io
import logging
import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

import pdfplumber
from azure.identity import (
    ChainedTokenCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    get_bearer_token_provider,
)
from openai import AsyncAzureOpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from PIL import Image
from pydantic import BaseModel, Field

from config import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    AZURE_TENANT_ID,
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

# Initialize Azure OpenAI client with credential targeting the correct tenant.
# AZURE_TENANT_ID must be the Tenant ID (Directory ID), not the Subscription ID.
# Uses a chain: AzureCliCredential first (for devs), then InteractiveBrowserCredential
# as a fallback (opens a browser login window for non-technical users).
if AZURE_TENANT_ID:
    credential = ChainedTokenCredential(
        # AzureCliCredential(tenant_id=AZURE_TENANT_ID),
        InteractiveBrowserCredential(tenant_id=AZURE_TENANT_ID),
    )
else:
    credential = DefaultAzureCredential()

token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)
client = AsyncAzureOpenAI(
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


async def extract_invoice_details(file_path: Optional[str] = None) -> dict:
    """
    Extract invoice details from a PDF or image file.

    Args:
        file_path: Path to the receipt file (PDF, PNG, JPG, etc.)

    Returns:
        Dictionary containing extracted invoice details
    """
    try:
        if file_path is None:
            raise FileNotFoundError("No file path provided")

        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file extension
        file_ext = Path(file_path).suffix.lower()

        image_data = []

        # Process based on file type
        if file_ext == ".pdf":
            # Convert PDF to images using pdfplumber
            images = pdf_to_images(file_path)
            if not images:
                raise Exception("No images extracted from PDF")

            # Use the first page for analysis
            for image in images:
                image_data.append(image_to_base64(image))

        elif file_ext in [".png", ".jpg", ".jpeg", ".gif"]:
            # Load image directly
            image = Image.open(file_path)
            image_data.append(image_to_base64(image))

        else:
            raise Exception(f"Unsupported file type: {file_ext}")

        # Prepare the message for Azure OpenAI
        messages = [
            ChatCompletionSystemMessageParam(
                role="system",
                content="""Extract invoice/receipt details from the provided image to
                        the provided output format. Be precise and only extract
                        information that is clearly visible in the receipt.""",
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

        # Call Azure OpenAI with structured output
        completion = await client.beta.chat.completions.parse(
            model=INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
            messages=messages,
            response_format=InvoiceDetails,
            temperature=0.1,  # Lower temperature for more consistent extraction
        )

        # Extract the parsed response
        invoice_details = completion.choices[0].message.parsed

        if invoice_details is None:
            raise Exception("Failed to parse invoice details from AI response")

        # Convert to dictionary format expected by the API
        return {
            "Amount": invoice_details.amount * (-1 if invoice_details.is_refund else 1),
            "Currency": invoice_details.currency,
            "Date": invoice_details.date,
            "Expense category": invoice_details.expense_category.value,
            "Merchant": invoice_details.merchant,
            "Additional information": invoice_details.expense_description,
        }

    except Exception as e:
        # Log error and return empty dictionary
        logger.error(f"Error extracting invoice details: {str(e)}", exc_info=True)
        return {}
