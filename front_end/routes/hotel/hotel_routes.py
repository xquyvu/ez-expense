"""
Hotel Routes

API routes for hotel itemization functionality.
Provides RESTful endpoints for hotel invoice processing, categorization, and MS Expense integration.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from quart import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Create blueprint
hotel_bp = Blueprint("hotel", __name__, url_prefix="/api/hotel")


@hotel_bp.route("/health", methods=["GET"])
async def health_check():
    """Health check endpoint for hotel itemizer service."""
    return jsonify({
        "status": "healthy",
        "service": "hotel_itemizer",
        "timestamp": datetime.now().isoformat()
    })


@hotel_bp.route("/extract", methods=["POST"])
async def extract_invoice():
    """
    Extract hotel invoice details from uploaded file.
    
    Expects multipart/form-data with:
    - file: PDF hotel invoice
    - original_amount: Original expense amount for validation
    """
    try:
        logger.info("Starting hotel invoice extraction")
        
        # Check if file is present
        files = await request.files
        if 'file' not in files:
            return jsonify({
                "success": False,
                "message": "No file provided",
                "errors": ["File is required"]
            }), 400
            
        file = files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "message": "No file selected",
                "errors": ["File is required"]
            }), 400

        # Get form data
        form = await request.form
        original_amount = form.get('original_amount')
        
        if not original_amount:
            return jsonify({
                "success": False,
                "message": "Original amount is required",
                "errors": ["original_amount field is required"]
            }), 400

        # Validate file type
        filename = secure_filename(file.filename)
        if not filename.lower().endswith('.pdf'):
            return jsonify({
                "success": False,
                "message": "Only PDF files are supported",
                "errors": ["File must be a PDF"]
            }), 400

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            await file.save(temp_file.name)
            temp_path = Path(temp_file.name)

        try:
            # TODO: Implement actual extraction once dependencies are resolved
            # For now, return a placeholder response
            
            logger.info("Successfully extracted invoice (placeholder)")
            
            return jsonify({
                "success": True,
                "message": "Successfully extracted invoice details (placeholder)",
                "data": {
                    "hotel_name": "Sample Hotel",
                    "hotel_location": "Sample Location",
                    "check_in_date": "2025-06-26",
                    "check_out_date": "2025-06-28",
                    "total_amount": original_amount,
                    "currency": "USD",
                    "invoice_number": "INV-12345",
                    "line_items": [
                        {
                            "description": "Room Rate",
                            "amount": "80.00",
                            "suggested_category": "Daily Room Rate",
                            "is_daily": True
                        },
                        {
                            "description": "Hotel Tax",
                            "amount": "20.00",
                            "suggested_category": "Hotel Tax",
                            "is_daily": True
                        }
                    ]
                },
                "validation": {
                    "passed": True,
                    "errors": []
                }
            })
            
        finally:
            # Clean up temporary file
            temp_path.unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"Error extracting invoice: {e}")
        return jsonify({
            "success": False,
            "message": "Error processing invoice",
            "errors": [str(e)]
        }), 500


@hotel_bp.route("/validate", methods=["POST"])
async def validate_categories():
    """
    Validate user-assigned categories and calculate consolidation.
    
    Expects JSON with validated invoice details including user_category for each line item.
    """
    try:
        logger.info("Starting category validation")
        
        # Get JSON data
        data = await request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided",
                "errors": ["Request body must contain JSON data"]
            }), 400

        # TODO: Implement actual validation once models are available
        
        logger.info("Category validation completed (placeholder)")
        
        return jsonify({
            "success": True,
            "message": "Successfully validated and consolidated categories (placeholder)",
            "data": {
                "consolidated_categories": [
                    {
                        "category": "Daily Room Rate",
                        "total_amount": "80.00",
                        "daily_rate": "40.00",
                        "quantity": 2,
                        "source_items_count": 1
                    },
                    {
                        "category": "Hotel Tax", 
                        "total_amount": "20.00",
                        "daily_rate": "10.00",
                        "quantity": 2,
                        "source_items_count": 1
                    }
                ],
                "total_itemized": "100.00",
                "total_original": "100.00",
                "validation_passed": True
            },
            "validation": {
                "passed": True,
                "errors": []
            }
        })
        
    except Exception as e:
        logger.error(f"Error validating categories: {e}")
        return jsonify({
            "success": False,
            "message": "Error validating categories",
            "errors": [str(e)]
        }), 500


@hotel_bp.route("/categories", methods=["GET"])
async def get_categories():
    """
    Get available hotel categories for frontend dropdown.
    """
    try:
        categories = [
            {"title": "Daily Room Rate", "value": "Daily Room Rate", "is_daily": True},
            {"title": "Hotel Deposit", "value": "Hotel Deposit", "is_daily": False},
            {"title": "Hotel Tax", "value": "Hotel Tax", "is_daily": True},
            {"title": "Hotel Telephone", "value": "Hotel Telephone", "is_daily": False},
            {"title": "Incidentals", "value": "Incidentals", "is_daily": False},
            {"title": "Laundry", "value": "Laundry", "is_daily": False},
            {"title": "Room Service & Meals etc", "value": "Room Service & Meals etc", "is_daily": False},
            {"title": "Ignore", "value": "Ignore", "is_daily": False}
        ]
        
        return jsonify({
            "success": True,
            "message": "Categories retrieved successfully",
            "data": {
                "categories": categories
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return jsonify({
            "success": False,
            "message": "Error retrieving categories",
            "errors": [str(e)]
        }), 500


@hotel_bp.route("/itemize", methods=["POST"])
async def itemize_expense():
    """
    Create MS Expense itemization entries and trigger browser automation.
    """
    try:
        logger.info("Starting MS Expense itemization")
        
        # Get JSON data
        data = await request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided",
                "errors": ["Request body must contain JSON data"]
            }), 400

        # Extract consolidated categories from request
        consolidated_categories = data.get("consolidated_categories", [])
        if not consolidated_categories:
            return jsonify({
                "success": False,
                "message": "No consolidated categories provided",
                "errors": ["consolidated_categories field is required"]
            }), 400

        # Convert to MS Expense entries using DailyRateCalculator
        try:
            from hotel_itemizer.daily_rate_calculator import DailyRateCalculator
            from hotel_itemizer.ms_expense_automator import populate_hotel_expenses_in_ms_expense
            from decimal import Decimal
            
            calculator = DailyRateCalculator()
            
            # Convert consolidated categories to MS Expense entries
            # First, convert data to proper models
            from hotel_itemizer.models import ConsolidatedCategory
            from datetime import datetime
            
            consolidated_models = []
            for category in consolidated_categories:
                check_in = datetime.strptime(category.get("check_in_date", "2025-01-01"), "%Y-%m-%d").date()
                check_out = datetime.strptime(category.get("check_out_date", "2025-01-02"), "%Y-%m-%d").date()
                
                consolidated_models.append(ConsolidatedCategory(
                    category=category.get("category"),
                    total_amount=Decimal(str(category.get("total_amount", 0))),
                    source_items=category.get("source_line_items", [])
                ))
            
            # Use the calculator to generate MS Expense entries
            ms_expense_entries = calculator.calculate_daily_rates(
                consolidated_categories=consolidated_models,
                check_in=check_in,
                check_out=check_out
            )
            
            logger.info(f"Generated {len(ms_expense_entries)} MS Expense entries")
            
            # Trigger browser automation
            automation_result = await populate_hotel_expenses_in_ms_expense(ms_expense_entries)
            
            if automation_result.get("success"):
                logger.info("MS Expense itemization completed successfully")
                
                return jsonify({
                    "success": True,
                    "message": "Expense itemization completed successfully",
                    "data": {
                        "entries_created": automation_result.get("populated_count", 0),
                        "total_entries": automation_result.get("total_count", 0),
                        "total_itemized": sum(float(cat.get("total_amount", 0)) for cat in consolidated_categories),
                        "automation_details": automation_result.get("entries", [])
                    }
                })
            else:
                logger.error(f"Browser automation failed: {automation_result.get('error')}")
                return jsonify({
                    "success": False,
                    "message": "Browser automation failed",
                    "errors": [automation_result.get("error", "Unknown automation error")]
                }), 500
            
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return jsonify({
                "success": False,
                "message": "Hotel itemizer modules not available",
                "errors": [str(e)]
            }), 500
        
    except Exception as e:
        logger.error(f"Error itemizing expense: {e}")
        return jsonify({
            "success": False,
            "message": "Error itemizing expense", 
            "errors": [str(e)]
        }), 500