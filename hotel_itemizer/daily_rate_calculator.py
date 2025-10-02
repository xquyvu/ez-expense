"""
Daily Rate Calculator

This module handles calculation of daily rates and quantities
for multi-day hotel stays.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Tuple

from hotel_itemizer.models import ConsolidatedCategory, MSExpenseItemEntry, HotelCategoryEnum

logger = logging.getLogger(__name__)


class DailyRateCalculator:
    """Handles daily rate calculations for hotel itemization."""

    def __init__(self):
        """Initialize the calculator."""
        pass

    def calculate_nights(self, check_in: date, check_out: date) -> int:
        """
        Calculate number of nights between check-in and check-out dates.
        
        Args:
            check_in: Check-in date
            check_out: Check-out date
            
        Returns:
            Number of nights (minimum 1)
        """
        nights = (check_out - check_in).days
        return max(1, nights)  # Minimum 1 night even for same-day checkout

    def calculate_daily_rates(
        self, 
        consolidated_categories: List[ConsolidatedCategory],
        check_in: date,
        check_out: date
    ) -> List[MSExpenseItemEntry]:
        """
        Calculate daily rates for MS Expense itemization interface.
        
        Args:
            consolidated_categories: List of consolidated categories with totals
            check_in: Check-in date for start date
            check_out: Check-out date for calculating nights
            
        Returns:
            List of MS Expense item entries with daily rates and quantities
        """
        try:
            logger.info("Calculating daily rates for MS Expense itemization")
            
            nights = self.calculate_nights(check_in, check_out)
            ms_expense_entries = []
            
            for category in consolidated_categories:
                # Skip ignored categories
                if category.category == HotelCategoryEnum.IGNORE:
                    continue
                    
                entry = MSExpenseItemEntry(
                    subcategory=category.category,
                    start_date=check_in,
                    daily_rate=category.daily_rate,
                    quantity=category.quantity,
                    total_amount=category.total_amount
                )
                
                ms_expense_entries.append(entry)
                
                logger.info(
                    f"Created MS Expense entry for {category.category.value}: "
                    f"daily_rate={category.daily_rate}, quantity={category.quantity}, "
                    f"total={category.total_amount}"
                )

            return ms_expense_entries
            
        except Exception as e:
            logger.error(f"Error calculating daily rates: {e}")
            return []

    def validate_daily_rate_totals(
        self, 
        ms_expense_entries: List[MSExpenseItemEntry],
        original_total: Decimal
    ) -> Tuple[bool, Decimal, List[str]]:
        """
        Validate that daily rate calculations sum to original expense total.
        
        Args:
            ms_expense_entries: List of calculated MS Expense entries
            original_total: Original expense total amount
            
        Returns:
            Tuple of (validation_passed, calculated_total, errors)
        """
        try:
            calculated_total = sum(entry.total_amount for entry in ms_expense_entries)
            
            # Allow for small rounding differences (up to 1 cent)
            difference = abs(calculated_total - original_total)
            validation_passed = difference <= Decimal('0.01')
            
            errors = []
            if not validation_passed:
                errors.append(
                    f"Daily rate totals ({calculated_total}) do not match "
                    f"original expense ({original_total}). Difference: {difference}"
                )
            
            logger.info(
                f"Daily rate validation: passed={validation_passed}, "
                f"calculated={calculated_total}, original={original_total}"
            )
            
            return validation_passed, calculated_total, errors
            
        except Exception as e:
            logger.error(f"Error validating daily rate totals: {e}")
            return False, Decimal('0'), [f"Validation error: {str(e)}"]

    def adjust_for_rounding(
        self,
        ms_expense_entries: List[MSExpenseItemEntry], 
        target_total: Decimal
    ) -> List[MSExpenseItemEntry]:
        """
        Adjust daily rates to account for rounding differences.
        
        This ensures the itemized total exactly matches the original expense.
        
        Args:
            ms_expense_entries: List of MS Expense entries
            target_total: Target total amount to match
            
        Returns:
            Adjusted list of MS Expense entries
        """
        try:
            if not ms_expense_entries:
                return ms_expense_entries
                
            current_total = sum(entry.total_amount for entry in ms_expense_entries)
            difference = target_total - current_total
            
            # If difference is negligible, no adjustment needed
            if abs(difference) <= Decimal('0.01'):
                return ms_expense_entries
                
            logger.info(f"Adjusting for rounding difference: {difference}")
            
            # Apply adjustment to the largest entry (typically room rate)
            adjusted_entries = ms_expense_entries.copy()
            
            # Find the entry with the largest total amount
            largest_entry_index = max(
                range(len(adjusted_entries)),
                key=lambda i: adjusted_entries[i].total_amount
            )
            
            # Adjust the daily rate and total for the largest entry
            largest_entry = adjusted_entries[largest_entry_index]
            
            # Recalculate daily rate with adjustment
            new_total = largest_entry.total_amount + difference
            new_daily_rate = new_total / largest_entry.quantity if largest_entry.quantity > 0 else new_total
            
            adjusted_entries[largest_entry_index] = MSExpenseItemEntry(
                subcategory=largest_entry.subcategory,
                start_date=largest_entry.start_date,
                daily_rate=new_daily_rate,
                quantity=largest_entry.quantity,
                total_amount=new_total
            )
            
            logger.info(
                f"Applied rounding adjustment to {largest_entry.subcategory.value}: "
                f"new_daily_rate={new_daily_rate}, new_total={new_total}"
            )
            
            return adjusted_entries
            
        except Exception as e:
            logger.error(f"Error adjusting for rounding: {e}")
            return ms_expense_entries


# Convenience functions
def calculate_hotel_daily_rates(
    consolidated_categories: List[ConsolidatedCategory],
    check_in: date,
    check_out: date
) -> List[MSExpenseItemEntry]:
    """Calculate daily rates for hotel categories."""
    calculator = DailyRateCalculator()
    return calculator.calculate_daily_rates(consolidated_categories, check_in, check_out)


def validate_hotel_totals(
    ms_expense_entries: List[MSExpenseItemEntry],
    original_total: Decimal
) -> Tuple[bool, Decimal, List[str]]:
    """Validate hotel itemization totals."""
    calculator = DailyRateCalculator()
    return calculator.validate_daily_rate_totals(ms_expense_entries, original_total)