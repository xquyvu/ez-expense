import asyncio
import base64
import io
import json
import logging
import os
import re
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import List, Optional

import pdfplumber
import pillow_heif
from PIL import Image
from pydantic import BaseModel, Field

from config import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    AZURE_TENANT_ID,
    COPILOT_MAX_CONCURRENCY,
    COPILOT_MODEL,
    COPILOT_TIMEOUT,
    CURRENCY_SYMBOL_MAP,
    EXPENSE_CATEGORIES,
    EXTRACTION_PROVIDER,
    HOTEL_SUBCATEGORIES,
    INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
)
from resource_utils import load_env_file

logger = logging.getLogger(__name__)

# Load environment variables
load_env_file()

pillow_heif.register_heif_opener()

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


# ── Hotel itemization ───────────────────────────────────────────────────────
# A hotel invoice/folio is broken down into itemized charges grouped by subcategory
# (e.g. "Daily Room Rate", "Hotel Tax"). The valid subcategories are loaded from
# hotel_subcategories.txt; when that list is non-empty we constrain the model's
# "Subcategory" field to it, otherwise we accept free-form text.
if HOTEL_SUBCATEGORIES:
    ValidHotelSubcategories = Enum(
        "ValidHotelSubcategories",
        ((x, x) for x in HOTEL_SUBCATEGORIES),
    )
    _HotelSubcategoryType = ValidHotelSubcategories
else:
    ValidHotelSubcategories = None
    _HotelSubcategoryType = str


class HotelItemizationLine(BaseModel):
    subcategory: _HotelSubcategoryType = Field(
        alias="Subcategory", description="The kind of hotel charge"
    )
    start_date: str = Field(
        alias="Start date", description="Date the charge applies to, in M/D/YYYY format"
    )
    daily_rate: float = Field(
        alias="Daily rate", description="Per-unit (e.g. per-night) amount, no currency symbol"
    )
    quantity: float = Field(alias="Quantity", description="Number of units (e.g. nights)")


class HotelItemization(BaseModel):
    lines: List[HotelItemizationLine] = Field(
        alias="Lines", description="Itemized hotel charges grouped by subcategory"
    )


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


HEIC_EXTENSIONS = (".heic", ".heif")


def convert_heic_to_jpg(file_path: str, remove_original: bool = False) -> str:
    """
    Convert a HEIC/HEIF image to a JPG saved alongside it and return the JPG path.

    MyExpense does not accept HEIC/HEIF attachments and browsers cannot render them, so
    receipts are converted to JPG when they are uploaded. The JPG is written next to the
    source using the same stem; when ``remove_original`` is True the source HEIC/HEIF file
    is deleted after a successful conversion.

    Args:
        file_path: Path to the source HEIC/HEIF image.
        remove_original: Delete the source file after a successful conversion.

    Returns:
        Path to the JPG file.
    """
    source = Path(file_path)

    image = Image.open(source)
    if image.mode != "RGB":
        image = image.convert("RGB")

    output_path = source.with_suffix(".jpg")
    image.save(output_path, format="JPEG", quality=85)

    if remove_original and output_path != source:
        source.unlink(missing_ok=True)

    logger.info(f"Converted HEIC/HEIF '{source.name}' to JPG '{output_path.name}'")
    return str(output_path)


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


async def _extract_with_azure(
    image_data: Optional[List[str]] = None, text: Optional[str] = None
) -> dict:
    """Extract invoice details using Azure OpenAI (images, or text for HTML receipts)."""
    from openai.types.chat import (
        ChatCompletionContentPartImageParam,
        ChatCompletionContentPartTextParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )

    client = _get_azure_client()

    if text is not None:
        user_content = [
            ChatCompletionContentPartTextParam(type="text", text=f"Receipt content:\n{text}")
        ]
    else:
        user_content = [
            ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={"url": f"data:image/jpeg;base64,{image_base64}"},
            )
            for image_base64 in (image_data or [])
        ]

    messages = [
        ChatCompletionSystemMessageParam(
            role="system",
            content=dedent("""\
                Extract invoice/receipt details from the provided receipt to
                the provided output format. Be precise and only extract
                information that is clearly present in the receipt."""),
        ),
        ChatCompletionUserMessageParam(role="user", content=user_content),
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


# ── GitHub Copilot SDK path ─────────────────────────────────────────────────
# Zero-setup vision extraction using the user's existing GitHub Copilot login.
# Copilot has no enforced structured-output mode, so we ask for JSON and parse it
# with the same _parse_local_llm_response() used by the local LLM path.

_copilot_client = None
_copilot_client_lock = asyncio.Lock()
_copilot_semaphore = asyncio.Semaphore(COPILOT_MAX_CONCURRENCY)
_resolved_copilot_model: Optional[str] = None
_copilot_auth_cache: Optional[dict] = None

# Small/specialized variants to skip when auto-selecting a default vision model.
_COPILOT_MODEL_DEPRIORITIZE = ("mini", "flash", "lite", "nano", "codex", "internal")


def _model_supports_vision(model) -> bool:
    """True if a Copilot ModelInfo advertises vision support (object or dict shape)."""
    caps = getattr(model, "capabilities", None)
    supports = getattr(caps, "supports", None)
    vision = getattr(supports, "vision", None)
    if vision is None and isinstance(caps, dict):
        vision = caps.get("supports", {}).get("vision")
    return bool(vision)


def _select_default_copilot_model(models) -> str:
    """Pick a vision-capable model id from the account's models, without hardcoding one."""
    vision_ids = [
        getattr(m, "id", None)
        for m in models
        if _model_supports_vision(m) and getattr(m, "id", None) not in (None, "auto")
    ]
    if not vision_ids:
        raise Exception("No vision-capable Copilot model is available for this account")
    # Prefer a full-size general model over mini/flash/codex variants when present.
    preferred = [
        m for m in vision_ids if not any(t in m.lower() for t in _COPILOT_MODEL_DEPRIORITIZE)
    ]
    return (preferred or vision_ids)[0]


async def _resolve_copilot_model(client) -> str:
    """Resolve model: explicit COPILOT_MODEL if set, else auto-select a vision-capable one."""
    global _resolved_copilot_model
    if COPILOT_MODEL:
        return COPILOT_MODEL
    if _resolved_copilot_model is None:
        _resolved_copilot_model = _select_default_copilot_model(await client.list_models())
        logger.info(f"Auto-selected Copilot vision model: {_resolved_copilot_model}")
    return _resolved_copilot_model


def _build_vision_extraction_prompt() -> str:
    """Vision prompt mirroring the Azure path: same instruction + serialized InvoiceDetails schema.

    Copilot can't enforce a response schema, so we serialize the same pydantic model the
    Azure path uses and ask the model to conform to it.
    """
    schema = json.dumps(InvoiceDetails.model_json_schema(by_alias=True), ensure_ascii=False)
    return (
        "Extract invoice/receipt details from the provided image to the provided output "
        "format. Be precise and only extract information that is clearly visible in the receipt.\n\n"
        'For "Amount", use the TOTAL - the final amount actually paid (including tax and tip), '
        "since that is the figure matched against the expense line, not the subtotal.\n"
        '"Merchant" is the SELLER company, not the buyer/customer.\n\n'
        "Return ONLY a single raw JSON object (no markdown fences, no commentary) that conforms "
        "to this JSON Schema:\n" + schema + "\n\n"
        'Use the exact property names from the schema (e.g. "Expense category", "Additional '
        'information"), and choose "Expense category" from the allowed enum values. Output JSON only.'
    )


async def _get_copilot_client():
    """Lazily start a single shared Copilot client (spawns the bundled CLI once)."""
    global _copilot_client
    async with _copilot_client_lock:
        if _copilot_client is None:
            from copilot import CopilotClient

            client = CopilotClient()
            await client.start()

            status = await client.get_auth_status()
            authed = getattr(status, "isAuthenticated", None)
            if authed is None and isinstance(status, dict):
                authed = status.get("isAuthenticated")
            if not authed:
                logger.warning("Copilot is not authenticated; run `copilot` to sign in")

            _copilot_client = client
    return _copilot_client


async def _get_copilot_auth_status(force_refresh: bool = False) -> dict:
    """Cached Copilot auth status: {'authenticated': bool, 'login': str|None}.

    Spawns the CLI once (lazily) to query auth, then caches the result.
    """
    global _copilot_auth_cache
    if _copilot_auth_cache is not None and not force_refresh:
        return _copilot_auth_cache

    result = {"authenticated": False, "login": None}
    try:
        client = await _get_copilot_client()
        status = await client.get_auth_status()
        authed = getattr(status, "isAuthenticated", None)
        login = getattr(status, "login", None)
        if isinstance(status, dict):
            authed = status.get("isAuthenticated", authed)
            login = status.get("login", login)
        result = {"authenticated": bool(authed), "login": login}
    except Exception as e:
        logger.warning(f"Copilot auth check failed: {e}")

    _copilot_auth_cache = result
    return result


async def _reset_copilot_client() -> None:
    """Drop the cached client + auth so the next call re-spawns with fresh credentials."""
    global _copilot_client, _copilot_auth_cache
    async with _copilot_client_lock:
        if _copilot_client is not None:
            try:
                await _copilot_client.stop()
            except Exception:
                pass
            _copilot_client = None
    _copilot_auth_cache = None


async def _extract_with_copilot(
    image_data: Optional[List[str]] = None, text: Optional[str] = None
) -> dict:
    """Extract invoice details via the GitHub Copilot SDK (vision, or text for HTML receipts)."""
    from copilot.session import PermissionHandler

    client = await _get_copilot_client()
    model = await _resolve_copilot_model(client)

    if text is not None:
        prompt = _build_text_extraction_prompt(text)
        attachments = None
    else:
        prompt = _build_vision_extraction_prompt()
        attachments = [
            {
                "type": "blob",
                "data": image_base64,
                "mimeType": "image/jpeg",
                "displayName": f"receipt_p{i}.jpg",
            }
            for i, image_base64 in enumerate(image_data or [])
        ]

    # Bound how many receipts hit Copilot at once (callers may fire many in parallel).
    async with _copilot_semaphore:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model,
            available_tools=[],  # pure inference, no agentic tools
        )
        response = await session.send_and_wait(
            prompt,
            attachments=attachments,
            timeout=COPILOT_TIMEOUT,
        )

    content = getattr(getattr(response, "data", None), "content", None)
    if not content:
        raise Exception("Copilot returned no content for invoice extraction")

    data = _parse_local_llm_response(content)

    amount = float(data.get("Amount", 0) or 0)
    if bool(data.get("is_refund", False)):
        amount = -abs(amount)

    return {
        "Amount": amount,
        "Currency": data.get("Currency", "USD"),
        "Date": data.get("Date", ""),
        "Expense category": data.get("Expense category", EXPENSE_CATEGORIES[0]),
        "Merchant": data.get("Merchant", ""),
        "Additional information": data.get("Additional information", ""),
    }


async def _extract_with_local(file_path: str) -> dict:
    """Extract invoice details using local OCR + LLM pipeline."""
    import local_model_manager

    file_ext = Path(file_path).suffix.lower()

    if file_ext in (".html", ".htm"):
        combined_text = _load_html_text(file_path)
    else:
        # Get images from file
        images: List[Image.Image] = []
        if file_ext == ".pdf":
            images = pdf_to_images(file_path)
        elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".heic", ".heif"]:
            images = [Image.open(file_path)]
        else:
            raise Exception(f"Unsupported file type: {file_ext}")

        if not images:
            raise Exception("No images to process")

        # OCR all pages and combine text
        ocr_texts = []
        for image in images:
            ocr = _ocr_image(image)
            if ocr:
                ocr_texts.append(ocr)

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


def _build_text_extraction_prompt(content: str) -> str:
    """Schema-based extraction prompt for text content (e.g. an HTML receipt)."""
    schema = json.dumps(InvoiceDetails.model_json_schema(by_alias=True), ensure_ascii=False)
    return (
        "Extract invoice/receipt details from the receipt content below to the provided "
        "output format. Be precise and only extract information clearly present.\n\n"
        'For "Amount", use the TOTAL - the final amount actually paid.\n'
        '"Merchant" is the SELLER company, not the buyer/customer.\n\n'
        "Return ONLY a single raw JSON object (no markdown fences) conforming to this JSON "
        "Schema:\n" + schema + "\n\nReceipt content:\n" + content + "\n\nOutput JSON only."
    )


def _load_html_text(file_path: str) -> str:
    """Extract visible text from an HTML receipt (scripts/styles stripped, length-capped)."""
    from bs4 import BeautifulSoup

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    if not text.strip():
        raise Exception("No text extracted from HTML")
    return text[:30000]


def _load_image_data(file_path: str) -> List[str]:
    """Convert a receipt file (PDF or image, incl. HEIC) to a list of base64 JPEG strings."""
    file_ext = Path(file_path).suffix.lower()
    image_data: List[str] = []

    if file_ext == ".pdf":
        images = pdf_to_images(file_path)
        if not images:
            raise Exception("No images extracted from PDF")
        for image in images:
            image_data.append(image_to_base64(image))
    elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".heic", ".heif"]:
        image_data.append(image_to_base64(Image.open(file_path)))
    else:
        raise Exception(f"Unsupported file type: {file_ext}")

    return image_data


def _resolve_extraction_provider(override: Optional[str] = None) -> str:
    """Resolve the extraction provider; a per-request override beats the EXTRACTION_PROVIDER env."""
    provider = (override or EXTRACTION_PROVIDER or "auto").lower()
    if provider in ("azure", "copilot", "local"):
        return provider
    if provider != "auto":
        logger.warning(f"Unknown extraction provider '{provider}', using auto")
    return "azure" if _is_azure_configured() else "local"


def _is_copilot_available() -> bool:
    """True if the Copilot SDK is importable (auth is verified lazily at extraction time)."""
    import importlib.util

    return importlib.util.find_spec("copilot") is not None


def _copilot_cli_path() -> Optional[str]:
    """Resolve the copilot CLI binary the same way the SDK does.

    Order: COPILOT_CLI_PATH env -> the SDK's bundled binary (copilot/bin/copilot) ->
    a `copilot` on PATH. Preferring the bundled binary means login works without a
    separately-installed CLI (e.g. in a packaged build) and shares the SDK's credential store.
    """
    import shutil

    candidates = [os.getenv("COPILOT_CLI_PATH")]
    try:
        from copilot.client import _get_bundled_cli_path

        candidates.append(_get_bundled_cli_path())
    except Exception:
        pass
    candidates.append(shutil.which("copilot"))

    for path in candidates:
        if path and os.path.exists(path):
            # Frozen builds may drop the exec bit when unpacking the binary.
            if not os.access(path, os.X_OK):
                try:
                    os.chmod(path, 0o755)
                except OSError:
                    pass
            return path
    return None


async def extract_invoice_details(
    file_path: Optional[str] = None, provider: Optional[str] = None
) -> dict:
    """
    Extract invoice details from a receipt file (PDF, PNG, JPG, GIF, HEIC, or HTML).

    HTML is read as text (visible text via BeautifulSoup); everything else is sent to
    the model as image(s). The backend is chosen by `provider` or EXTRACTION_PROVIDER:
      - "auto" (default): Azure OpenAI if configured, else local OCR + LLM
      - "azure":   Azure OpenAI vision
      - "copilot": GitHub Copilot SDK vision (zero setup, uses the Copilot login)
      - "local":   local OCR + llama

    Returns:
        Dictionary containing extracted invoice details, or {} on failure.
    """
    try:
        if file_path is None:
            raise FileNotFoundError("No file path provided")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        resolved = _resolve_extraction_provider(provider)
        logger.info(f"Using '{resolved}' provider for invoice extraction")

        is_html = Path(file_path).suffix.lower() in (".html", ".htm")

        if resolved == "copilot":
            if is_html:
                return await _extract_with_copilot(text=_load_html_text(file_path))
            return await _extract_with_copilot(image_data=_load_image_data(file_path))
        elif resolved == "azure":
            if is_html:
                return await _extract_with_azure(text=_load_html_text(file_path))
            return await _extract_with_azure(image_data=_load_image_data(file_path))
        else:  # local (handles HTML + images internally)
            return await _extract_with_local(file_path)

    except Exception as e:
        logger.error(f"Error extracting invoice details: {str(e)}", exc_info=True)
        return {}


# ── Hotel itemization extraction ────────────────────────────────────────────


def _normalize_date_mdy(value: str) -> str:
    """Normalize a date string to M/D/YYYY (no leading zeros), matching the dialog field.

    Returns the original string unchanged if it can't be parsed.
    """
    from datetime import datetime

    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return f"{dt.month}/{dt.day}/{dt.year}"
        except ValueError:
            continue
    return value


def _coerce_subcategory(value: str) -> str:
    """Snap a model-produced subcategory to the closest valid configured value.

    No-op when no subcategory list is configured (free-form mode).
    """
    value = (value or "").strip()
    if not HOTEL_SUBCATEGORIES or not value:
        return value
    if value in HOTEL_SUBCATEGORIES:
        return value
    lowered = value.lower()
    for valid in HOTEL_SUBCATEGORIES:
        if valid.lower() == lowered:
            return valid
    for valid in HOTEL_SUBCATEGORIES:
        if lowered in valid.lower() or valid.lower() in lowered:
            return valid
    return value


def _to_number(value) -> float:
    """Best-effort parse of a numeric field that may carry currency symbols/commas."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


# Tolerance (in the expense currency's minor unit, e.g. cents) for treating the itemized total
# as equal to the expense amount. Allows for per-line rounding without masking real errors.
ITEMIZATION_BALANCE_TOLERANCE = 0.01


def itemized_total(lines: List[dict]) -> float:
    """Sum of (Daily rate × Quantity) across itemization lines, rounded to 2 decimals."""
    total = 0.0
    for line in lines or []:
        rate = _to_number(line.get("Daily rate", line.get("daily_rate", 0)))
        qty = _to_number(line.get("Quantity", line.get("quantity", 0)))
        total += round(rate * qty, 2)
    return round(total, 2)


def is_balanced(
    lines: List[dict], amount, tolerance: float = ITEMIZATION_BALANCE_TOLERANCE
) -> bool:
    """True if the itemized lines reconcile to ``amount`` (within ``tolerance``).

    Returns False when ``amount`` is missing/unparseable so callers surface the mismatch.
    """
    if amount is None or (isinstance(amount, str) and not amount.strip()):
        return False
    target = _to_number(amount)
    return abs(itemized_total(lines) - target) <= tolerance


def _normalize_itemization_line(item: dict) -> dict:
    """Map a single extracted line to the canonical itemization-form columns."""
    sub = item.get("Subcategory", item.get("subcategory", ""))
    if hasattr(sub, "value"):  # Enum member
        sub = sub.value
    return {
        "Subcategory": _coerce_subcategory(str(sub)),
        "Start date": _normalize_date_mdy(str(item.get("Start date", item.get("start_date", "")))),
        "Daily rate": _to_number(item.get("Daily rate", item.get("daily_rate", 0))),
        "Quantity": _to_number(item.get("Quantity", item.get("quantity", 0))),
    }


def _parse_itemization_response(raw: str) -> List[dict]:
    """Parse a model JSON response into a list of normalized itemization lines.

    Tolerant of markdown fences and surrounding prose: if the whole string isn't valid JSON,
    fall back to the first balanced ``{...}`` (or ``[...]``) block found in the text.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
        text = "\n".join(lines)

    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = _extract_json_block(text)

    if isinstance(data, dict):
        if "Lines" in data or "lines" in data:
            raw_lines = data.get("Lines") or data.get("lines") or []
        elif any(k in data for k in ("Subcategory", "subcategory", "Daily rate", "daily_rate")):
            # A bare single line object (no wrapper) — treat as a one-line list.
            raw_lines = [data]
        else:
            raw_lines = []
    elif isinstance(data, list):
        raw_lines = data
    else:
        raw_lines = []

    return [_normalize_itemization_line(item) for item in raw_lines if isinstance(item, dict)]


def _extract_json_block(text: str):
    """Find and parse the first balanced JSON object/array embedded in ``text``.

    Models sometimes wrap JSON in explanatory prose; this scans for the outermost ``{}`` or
    ``[]`` (respecting strings/escapes) and parses it. Returns None if nothing parses.
    """
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


def _build_hotel_itemization_prompt(expected_total: Optional[float] = None) -> str:
    """Vision prompt: break a hotel invoice into itemized charges grouped by subcategory."""
    schema = json.dumps(HotelItemization.model_json_schema(by_alias=True), ensure_ascii=False)
    if HOTEL_SUBCATEGORIES:
        allowed = (
            'Choose each "Subcategory" from exactly these allowed values: '
            + ", ".join(f'"{c}"' for c in HOTEL_SUBCATEGORIES)
            + ".\n"
        )
    else:
        allowed = ""
    if expected_total is not None:
        reconcile = (
            f"\nIMPORTANT: the expense total is {expected_total:.2f}. The sum of "
            '("Daily rate" × "Quantity") across ALL lines MUST equal exactly this total. '
            "Double-check your arithmetic; if there is any remainder (taxes, fees, resort "
            "charges, rounding), add or adjust a line (e.g. Hotel Tax or Incidentals) so the "
            "lines reconcile to the total exactly.\n"
        )
    else:
        reconcile = ""
    return (
        "You are itemizing a HOTEL invoice/folio for an expense report. Read the invoice "
        "image(s) and break the total down into itemized charges.\n\n"
        "CRITICAL — ONE ROW PER DATE:\n"
        '- Emit ONE line for each (subcategory, date) pair. Set "Quantity" to 1 on every '
        "line, and put the per-day amount in \"Daily rate\".\n"
        "- For a multi-night stay, do NOT collapse nightly room charges into a single line: "
        "produce one Daily Room Rate line per night, each with that night's date and rate.\n"
        "- Per-night taxes/fees (e.g. Hotel Tax, resort fee, occupancy tax) likewise get one "
        "line per night, with that night's date and the tax amount charged that night.\n"
        "- One-off charges (e.g. parking on a specific day, a single restaurant charge, an "
        "incidental) get a single line on the date they were incurred.\n"
        "- If a charge legitimately spans multiple days at the same rate but the invoice only "
        "shows it once with no per-day breakdown, still split it into one line per applicable "
        "date (rate = total ÷ number of days).\n\n"
        'Use the M/D/YYYY format for "Start date" (the date the charge applies to). Numbers '
        "must not include currency symbols. Only include charges actually present on the "
        "invoice.\n" + allowed + reconcile + "\nReturn ONLY a single raw JSON object "
        "(no markdown fences, no commentary) that conforms to this JSON Schema:\n" + schema
        + "\n\nUse the exact property names from the schema. Output JSON only."
    )


def _build_hotel_itemization_text_prompt(
    content: str, expected_total: Optional[float] = None
) -> str:
    """Text variant of the hotel itemization prompt (e.g. for HTML folios)."""
    return _build_hotel_itemization_prompt(expected_total) + "\n\nInvoice content:\n" + content


async def _extract_itemization_with_azure(
    image_data: Optional[List[str]] = None,
    text: Optional[str] = None,
    expected_total: Optional[float] = None,
) -> List[dict]:
    """Hotel itemization via Azure OpenAI structured output."""
    from openai.types.chat import (
        ChatCompletionContentPartImageParam,
        ChatCompletionContentPartTextParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )

    client = _get_azure_client()

    if text is not None:
        user_content = [
            ChatCompletionContentPartTextParam(type="text", text=f"Invoice content:\n{text}")
        ]
    else:
        user_content = [
            ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={"url": f"data:image/jpeg;base64,{image_base64}"},
            )
            for image_base64 in (image_data or [])
        ]

    messages = [
        ChatCompletionSystemMessageParam(
            role="system", content=_build_hotel_itemization_prompt(expected_total)
        ),
        ChatCompletionUserMessageParam(role="user", content=user_content),
    ]

    completion = await client.beta.chat.completions.parse(
        model=INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
        messages=messages,
        response_format=HotelItemization,
        temperature=0.1,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise Exception("Failed to parse hotel itemization from AI response")

    return [
        _normalize_itemization_line(line.model_dump(by_alias=True)) for line in parsed.lines
    ]


async def _extract_itemization_with_copilot(
    image_data: Optional[List[str]] = None,
    text: Optional[str] = None,
    expected_total: Optional[float] = None,
) -> List[dict]:
    """Hotel itemization via the GitHub Copilot SDK (vision, or text for HTML folios)."""
    from copilot.session import PermissionHandler

    client = await _get_copilot_client()
    model = await _resolve_copilot_model(client)

    if text is not None:
        prompt = _build_hotel_itemization_text_prompt(text, expected_total)
        attachments = None
    else:
        prompt = _build_hotel_itemization_prompt(expected_total)
        attachments = [
            {
                "type": "blob",
                "data": image_base64,
                "mimeType": "image/jpeg",
                "displayName": f"invoice_p{i}.jpg",
            }
            for i, image_base64 in enumerate(image_data or [])
        ]

    async with _copilot_semaphore:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model,
            available_tools=[],
        )
        response = await session.send_and_wait(
            prompt,
            attachments=attachments,
            timeout=COPILOT_TIMEOUT,
        )

    content = getattr(getattr(response, "data", None), "content", None)
    if not content:
        raise Exception("Copilot returned no content for hotel itemization")

    return _parse_itemization_response(content)


async def _extract_itemization_with_local(
    file_path: str, expected_total: Optional[float] = None
) -> List[dict]:
    """Hotel itemization via the local OCR + LLM pipeline (best effort)."""
    import local_model_manager

    file_ext = Path(file_path).suffix.lower()

    if file_ext in (".html", ".htm"):
        combined_text = _load_html_text(file_path)
    else:
        images: List[Image.Image] = []
        if file_ext == ".pdf":
            images = pdf_to_images(file_path)
        elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".heic", ".heif"]:
            images = [Image.open(file_path)]
        else:
            raise Exception(f"Unsupported file type: {file_ext}")

        ocr_texts = [ocr for ocr in (_ocr_image(image) for image in images) if ocr]
        combined_text = "\n\n".join(ocr_texts)
        if not combined_text.strip():
            raise Exception("OCR extracted no text from the invoice")

    raw_response = local_model_manager.generate(
        _build_hotel_itemization_text_prompt(combined_text, expected_total)
    )
    logger.info(f"Local LLM itemization response: {raw_response[:200]}...")
    return _parse_itemization_response(raw_response)


async def extract_hotel_itemization(
    file_path: Optional[str] = None,
    provider: Optional[str] = None,
    expected_total: Optional[float] = None,
) -> List[dict]:
    """Extract itemized hotel charges from a hotel invoice (PDF, image, HEIC, or HTML).

    Mirrors :func:`extract_invoice_details` but returns a list of itemization lines, each a
    dict with keys: "Subcategory", "Start date" (M/D/YYYY), "Daily rate", "Quantity".

    When ``expected_total`` is provided it is passed to the model so the lines are reconciled
    to the expense amount (the sum of Daily rate × Quantity should equal the total).

    Returns an empty list on failure.
    """
    try:
        if file_path is None:
            raise FileNotFoundError("No file path provided")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        resolved = _resolve_extraction_provider(provider)
        logger.info(f"Using '{resolved}' provider for hotel itemization extraction")

        is_html = Path(file_path).suffix.lower() in (".html", ".htm")

        if resolved == "copilot":
            if is_html:
                return await _extract_itemization_with_copilot(
                    text=_load_html_text(file_path), expected_total=expected_total
                )
            return await _extract_itemization_with_copilot(
                image_data=_load_image_data(file_path), expected_total=expected_total
            )
        elif resolved == "azure":
            if is_html:
                return await _extract_itemization_with_azure(
                    text=_load_html_text(file_path), expected_total=expected_total
                )
            return await _extract_itemization_with_azure(
                image_data=_load_image_data(file_path), expected_total=expected_total
            )
        else:  # local
            return await _extract_itemization_with_local(file_path, expected_total=expected_total)

    except Exception as e:
        logger.error(f"Error extracting hotel itemization: {str(e)}", exc_info=True)
        return []
