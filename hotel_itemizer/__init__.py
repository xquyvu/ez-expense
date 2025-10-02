"""
Hotel Itemizer Module

This module provides AI-powered hotel invoice processing, categorization,
and integration with MS Expense itemization interface.

Main components:
- hotel_extractor: AI-powered PDF invoice extraction
- hotel_categorizer: Category suggestion and mapping
- daily_rate_calculator: Daily rate calculations for multi-day stays
- hotel_validator: Validation and consolidation logic
- models: Pydantic data models
"""

from .config import HOTEL_CATEGORIES, DAILY_RATE_CATEGORIES, ONE_TIME_CATEGORIES

__version__ = "1.0.0"
__all__ = [
    "HOTEL_CATEGORIES",
    "DAILY_RATE_CATEGORIES", 
    "ONE_TIME_CATEGORIES"
]