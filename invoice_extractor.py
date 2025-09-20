import base64
import io
import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

import pdfplumber
from dotenv import load_dotenv
from openai import AzureOpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from PIL import Image
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

with open("assets/category_list.txt") as f:
    CATEGORY_LIST = [line.strip() for line in f if line.strip()]


ValidExpenseCategories = Enum(
    "ValidExpenseCategories",
    ((x, x) for x in CATEGORY_LIST),
)


class InvoiceDetails(BaseModel):
    amount: float = Field(..., alias="Amount")
    currency: str = Field(..., alias="Currency")
    date: str = Field(..., alias="Date", description="Date in YYYY-MM-DD format")
    expense_category: ValidExpenseCategories = Field(..., alias="Expense category")


IMAGE_RESOLUTION = 300  # DPI for image extraction from PDF

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

model_name = os.environ["AZURE_OPENAI_DEPLOYMENT"]


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


def extract_invoice_details(file_path: Optional[str] = None) -> dict:
    """
    Extract invoice details from a PDF or image file.

    Args:
        file_path: Path to the receipt file (PDF, PNG, JPG, etc.)

    Returns:
        Dictionary containing extracted invoice details
    """
    try:
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
        completion = client.beta.chat.completions.parse(
            model=model_name,
            messages=messages,
            response_format=InvoiceDetails,
            temperature=0.1,  # Lower temperature for more consistent extraction
        )

        # Extract the parsed response
        invoice_details = completion.choices[0].message.parsed

        # Convert to dictionary format expected by the API
        return {
            "Amount": invoice_details.amount,
            "Currency": invoice_details.currency,
            "Date": invoice_details.date,
            "Expense category": invoice_details.expense_category.value,
        }

    except Exception as e:
        # Log error and return empty dictionary
        print(f"Error extracting invoice details: {str(e)}")
        return {}
