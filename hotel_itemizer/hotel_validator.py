"""
Hotel Validator

This module handles validation and consolidation logic for hotel itemization,
ensuring data integrity and total validation throughout the process.
"""

import logging
from decimal import Decimal
from typing import List, Tuple

from hotel_itemizer.models import (
    HotelInvoiceDetails,
    HotelItemizationResult,
    ConsolidatedCategory,
    MSExpenseItemEntry,
    HotelCategoryEnum,
)

logger = logging.getLogger(__name__)


class HotelValidator:
    """Handles validation and consolidation for hotel expense processing."""

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate_invoice_details(self, invoice_details: HotelInvoiceDetails) -> Tuple[bool, List[str]]:
        """
        Validate extracted invoice details for completeness and consistency.
        
        Args:
            invoice_details: Extracted hotel invoice details
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Check required fields
            if not invoice_details.hotel_name:
                errors.append("Hotel name is required")
                
            if not invoice_details.line_items:
                errors.append("No line items found in invoice")
                
            if invoice_details.total_amount <= 0:
                errors.append("Total amount must be greater than zero")
                
            # Validate dates
            if invoice_details.check_out_date < invoice_details.check_in_date:
                errors.append("Check-out date cannot be before check-in date")
                
            # Validate line items
            line_items_total = sum(item.amount for item in invoice_details.line_items)
            
            # Allow for small differences due to rounding or fees not itemized
            total_difference = abs(line_items_total - invoice_details.total_amount)
            if total_difference > invoice_details.total_amount * Decimal('0.1'):  # 10% tolerance
                errors.append(
                    f"Line items total ({line_items_total}) differs significantly "
                    f"from invoice total ({invoice_details.total_amount})"
                )
            
            # Check for negative amounts
            negative_items = [item for item in invoice_details.line_items if item.amount < 0]
            if negative_items:
                logger.warning(f"Found {len(negative_items)} negative line items (possible credits/refunds)")
                
            is_valid = len(errors) == 0
            
            logger.info(f"Invoice validation completed. Valid: {is_valid}")
            if errors:
                logger.warning(f"Validation errors: {errors}")
                
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error validating invoice details: {e}")
            return False, [f"Validation error: {str(e)}"]

    def validate_categorization(self, invoice_details: HotelInvoiceDetails) -> Tuple[bool, List[str]]:
        """
        Validate that all line items have appropriate categories assigned.
        
        Args:
            invoice_details: Invoice details with user-assigned categories
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            uncategorized_items = []
            ignored_total = Decimal('0')
            categorized_total = Decimal('0')
            
            for item in invoice_details.line_items:
                if item.user_category is None:
                    uncategorized_items.append(item.description)
                elif item.user_category == HotelCategoryEnum.IGNORE:
                    ignored_total += item.amount
                else:
                    categorized_total += item.amount
                    
            # Check for uncategorized items
            if uncategorized_items:
                errors.append(f"Uncategorized items: {', '.join(uncategorized_items[:3])}")
                if len(uncategorized_items) > 3:
                    errors.append(f"... and {len(uncategorized_items) - 3} more items")
                    
            # Validate total consistency
            expected_total = categorized_total + ignored_total
            total_difference = abs(expected_total - invoice_details.total_amount)
            
            if total_difference > Decimal('0.01'):
                errors.append(
                    f"Categorized total ({categorized_total}) plus ignored items ({ignored_total}) "
                    f"does not match invoice total ({invoice_details.total_amount})"
                )
            
            # Check for reasonable category distribution
            if categorized_total == 0 and ignored_total > 0:
                errors.append("All items are marked as 'Ignore' - at least some items should be categorized")
                
            is_valid = len(errors) == 0
            
            logger.info(
                f"Categorization validation completed. Valid: {is_valid}, "
                f"categorized: {categorized_total}, ignored: {ignored_total}"
            )
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error validating categorization: {e}")
            return False, [f"Categorization validation error: {str(e)}"]

    def validate_consolidation(
        self, 
        consolidated_categories: List[ConsolidatedCategory],
        original_total: Decimal
    ) -> Tuple[bool, List[str]]:
        """
        Validate consolidated categories for consistency and accuracy.
        
        Args:
            consolidated_categories: List of consolidated categories
            original_total: Original invoice total for validation
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            if not consolidated_categories:
                errors.append("No categories to consolidate")
                return False, errors
                
            total_consolidated = sum(cat.total_amount for cat in consolidated_categories)
            
            # Validate total matches (allowing small rounding differences)
            total_difference = abs(total_consolidated - original_total)
            if total_difference > Decimal('0.01'):
                errors.append(
                    f"Consolidated total ({total_consolidated}) does not match "
                    f"original total ({original_total}). Difference: {total_difference}"
                )
            
            # Validate individual categories
            for category in consolidated_categories:
                # Check for zero or negative totals
                if category.total_amount <= 0:
                    errors.append(f"Category '{category.category.value}' has invalid total: {category.total_amount}")
                    
                # Validate daily rate calculation
                if category.quantity > 0:
                    expected_total = category.daily_rate * category.quantity
                    calc_difference = abs(expected_total - category.total_amount)
                    if calc_difference > Decimal('0.01'):
                        errors.append(
                            f"Category '{category.category.value}' daily rate calculation error: "
                            f"daily_rate({category.daily_rate}) * quantity({category.quantity}) "
                            f"!= total({category.total_amount})"
                        )
                        
                # Check that source items exist
                if not category.source_items:
                    errors.append(f"Category '{category.category.value}' has no source items")
                    
            is_valid = len(errors) == 0
            
            logger.info(
                f"Consolidation validation completed. Valid: {is_valid}, "
                f"categories: {len(consolidated_categories)}, total: {total_consolidated}"
            )
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error validating consolidation: {e}")
            return False, [f"Consolidation validation error: {str(e)}"]

    def create_itemization_result(
        self,
        invoice_details: HotelInvoiceDetails,
        consolidated_categories: List[ConsolidatedCategory]
    ) -> HotelItemizationResult:
        """
        Create final itemization result with validation.
        
        Args:
            invoice_details: Original invoice details
            consolidated_categories: Consolidated categories
            
        Returns:
            Complete itemization result
        """
        try:
            total_itemized = sum(cat.total_amount for cat in consolidated_categories)
            total_original = invoice_details.total_amount
            
            # Calculate number of nights
            nights = (invoice_details.check_out_date - invoice_details.check_in_date).days
            nights = max(1, nights)  # Minimum 1 night
            
            # Validate totals match
            validation_passed = abs(total_itemized - total_original) <= Decimal('0.01')
            
            result = HotelItemizationResult(
                invoice_details=invoice_details,
                consolidated_categories=consolidated_categories,
                total_itemized=total_itemized,
                total_original=total_original,
                validation_passed=validation_passed,
                number_of_nights=nights
            )
            
            logger.info(
                f"Created itemization result: {len(consolidated_categories)} categories, "
                f"validation_passed: {validation_passed}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating itemization result: {e}")
            # Return a basic result with error indication
            return HotelItemizationResult(
                invoice_details=invoice_details,
                consolidated_categories=[],
                total_itemized=Decimal('0'),
                total_original=invoice_details.total_amount,
                validation_passed=False,
                number_of_nights=1
            )

    def validate_ms_expense_entries(
        self,
        ms_expense_entries: List[MSExpenseItemEntry],
        original_total: Decimal
    ) -> Tuple[bool, List[str]]:
        """
        Validate MS Expense entries before submitting to automation.
        
        Args:
            ms_expense_entries: List of MS Expense entries
            original_total: Original expense total
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            if not ms_expense_entries:
                errors.append("No MS Expense entries to validate")
                return False, errors
                
            # Validate total
            entries_total = sum(entry.total_amount for entry in ms_expense_entries)
            total_difference = abs(entries_total - original_total)
            
            if total_difference > Decimal('0.01'):
                errors.append(
                    f"MS Expense entries total ({entries_total}) does not match "
                    f"original expense ({original_total}). Difference: {total_difference}"
                )
            
            # Validate individual entries
            for entry in ms_expense_entries:
                # Check for valid amounts
                if entry.daily_rate <= 0:
                    errors.append(f"Invalid daily rate for {entry.subcategory.value}: {entry.daily_rate}")
                    
                if entry.quantity <= 0:
                    errors.append(f"Invalid quantity for {entry.subcategory.value}: {entry.quantity}")
                    
                # Check calculation consistency
                expected_total = entry.daily_rate * entry.quantity
                calc_difference = abs(expected_total - entry.total_amount)
                if calc_difference > Decimal('0.01'):
                    errors.append(
                        f"Calculation error for {entry.subcategory.value}: "
                        f"daily_rate({entry.daily_rate}) * quantity({entry.quantity}) "
                        f"!= total({entry.total_amount})"
                    )
            
            is_valid = len(errors) == 0
            
            logger.info(
                f"MS Expense entries validation completed. Valid: {is_valid}, "
                f"entries: {len(ms_expense_entries)}, total: {entries_total}"
            )
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error validating MS Expense entries: {e}")
            return False, [f"MS Expense validation error: {str(e)}"]


# Convenience functions for validation
def validate_hotel_invoice(invoice_details: HotelInvoiceDetails) -> Tuple[bool, List[str]]:
    """Validate hotel invoice details."""
    validator = HotelValidator()
    return validator.validate_invoice_details(invoice_details)


def validate_hotel_categorization(invoice_details: HotelInvoiceDetails) -> Tuple[bool, List[str]]:
    """Validate hotel categorization."""
    validator = HotelValidator()
    return validator.validate_categorization(invoice_details)