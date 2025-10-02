"""
Pydantic models for Hotel Itemizer feature.

This module defines the data structures used throughout the hotel itemization process,
including invoice extraction, categorization, and MS Expense integration.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class HotelCategoryEnum(str, Enum):
    """Enum for hotel expense categories matching MS Expense subcategories."""
    DAILY_ROOM_RATE = "Daily Room Rate"
    HOTEL_DEPOSIT = "Hotel Deposit"
    HOTEL_TAX = "Hotel Tax"
    HOTEL_TELEPHONE = "Hotel Telephone"
    INCIDENTALS = "Incidentals"
    LAUNDRY = "Laundry"
    ROOM_SERVICE_MEALS = "Room Service & Meals etc"
    IGNORE = "Ignore"


class HotelLineItem(BaseModel):
    """Individual line item extracted from hotel invoice."""
    description: str = Field(description="Line item description from invoice")
    amount: Decimal = Field(description="Line item amount")
    suggested_category: Optional[HotelCategoryEnum] = Field(
        default=None, description="AI-suggested category"
    )
    user_category: Optional[HotelCategoryEnum] = Field(
        default=None, description="User-validated category"
    )
    is_daily: bool = Field(
        default=False, description="Whether this item should be calculated as daily rate"
    )


class HotelInvoiceDetails(BaseModel):
    """Complete hotel invoice information extracted by AI."""
    hotel_name: str = Field(description="Hotel name")
    hotel_location: Optional[str] = Field(default=None, description="Hotel location/address")
    check_in_date: date = Field(description="Check-in date")
    check_out_date: date = Field(description="Check-out date")
    total_amount: Decimal = Field(description="Total invoice amount")
    line_items: List[HotelLineItem] = Field(description="Individual line items")
    currency: str = Field(default="USD", description="Currency code")
    invoice_number: Optional[str] = Field(default=None, description="Invoice/confirmation number")


class ConsolidatedCategory(BaseModel):
    """Category with consolidated amount and daily rate calculation."""
    category: HotelCategoryEnum = Field(description="Hotel expense category")
    total_amount: Decimal = Field(description="Consolidated total for this category")
    daily_rate: Optional[Decimal] = Field(
        default=None, description="Daily rate (for daily categories)"
    )
    quantity: int = Field(default=1, description="Number of days or occurrences")
    source_items: List[HotelLineItem] = Field(
        description="Original line items that make up this category"
    )


class HotelItemizationResult(BaseModel):
    """Final result of hotel itemization process."""
    invoice_details: HotelInvoiceDetails = Field(description="Original invoice details")
    consolidated_categories: List[ConsolidatedCategory] = Field(
        description="Categories with consolidated amounts and daily rates"
    )
    total_itemized: Decimal = Field(description="Sum of all itemized amounts")
    total_original: Decimal = Field(description="Original expense total")
    validation_passed: bool = Field(description="Whether totals match")
    number_of_nights: int = Field(description="Number of nights calculated from dates")


class MSExpenseItemEntry(BaseModel):
    """Individual entry for MS Expense itemization interface."""
    subcategory: HotelCategoryEnum = Field(description="MS Expense subcategory")
    start_date: date = Field(description="Start date (check-in date)")
    daily_rate: Decimal = Field(description="Daily rate amount")
    quantity: int = Field(description="Number of days/occurrences")
    total_amount: Decimal = Field(description="Total for this entry (daily_rate * quantity)")


class HotelProcessingRequest(BaseModel):
    """Request model for hotel invoice processing."""
    file_path: str = Field(description="Path to uploaded hotel invoice file")
    expense_id: Optional[str] = Field(default=None, description="Associated expense ID")
    original_amount: Decimal = Field(description="Original expense amount for validation")


class HotelProcessingResponse(BaseModel):
    """Response model for hotel processing operations."""
    success: bool = Field(description="Whether operation was successful")
    message: str = Field(description="Status message")
    data: Optional[HotelItemizationResult] = Field(default=None, description="Processing results")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class CategoryValidationRequest(BaseModel):
    """Request for category validation and consolidation."""
    invoice_details: HotelInvoiceDetails = Field(description="Invoice with user-validated categories")
    
    
class CategoryValidationResponse(BaseModel):
    """Response for category validation."""
    consolidated_categories: List[ConsolidatedCategory] = Field(description="Consolidated results")
    validation_passed: bool = Field(description="Whether validation passed")
    total_itemized: Decimal = Field(description="Total itemized amount")
    errors: List[str] = Field(default_factory=list, description="Validation errors")