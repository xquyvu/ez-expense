"""
Expense-related API routes for the Flask application.
"""

import logging
import os
import sys
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEBUG

# Add the parent directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from expense_importer import (
        get_expense_page,
        import_expense_wrapper,
    )
except ImportError as e:
    logging.error(f"Could not import expense_importer: {e}")
    get_expense_page = None
    import_expense_wrapper = None

try:
    from expense_matcher import receipt_match_score
except ImportError as e:
    logging.error(f"Could not import expense_matcher: {e}")
    receipt_match_score = None

# Create blueprint
expense_bp = Blueprint("expenses", __name__)
logger = logging.getLogger(__name__)


@expense_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Get the list of expense categories from category_list.txt for autocomplete functionality.
    """
    try:
        # Get the path to the category list file
        category_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets",
            "category_list.txt",
        )

        if not os.path.exists(category_file_path):
            logger.error(f"Category file not found: {category_file_path}")
            return jsonify({"error": "Category file not found"}), 404

        categories = []
        with open(category_file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line:  # Skip empty lines
                    categories.append(line)

        logger.info(f"Loaded {len(categories)} categories from {category_file_path}")
        return jsonify({"categories": categories})

    except Exception as e:
        logger.error(f"Error loading categories: {e}")
        return jsonify({"error": "Failed to load categories"}), 500


@expense_bp.route("/import", methods=["POST"])
def import_expenses():
    """
    Primary import endpoint that automatically chooses between mock and real import based on environment.
    This is the main endpoint used by the frontend in production.
    """
    try:
        logger.info(f"Starting expense import (DEBUG mode: {DEBUG})")

        if DEBUG:
            logger.info("Using mock data due to DEBUG=True")
            result = get_mock_expenses_internal()
            logger.info("Import completed successfully using mock source")
            return result
        else:
            logger.info("Using real browser import due to DEBUG=False")
            result = _import_real_data()
            logger.info("Import completed successfully using browser source")
            return result

    except Exception as e:
        logger.error(f"Error during expense import: {e}")
        return jsonify(
            {
                "error": "Import failed",
                "message": str(e),
            }
        ), 500


@expense_bp.route("/import/mock", methods=["POST"])
def import_expenses_mock():
    """
    Explicit mock import endpoint for testing and development.
    Always returns mock data regardless of DEBUG setting.
    """
    logger.info("Explicit mock import requested")
    return get_mock_expenses_internal()


@expense_bp.route("/import/real", methods=["POST"])
def import_expenses_real():
    """
    Explicit real import endpoint for testing and debugging.
    Always attempts real browser import regardless of DEBUG setting.
    """
    logger.info("Explicit real import requested")
    return _import_real_data()


def _import_real_data():
    """Internal function to handle real browser-based import."""
    if import_expense_wrapper is None:
        return jsonify(
            {
                "error": "Import function not available",
                "message": "Expense importer module could not be loaded.",
            }
        ), 500

    try:
        # Use the import_expense_wrapper function to get real browser data
        expense_df = import_expense_wrapper()
        expense_df["id"] = range(1, len(expense_df) + 1)

        # Convert DataFrame to list of dictionaries for JSON response
        expenses = expense_df.to_dict("records")

        logger.info(f"Successfully imported {len(expenses)} expenses from browser")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully imported {len(expenses)} expenses from My Expense",
                "data": expenses,
                "count": len(expenses),
                "source": "browser",
            }
        )

    except RuntimeError as e:
        # Handle browser connection errors specifically
        error_msg = str(e)
        if "Expense page not available" in error_msg:
            return jsonify(
                {
                    "error": "Browser session required",
                    "message": "No active browser session found. Please run main.py first to start the browser session, or set DEBUG=True in .env for mock data.",
                }
            ), 400
        else:
            return jsonify(
                {
                    "error": "Browser automation failed",
                    "message": error_msg,
                }
            ), 500

    except Exception as e:
        logger.error(f"Error in real data import: {e}")
        return jsonify(
            {
                "error": "Import failed",
                "message": str(e),
            }
        ), 500


def get_mock_expenses_internal():
    """Internal function to handle mock data import."""
    try:
        # Import mock function specifically for this endpoint
        from expense_importer import import_expense_mock

        mock_expenses_df = import_expense_mock()
        mock_expenses_df["id"] = range(1, len(mock_expenses_df) + 1)

        # Convert DataFrame to list of dictionaries for JSON response
        expenses = mock_expenses_df.to_dict("records")

        logger.info(f"Successfully loaded {len(expenses)} mock expenses")

        return jsonify(
            {
                "success": True,
                "message": f"Mock data loaded with {len(expenses)} expenses",
                "data": expenses,
                "count": len(expenses),
                "source": "mock",
            }
        )
    except Exception as e:
        logger.error(f"Error loading mock expenses: {e}")
        return jsonify(
            {
                "error": "Failed to load mock data",
                "message": str(e),
            }
        ), 500


@expense_bp.route("/mock", methods=["POST"])
def get_mock_expenses():
    """
    Explicit mock endpoint for testing purposes - always returns mock data regardless of DEBUG setting.
    """
    logger.info("Explicit mock data request")
    return get_mock_expenses_internal()


@expense_bp.route("/debug-status", methods=["GET"])
def get_debug_status():
    """
    Get the current DEBUG status from centralized configuration.
    """
    return jsonify({"debug": DEBUG})


@expense_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint that reports system status including browser availability.
    """
    try:
        # Check browser availability
        browser_available = get_expense_page() is not None if get_expense_page else False

        # Check if import functions are available
        import_functions_available = import_expense_wrapper is not None

        # Determine overall health
        is_healthy = True
        issues = []

        if not import_functions_available:
            is_healthy = False
            issues.append("Import functions not available")

        if not DEBUG and not browser_available:
            is_healthy = False
            issues.append("Browser session not available (required for non-DEBUG mode)")

        health_status = {
            "status": "healthy" if is_healthy else "degraded",
            "debug_mode": DEBUG,
            "browser_available": browser_available,
            "import_functions_available": import_functions_available,
            "timestamp": datetime.now().isoformat(),
        }

        if issues:
            health_status["issues"] = issues

        status_code = 200 if is_healthy else 503

        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@expense_bp.route("/upload-receipt", methods=["POST"])
def upload_receipt():
    """
    Upload receipt file for an expense.

    Expected form data:
    - file: Receipt file (PDF, PNG, JPG, JPEG, GIF)
    - expense_id: ID of the expense this receipt belongs to (optional)

    Returns:
    - JSON response with file information and upload status
    """
    try:
        # Check if file is present in request
        if "file" not in request.files:
            return jsonify(
                {"error": "No file provided", "message": "Please select a receipt file"}
            ), 400

        file = request.files["file"]

        # Check if file was actually selected
        if file.filename == "":
            return jsonify(
                {"error": "No file selected", "message": "Please select a receipt file"}
            ), 400

        # Check file extension
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}
        if not allowed_file(file.filename, allowed_extensions):
            return jsonify(
                {
                    "error": "Invalid file type",
                    "message": f"Only {', '.join(allowed_extensions).upper()} files are allowed",
                }
            ), 400

        # Secure the filename
        filename = secure_filename(file.filename)

        # Add timestamp to prevent filename conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Save file to upload directory
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # Get expense ID if provided
        expense_id = request.form.get("expense_id")

        # Get file size
        file_size = os.path.getsize(file_path)

        logger.info(f"Successfully uploaded receipt: {unique_filename} ({file_size} bytes)")

        response_data = {
            "success": True,
            "message": "Receipt uploaded successfully",
            "file_info": {
                "original_filename": file.filename,
                "saved_filename": unique_filename,
                "file_path": file_path,
                "file_size": file_size,
                "file_type": ext.lower(),
            },
        }

        if expense_id:
            response_data["expense_id"] = expense_id

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error uploading receipt: {e}")
        return jsonify({"error": "Upload failed", "message": str(e)}), 500


@expense_bp.route("/match-receipt", methods=["POST"])
def match_receipt():
    """
    Calculate confidence score for expense-receipt match.

    Expected JSON data:
    - expense_data: Dictionary containing expense information
    - receipt_path: Path to the receipt file

    Returns:
    - JSON response with confidence score
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify(
                {
                    "error": "No data provided",
                    "message": "Please provide expense and receipt information",
                }
            ), 400

        expense_data = data.get("expense_data")
        receipt_data = data.get("receipt_data")

        # Calculate confidence score using existing receipt_matcher
        if receipt_match_score is None:
            # Fallback to mock score if function not available
            confidence_score = None
            logger.warning(
                "Using None as confidence score as receipt_match_score function is not available"
            )
        else:
            try:
                confidence_score = receipt_match_score(receipt_data, expense_data)
            except Exception as e:
                logger.warning(f"Error calling receipt_match_score: {e}")
                confidence_score = None

        logger.info(
            f"Calculated match confidence: {confidence_score} for expense {expense_data.get('id', 'unknown')}"
        )

        return jsonify(
            {
                "success": True,
                "confidence_score": confidence_score,
                "expense_id": expense_data.get("id"),
                "message": f"Match confidence calculated: {confidence_score}",
            }
        )

    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return jsonify({"error": "Match calculation failed", "message": str(e)}), 500


# Additional utility endpoints


@expense_bp.route("/list", methods=["GET"])
def list_expenses():
    """
    Get a list of all available expense data.
    This could be used to retrieve previously imported/uploaded expenses.
    """
    try:
        # This is a placeholder - in a real app, you'd fetch from a database
        # For now, return empty list or check for saved CSV files

        return jsonify(
            {"success": True, "message": "No stored expenses found", "data": [], "count": 0}
        )

    except Exception as e:
        logger.error(f"Error listing expenses: {e}")
        return jsonify({"error": "List failed", "message": str(e)}), 500


@expense_bp.route("/receipts", methods=["GET"])
def list_receipts():
    """
    Get a list of all uploaded receipt files.
    """
    try:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")

        if not os.path.exists(upload_folder):
            return jsonify(
                {"success": True, "message": "No receipts found", "receipts": [], "count": 0}
            )

        receipts = []
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}

        for filename in os.listdir(upload_folder):
            if allowed_file(filename, allowed_extensions):
                file_path = os.path.join(upload_folder, filename)
                file_size = os.path.getsize(file_path)
                file_ext = filename.rsplit(".", 1)[1].lower()

                receipts.append(
                    {
                        "filename": filename,
                        "file_path": file_path,
                        "file_size": file_size,
                        "file_type": file_ext,
                    }
                )

        return jsonify(
            {
                "success": True,
                "message": f"Found {len(receipts)} receipt files",
                "receipts": receipts,
                "count": len(receipts),
            }
        )

    except Exception as e:
        logger.error(f"Error listing receipts: {e}")
        return jsonify({"error": "List failed", "message": str(e)}), 500


@expense_bp.route("/delete", methods=["POST"])
def delete_expenses():
    """
    Delete specified expenses from the current working set.

    Expected JSON data:
    - expense_ids: Array of expense IDs to delete

    Returns:
    - JSON response indicating success/failure
    """
    try:
        # Get the request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request", "message": "No JSON data provided"}), 400

        expense_ids = data.get("expense_ids", [])
        if not expense_ids:
            return jsonify({"error": "Invalid request", "message": "No expense IDs provided"}), 400

        if not isinstance(expense_ids, list):
            return jsonify(
                {"error": "Invalid request", "message": "expense_ids must be an array"}
            ), 400

        # Convert IDs to strings for consistent comparison
        expense_ids = [str(id) for id in expense_ids]

        logger.info(f"Delete request for expense IDs: {expense_ids}")

        # Note: Since this application doesn't have persistent storage,
        # the actual deletion happens on the frontend by filtering the expenses array.
        # This endpoint serves as a validation and logging point.

        return jsonify(
            {
                "success": True,
                "message": f"Successfully processed deletion of {len(expense_ids)} expense(s)",
                "deleted_ids": expense_ids,
                "count": len(expense_ids),
            }
        )

    except Exception as e:
        logger.error(f"Error deleting expenses: {e}")
        return jsonify({"error": "Delete failed", "message": str(e)}), 500


@expense_bp.route("/create-from-receipts", methods=["POST"])
def create_expenses_from_receipts():
    """
    Create new expense entries from receipts with invoice details.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        receipts_with_invoice_details = data.get("receipts_with_invoice_details", [])
        current_expense_data = data.get("current_expense_data", [])

        if not receipts_with_invoice_details:
            return jsonify({"error": "No receipts with invoice details provided"}), 400

        logger.info(f"Creating expenses from {len(receipts_with_invoice_details)} receipts")

        # Find the highest existing expense ID to generate new sequential IDs
        max_id = max(expense["id"] for expense in current_expense_data if "id" in expense)

        # Start new IDs from the next number
        next_id = max_id + 1

        new_expenses = []
        processed_count = 0

        for receipt in receipts_with_invoice_details:
            try:
                invoice_details = receipt.get("invoiceDetails", {})

                if not invoice_details:
                    logger.warning(
                        f"Skipping receipt {receipt.get('name', 'unknown')} - no invoice details"
                    )
                    continue

                # Create new expense object
                new_expense = {
                    "id": next_id,
                    "Date": invoice_details.get("Date", ""),
                    "Amount": invoice_details.get("Amount"),
                    "Currency": invoice_details.get("Currency"),
                    "Additional description": f"Expense from {receipt.get('name')}",
                    "Expense category": invoice_details.get("Expense category"),
                    "Payment method": "Cash",
                    "receipts": [receipt],  # Attach the receipt to the expense
                }

                new_expenses.append(new_expense)
                next_id += 1
                processed_count += 1

                logger.info(
                    f"Created expense {new_expense['id']} from receipt {receipt.get('name')}"
                )

            except Exception as e:
                logger.error(f"Error processing receipt {receipt.get('name', 'unknown')}: {e}")
                continue

        if not new_expenses:
            return jsonify(
                {"error": "No valid expenses could be created from the provided receipts"}
            ), 400

        logger.info(f"Successfully created {len(new_expenses)} new expenses")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully created {len(new_expenses)} expenses from receipts",
                "new_expenses": new_expenses,
                "processed_receipt_count": processed_count,
            }
        )

    except Exception as e:
        logger.error(f"Error creating expenses from receipts: {e}")
        return jsonify({"error": "Failed to create expenses", "message": str(e)}), 500


@expense_bp.route("/bring-page-to-front", methods=["POST"])
def bring_page_to_front():
    """
    Bring the My Expense page to the front of the browser.

    Returns:
    - JSON response indicating success or failure
    """
    try:
        logger.info("Attempting to bring My Expense page to front")

        # Get the current expense page
        if not get_expense_page:
            logger.error("Expense page getter not available")
            return jsonify({"success": False, "error": "Browser control not available"}), 503

        page = get_expense_page()
        if page is None:
            logger.error("No active browser page found")
            return jsonify(
                {
                    "success": False,
                    "error": "No active browser session found. Please ensure the browser is connected.",
                }
            ), 503

        # Bring the page to front
        page.bring_to_front()
        logger.info("Successfully brought page to front")

        return jsonify({"success": True, "message": "Page brought to front successfully"})

    except Exception as e:
        logger.error(f"Error bringing page to front: {e}")
        return jsonify(
            {"success": False, "error": "Failed to bring page to front", "message": str(e)}
        ), 500
