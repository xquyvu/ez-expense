"""
Hotel Invoice Extractor

This module handles AI-powered extraction of line items and details
from hotel invoices using Azure OpenAI and PDF processing.
"""

import base64
import io
import logging
from pathlib import Path
from typing import List, Optional

import pdfplumber
from openai import AsyncAzureOpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionSystemMessageParam,  
    ChatCompletionUserMessageParam,
)
from PIL import Image

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
)
from hotel_itemizer.config import HOTEL_EXTRACTION_PROMPT, HOTEL_CATEGORIZATION_PROMPT
from hotel_itemizer.models import HotelInvoiceDetails, HotelLineItem, HotelCategoryEnum

logger = logging.getLogger(__name__)


class HotelInvoiceExtractor:
    """Handles extraction of hotel invoice details using AI."""

    def __init__(self):
        """Initialize the extractor with Azure OpenAI client."""
        self.client = AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )

    async def extract_from_pdf(self, file_path: Path) -> Optional[HotelInvoiceDetails]:
        """
        Extract hotel invoice details from a PDF file.
        
        Args:
            file_path: Path to the PDF hotel invoice
            
        Returns:
            HotelInvoiceDetails if successful, None if extraction fails
        """
        try:
            logger.info(f"Starting extraction from PDF: {file_path}")
            
            # Extract text from PDF
            pdf_text = self._extract_pdf_text(file_path)
            if not pdf_text:
                logger.error("No text extracted from PDF")
                return None

            # Convert PDF to image for visual analysis if needed
            pdf_image = self._convert_pdf_to_image(file_path)
            
            # Use AI to extract structured data
            extraction_result = await self._extract_with_ai(pdf_text, pdf_image)
            
            if extraction_result:
                logger.info("Successfully extracted hotel invoice details")
                return extraction_result
            else:
                logger.error("AI extraction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting from PDF {file_path}: {e}")
            return None

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text content from PDF using pdfplumber."""
        try:
            text_content = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
            return text_content
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def _convert_pdf_to_image(self, file_path: Path) -> Optional[str]:
        """Convert first page of PDF to base64 image for visual AI analysis."""
        try:
            with pdfplumber.open(file_path) as pdf:
                if pdf.pages:
                    # Convert first page to image
                    page = pdf.pages[0]
                    img = page.to_image()
                    
                    # Convert PIL image to base64
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    img_base64 = base64.b64encode(buffer.getvalue()).decode()
                    return img_base64
                    
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            return None

    async def _extract_with_ai(self, pdf_text: str, pdf_image: Optional[str] = None) -> Optional[HotelInvoiceDetails]:
        """Use Azure OpenAI to extract structured hotel invoice data."""
        try:
            messages = [
                ChatCompletionSystemMessageParam(
                    role="system",
                    content=HOTEL_EXTRACTION_PROMPT
                )
            ]

            # Prepare user message content
            user_content = [
                {
                    "type": "text",
                    "text": f"Please extract hotel invoice details from this content:\n\n{pdf_text}"
                }
            ]

            # Add image if available for better extraction
            if pdf_image:
                user_content.append(
                    ChatCompletionContentPartImageParam(
                        type="image_url",
                        image_url={"url": f"data:image/png;base64,{pdf_image}"}
                    )
                )

            messages.append(
                ChatCompletionUserMessageParam(
                    role="user", 
                    content=user_content
                )
            )

            # Call Azure OpenAI
            response = await self.client.chat.completions.create(
                model=INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
                messages=messages,
                temperature=0.1,
            )

            # Parse the response
            ai_response = response.choices[0].message.content
            logger.info(f"AI extraction response received: {len(ai_response)} characters")
            
            # Parse AI response into structured data
            return self._parse_ai_response(ai_response)

        except Exception as e:
            logger.error(f"Error in AI extraction: {e}")
            return None

    def _parse_ai_response(self, ai_response: str) -> Optional[HotelInvoiceDetails]:
        """Parse AI response text into structured HotelInvoiceDetails."""
        try:
            # This is a simplified parser - in production you'd want more robust parsing
            # For now, we'll use a basic JSON-like parsing approach
            
            # TODO: Implement robust parsing of AI response
            # This should handle various response formats and extract:
            # - Hotel name and location
            # - Check-in/check-out dates  
            # - Line items with descriptions and amounts
            # - Total amount
            # - Invoice number if available
            
            logger.info("Parsing AI response into structured data")
            
            # Placeholder - implement actual parsing logic based on AI response format
            # You'll need to analyze the actual AI responses to build this parser
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None

    async def suggest_categories(self, line_items: List[HotelLineItem]) -> List[HotelLineItem]:
        """
        Use AI to suggest categories for extracted line items.
        
        Args:
            line_items: List of line items without categories
            
        Returns:
            Same line items with suggested_category filled in
        """
        try:
            logger.info(f"Suggesting categories for {len(line_items)} line items")
            
            # Prepare line items text for AI
            items_text = "\n".join([
                f"- {item.description}: {item.amount}" 
                for item in line_items
            ])

            messages = [
                ChatCompletionSystemMessageParam(
                    role="system",
                    content=HOTEL_CATEGORIZATION_PROMPT
                ),
                ChatCompletionUserMessageParam(
                    role="user",
                    content=f"Categorize these hotel invoice line items:\n\n{items_text}"
                )
            ]

            response = await self.client.chat.completions.create(
                model=INVOICE_DETAILS_EXTRACTOR_MODEL_NAME,
                messages=messages,
                temperature=0.1,
            )

            ai_response = response.choices[0].message.content
            
            # Parse AI category suggestions and apply to line items
            categorized_items = self._apply_category_suggestions(line_items, ai_response)
            
            logger.info("Successfully applied AI category suggestions")
            return categorized_items

        except Exception as e:
            logger.error(f"Error suggesting categories: {e}")
            # Return original items without suggestions if AI fails
            return line_items

    def _apply_category_suggestions(self, line_items: List[HotelLineItem], ai_response: str) -> List[HotelLineItem]:
        """Apply AI category suggestions to line items."""
        try:
            # TODO: Implement parsing of AI category suggestions
            # This should map AI suggested categories back to the line items
            
            # For now, return original items
            # In production, parse ai_response and set suggested_category for each item
            
            return line_items
            
        except Exception as e:
            logger.error(f"Error applying category suggestions: {e}")
            return line_items


# Convenience function for direct usage
async def extract_hotel_invoice(file_path: Path) -> Optional[HotelInvoiceDetails]:
    """
    Extract hotel invoice details from file.
    
    Args:
        file_path: Path to hotel invoice file (PDF or image)
        
    Returns:
        HotelInvoiceDetails if successful, None otherwise
    """
    extractor = HotelInvoiceExtractor()
    
    if file_path.suffix.lower() == '.pdf':
        return await extractor.extract_from_pdf(file_path)
    else:
        logger.error(f"Unsupported file format: {file_path.suffix}")
        return None