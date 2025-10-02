"""
Hotel Categorizer

This module handles category mapping, validation, and consolidation
for hotel expense line items.
"""

import logging
from decimal import Decimal
from typing import Dict, List

from hotel_itemizer.config import DAILY_RATE_CATEGORIES, ONE_TIME_CATEGORIES, EXCLUDE_CATEGORIES
from hotel_itemizer.models import (
    HotelLineItem,
    HotelCategoryEnum,
    ConsolidatedCategory,
    HotelInvoiceDetails,
)

logger = logging.getLogger(__name__)


class HotelCategorizer:
    """Handles categorization and consolidation of hotel expense line items."""

    def __init__(self):
        """Initialize the categorizer."""
        pass

    def validate_categories(self, invoice_details: HotelInvoiceDetails) -> Dict[str, any]:
        """
        Validate user-assigned categories and prepare for consolidation.
        
        Args:
            invoice_details: Hotel invoice with user-validated categories
            
        Returns:
            Dictionary with validation results and errors
        """
        try:
            logger.info("Validating categories for hotel invoice")
            
            errors = []
            total_assigned = Decimal('0')
            
            # Check that all non-ignored items have categories assigned
            for item in invoice_details.line_items:
                if item.user_category is None:
                    errors.append(f"No category assigned for: {item.description}")
                elif item.user_category != HotelCategoryEnum.IGNORE:
                    total_assigned += item.amount

            # Check if totals match (allowing for small rounding differences)
            total_difference = abs(total_assigned - invoice_details.total_amount)
            if total_difference > Decimal('0.01'):
                errors.append(
                    f"Total assigned ({total_assigned}) does not match invoice total "
                    f"({invoice_details.total_amount}). Difference: {total_difference}"
                )

            validation_passed = len(errors) == 0
            
            logger.info(f"Category validation completed. Passed: {validation_passed}")
            
            return {
                "validation_passed": validation_passed,
                "total_assigned": total_assigned,
                "total_original": invoice_details.total_amount,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error validating categories: {e}")
            return {
                "validation_passed": False,
                "total_assigned": Decimal('0'),
                "total_original": invoice_details.total_amount,
                "errors": [f"Validation error: {str(e)}"]
            }

    def consolidate_categories(self, invoice_details: HotelInvoiceDetails) -> List[ConsolidatedCategory]:
        """
        Consolidate line items by category and calculate daily rates.
        
        Args:
            invoice_details: Hotel invoice with validated categories
            
        Returns:
            List of consolidated categories with totals and daily rates
        """
        try:
            logger.info("Consolidating categories")
            
            # Group items by category
            category_groups: Dict[HotelCategoryEnum, List[HotelLineItem]] = {}
            
            for item in invoice_details.line_items:
                if item.user_category and item.user_category != HotelCategoryEnum.IGNORE:
                    if item.user_category not in category_groups:
                        category_groups[item.user_category] = []
                    category_groups[item.user_category].append(item)

            # Calculate number of nights
            nights = (invoice_details.check_out_date - invoice_details.check_in_date).days
            if nights <= 0:
                nights = 1  # Minimum 1 night for same-day checkout
                
            logger.info(f"Calculated {nights} nights stay")

            # Create consolidated categories
            consolidated = []
            
            for category, items in category_groups.items():
                total_amount = sum(item.amount for item in items)
                
                # Determine if this is a daily rate category
                is_daily = category.value in DAILY_RATE_CATEGORIES
                
                if is_daily:
                    daily_rate = total_amount / nights
                    quantity = nights
                else:
                    daily_rate = total_amount  # For one-time charges
                    quantity = 1

                consolidated_category = ConsolidatedCategory(
                    category=category,
                    total_amount=total_amount,
                    daily_rate=daily_rate,
                    quantity=quantity,
                    source_items=items
                )
                
                consolidated.append(consolidated_category)
                
                logger.info(
                    f"Consolidated {category.value}: {total_amount} "
                    f"(daily: {daily_rate}, qty: {quantity})"
                )

            return consolidated
            
        except Exception as e:
            logger.error(f"Error consolidating categories: {e}")
            return []

    def get_category_mapping(self) -> Dict[str, Dict[str, any]]:
        """
        Get category mapping information for frontend.
        
        Returns:
            Dictionary with category details including daily/one-time classification
        """
        mapping = {}
        
        for category in HotelCategoryEnum:
            mapping[category.value] = {
                "title": category.value,
                "value": category.value,
                "is_daily": category.value in DAILY_RATE_CATEGORIES,
                "is_one_time": category.value in ONE_TIME_CATEGORIES,
                "is_exclude": category.value in EXCLUDE_CATEGORIES
            }
            
        return mapping

    def suggest_category_for_description(self, description: str, amount: Decimal) -> HotelCategoryEnum:
        """
        Suggest a category based on line item description and amount.
        
        This is a fallback method for when AI categorization is not available.
        
        Args:
            description: Line item description
            amount: Line item amount
            
        Returns:
            Suggested category enum
        """
        description_lower = description.lower()
        
        # Room rate indicators
        if any(term in description_lower for term in ['room', 'accommodation', 'stay', 'night']):
            return HotelCategoryEnum.DAILY_ROOM_RATE
            
        # Tax indicators
        if any(term in description_lower for term in ['tax', 'vat', 'occupancy', 'city tax']):
            return HotelCategoryEnum.HOTEL_TAX
            
        # Deposit indicators
        if any(term in description_lower for term in ['deposit', 'advance', 'prepayment']):
            return HotelCategoryEnum.HOTEL_DEPOSIT
            
        # Telephone indicators
        if any(term in description_lower for term in ['phone', 'telephone', 'call', 'communication']):
            return HotelCategoryEnum.HOTEL_TELEPHONE
            
        # Food and beverage indicators
        if any(term in description_lower for term in ['room service', 'restaurant', 'bar', 'food', 'beverage', 'meal']):
            return HotelCategoryEnum.ROOM_SERVICE_MEALS
            
        # Laundry indicators
        if any(term in description_lower for term in ['laundry', 'cleaning', 'valet']):
            return HotelCategoryEnum.LAUNDRY
            
        # Default to incidentals for everything else
        return HotelCategoryEnum.INCIDENTALS


# Convenience functions
def validate_hotel_categories(invoice_details: HotelInvoiceDetails) -> Dict[str, any]:
    """Validate categories for a hotel invoice."""
    categorizer = HotelCategorizer()
    return categorizer.validate_categories(invoice_details)


def consolidate_hotel_categories(invoice_details: HotelInvoiceDetails) -> List[ConsolidatedCategory]:
    """Consolidate categories for a hotel invoice."""
    categorizer = HotelCategorizer()
    return categorizer.consolidate_categories(invoice_details)