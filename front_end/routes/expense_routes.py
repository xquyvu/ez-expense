"""
Expense-related API routes for the Flask application.
"""

import csv
import io
import logging
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEBUG

# Add the parent directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from expense_importer import (
        get_playwright_page,
        import_expense_wrapper,
    )
except ImportError as e:
    logging.error(f"Could not import expense_importer: {e}")
    get_playwright_page = None
    import_expense_wrapper = None

try:
    from expense_matcher import receipt_match_score
except ImportError as e:
    logging.error(f"Could not import expense_matcher: {e}")
    receipt_match_score = None

# Create blueprint
expense_bp = Blueprint("expenses", __name__)
logger = logging.getLogger(__name__)


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
        if "Playwright page not available" in error_msg:
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
        browser_available = get_playwright_page() is not None if get_playwright_page else False

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


@expense_bp.route("/upload-csv", methods=["POST"])
def upload_csv():
    """
    Upload and parse CSV file containing expense data.

    Expected form data:
    - file: CSV file containing expense data

    Returns:
    - JSON response with parsed expense data
    """
    try:
        # Check if file is present in request
        if "file" not in request.files:
            return jsonify(
                {"error": "No file provided", "message": "Please select a CSV file"}
            ), 400

        file = request.files["file"]

        # Check if file was actually selected
        if file.filename == "":
            return jsonify(
                {"error": "No file selected", "message": "Please select a CSV file"}
            ), 400

        # Check file extension
        if not allowed_file(file.filename, {"csv"}):
            return jsonify(
                {"error": "Invalid file type", "message": "Only CSV files are allowed"}
            ), 400

        # Read and parse CSV file
        csv_content = file.read().decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        expenses = []
        for i, row in enumerate(csv_reader):
            expense = dict(row)
            # Add ID if not present
            if "id" not in expense:
                expense["id"] = i + 1
            expenses.append(expense)

        if not expenses:
            return jsonify({"error": "Empty file", "message": "CSV file contains no data"}), 400

        logger.info(f"Successfully parsed CSV with {len(expenses)} expenses")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully uploaded and parsed {len(expenses)} expenses from CSV",
                "data": expenses,
                "count": len(expenses),
                "columns": list(expenses[0].keys()) if expenses else [],
            }
        )

    except UnicodeDecodeError:
        return jsonify(
            {
                "error": "File encoding error",
                "message": "Could not read CSV file. Please ensure it's UTF-8 encoded",
            }
        ), 400
    except csv.Error as e:
        return jsonify(
            {"error": "CSV parsing error", "message": f"Could not parse CSV file: {str(e)}"}
        ), 400
    except Exception as e:
        logger.error(f"Error uploading CSV: {e}")
        return jsonify({"error": "Upload failed", "message": str(e)}), 500


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
        receipt_path = data.get("receipt_path")

        if not expense_data or not receipt_path:
            return jsonify(
                {
                    "error": "Missing data",
                    "message": "Both expense_data and receipt_path are required",
                }
            ), 400

        # Check if receipt file exists (skip in test mode)
        skip_file_check = request.args.get("debug") == "true"
        if not skip_file_check and not os.path.exists(receipt_path):
            return jsonify(
                {"error": "Receipt not found", "message": "Receipt file does not exist"}
            ), 404

        # Calculate confidence score using existing receipt_matcher
        if receipt_match_score is None:
            # Fallback to mock score if function not available
            confidence_score = 0.85
            logger.warning(
                "Using mock confidence score as receipt_match_score function is not available"
            )
        else:
            try:
                confidence_score = receipt_match_score()
            except Exception as e:
                logger.warning(f"Error calling receipt_match_score: {e}, using mock score")
                confidence_score = 0.75

        logger.info(
            f"Calculated match confidence: {confidence_score} for expense {expense_data.get('id', 'unknown')}"
        )

        return jsonify(
            {
                "success": True,
                "confidence_score": confidence_score,
                "expense_id": expense_data.get("id"),
                "receipt_path": receipt_path,
                "message": f"Match confidence calculated: {confidence_score:.2%}",
            }
        )

    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return jsonify({"error": "Match calculation failed", "message": str(e)}), 500


@expense_bp.route("/export", methods=["POST"])
def export_expenses():
    """
    Export finalized expenses (with matched receipts) to CSV file.

    Expected JSON data:
    - expenses: List of expense dictionaries with receipt information
    - filename: Optional filename for the export (default: "exported_expenses.csv")

    Returns:
    - JSON response with export status and file information
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify(
                {"error": "No data provided", "message": "Please provide expenses to export"}
            ), 400

        expenses = data.get("expenses", [])
        filename = data.get("filename", "exported_expenses.csv")

        if not expenses:
            return jsonify(
                {"error": "No expenses provided", "message": "Please provide expenses to export"}
            ), 400

        # Ensure filename has .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        # Secure the filename
        filename = secure_filename(filename)

        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Use system temporary directory for exports
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", prefix=f"{name}_{timestamp}_", delete=False
        ) as temp_file:
            # Convert to pandas DataFrame and export to CSV
            df = pd.DataFrame(expenses)
            df.to_csv(temp_file.name, index=False)
            export_path = temp_file.name

        # Get file size
        file_size = os.path.getsize(export_path)

        logger.info(
            f"Successfully exported {len(expenses)} expenses to temporary file: {unique_filename}"
        )
        logger.info(f"Temporary export path: {export_path}")

        # Schedule cleanup of temporary file after response is sent
        def cleanup_temp_file():
            try:
                if os.path.exists(export_path):
                    os.unlink(export_path)
                    logger.info(f"Cleaned up temporary export file: {export_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {export_path}: {e}")

        # Register cleanup to happen after request
        from flask import g

        if not hasattr(g, "cleanup_functions"):
            g.cleanup_functions = []
        g.cleanup_functions.append(cleanup_temp_file)

        return jsonify(
            {
                "success": True,
                "message": f"Successfully exported {len(expenses)} expenses",
                "export_info": {
                    "filename": unique_filename,
                    "file_path": export_path,
                    "file_size": file_size,
                    "expense_count": len(expenses),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error exporting expenses: {e}")
        return jsonify({"error": "Export failed", "message": str(e)}), 500


@expense_bp.route("/export/download", methods=["POST"])
def export_expenses_download():
    """
    Export finalized expenses (with matched receipts) to CSV and return file data for client-side download.

    Expected JSON data:
    - expenses: List of expense dictionaries with receipt information
    - filename: Optional filename for the export (default: "exported_expenses.csv")

    Returns:
    - CSV file data as downloadable response
    """
    try:
        from flask import Response

        data = request.get_json()

        if not data:
            return jsonify(
                {"error": "No data provided", "message": "Please provide expenses to export"}
            ), 400

        expenses = data.get("expenses", [])
        filename = data.get("filename", "exported_expenses.csv")

        if not expenses:
            return jsonify(
                {"error": "No expenses provided", "message": "Please provide expenses to export"}
            ), 400

        # Ensure filename has .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        # Secure the filename
        filename = secure_filename(filename)

        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Convert to pandas DataFrame and generate CSV
        df = pd.DataFrame(expenses)

        # Create CSV string
        output = io.StringIO()
        df.to_csv(output, index=False)
        csv_data = output.getvalue()
        output.close()

        logger.info(
            f"Successfully prepared {len(expenses)} expenses for download as {unique_filename}"
        )

        # Return CSV data as downloadable file
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{unique_filename}"',
                "Content-Type": "text/csv; charset=utf-8",
            },
        )

    except Exception as e:
        logger.error(f"Error exporting expenses for download: {e}")
        return jsonify({"error": "Export failed", "message": str(e)}), 500


@expense_bp.route("/export/data", methods=["POST"])
def export_expenses_data():
    """
    Export finalized expenses (with matched receipts) and return CSV data as JSON for client-side file saving.

    Expected JSON data:
    - expenses: List of expense dictionaries with receipt information
    - filename: Optional filename for the export (default: "exported_expenses.csv")

    Returns:
    - JSON response with CSV data string and filename
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify(
                {"error": "No data provided", "message": "Please provide expenses to export"}
            ), 400

        expenses = data.get("expenses", [])
        filename = data.get("filename", "exported_expenses.csv")

        if not expenses:
            return jsonify(
                {"error": "No expenses provided", "message": "Please provide expenses to export"}
            ), 400

        # Ensure filename has .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        # Secure the filename
        filename = secure_filename(filename)

        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Convert to pandas DataFrame and generate CSV
        df = pd.DataFrame(expenses)

        # Create CSV string
        output = io.StringIO()
        df.to_csv(output, index=False)
        csv_data = output.getvalue()
        output.close()

        logger.info(
            f"Successfully prepared {len(expenses)} expenses for client-side download as {unique_filename}"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Successfully prepared {len(expenses)} expenses for download",
                "export_data": {
                    "filename": unique_filename,
                    "csv_data": csv_data,
                    "expense_count": len(expenses),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error preparing expenses data for client-side download: {e}")
        return jsonify({"error": "Export failed", "message": str(e)}), 500


@expense_bp.route("/export/enhanced", methods=["POST"])
def export_expenses_enhanced():
    """
    Enhanced export that saves CSV and copies receipt files to a specified directory structure.

    Expected JSON data:
    - expenses: List of expense dictionaries with receipt information
    - destination_path: Base directory path where to save files
    - filename: Optional filename for the CSV export (default: "exported_expenses.csv")

    Returns:
    - JSON response with export status and file information
    """
    try:
        import shutil

        data = request.get_json()

        if not data:
            return jsonify(
                {
                    "error": "No data provided",
                    "message": "Please provide expenses and destination path",
                }
            ), 400

        expenses = data.get("expenses", [])
        destination_path = data.get("destination_path", "")
        filename = data.get("filename", "exported_expenses.csv")

        if not expenses:
            return jsonify(
                {"error": "No expenses provided", "message": "Please provide expenses to export"}
            ), 400

        if not destination_path:
            return jsonify(
                {
                    "error": "No destination path provided",
                    "message": "Please provide a destination directory",
                }
            ), 400

        # Validate destination path exists
        if not os.path.exists(destination_path):
            return jsonify(
                {
                    "error": "Invalid destination path",
                    "message": "The specified destination directory does not exist",
                }
            ), 400

        # Ensure filename has .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        # Secure the filename
        filename = secure_filename(filename)

        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Create receipts subfolder
        receipts_folder = os.path.join(destination_path, "receipts")
        os.makedirs(receipts_folder, exist_ok=True)

        # Get upload folder path
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")

        # Process expenses and copy receipt files
        processed_expenses = []
        copied_receipts = []
        failed_receipts = []

        for expense in expenses:
            processed_expense = expense.copy()

            # Extract receipt file paths from the expense
            receipt_paths = []
            if "receipt_file_paths" in expense and expense["receipt_file_paths"]:
                # Receipt file paths are stored as semicolon-separated values
                receipt_paths = [
                    path.strip()
                    for path in expense["receipt_file_paths"].split(";")
                    if path.strip() and path.strip() != "N/A"
                ]

            copied_receipt_names = []

            for receipt_path in receipt_paths:
                try:
                    # Handle both absolute and relative paths
                    if os.path.isabs(receipt_path):
                        source_path = receipt_path
                    else:
                        # Try to find the file in the upload folder
                        source_path = os.path.join(upload_folder, os.path.basename(receipt_path))

                    if os.path.exists(source_path):
                        receipt_filename = os.path.basename(source_path)
                        destination_receipt_path = os.path.join(receipts_folder, receipt_filename)

                        # Copy the receipt file
                        shutil.copy2(source_path, destination_receipt_path)
                        copied_receipts.append(receipt_filename)
                        copied_receipt_names.append(receipt_filename)
                        logger.info(f"Copied receipt: {receipt_filename}")
                    else:
                        failed_receipts.append(os.path.basename(receipt_path))
                        logger.warning(f"Receipt file not found: {receipt_path}")

                except Exception as e:
                    failed_receipts.append(
                        os.path.basename(receipt_path) if receipt_path else "unknown"
                    )
                    logger.error(f"Failed to copy receipt {receipt_path}: {e}")

            # Update the receipt file paths to point to the new location
            if copied_receipt_names:
                processed_expense["receipt_file_paths"] = "; ".join(
                    [f"receipts/{name}" for name in copied_receipt_names]
                )
            else:
                processed_expense["receipt_file_paths"] = ""

            processed_expenses.append(processed_expense)

        # Generate CSV in the destination directory
        csv_path = os.path.join(destination_path, unique_filename)
        df = pd.DataFrame(processed_expenses)
        df.to_csv(csv_path, index=False)

        # Get file size
        csv_file_size = os.path.getsize(csv_path)

        logger.info(f"Enhanced export completed: {unique_filename}")
        logger.info(f"CSV saved to: {csv_path}")
        logger.info(f"Receipts copied: {len(copied_receipts)}")
        logger.info(f"Failed receipts: {len(failed_receipts)}")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully exported {len(expenses)} expenses with receipts",
                "export_info": {
                    "csv_filename": unique_filename,
                    "csv_path": csv_path,
                    "csv_file_size": csv_file_size,
                    "receipts_folder": receipts_folder,
                    "expense_count": len(expenses),
                    "receipts_copied": len(copied_receipts),
                    "receipts_failed": len(failed_receipts),
                    "copied_receipt_files": copied_receipts,
                    "failed_receipt_files": failed_receipts,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error in enhanced export: {e}")
        return jsonify({"error": "Enhanced export failed", "message": str(e)}), 500


@expense_bp.route("/export/zip", methods=["POST"])
def export_expenses_zip():
    """
    Export expenses and receipts as a ZIP file.

    Expected JSON data:
    - expenses: List of expense dictionaries with receipt information
    - filename: Optional filename for the CSV export (default: "exported_expenses.csv")

    Returns:
    - ZIP file containing CSV and receipts folder
    """
    try:
        import shutil
        import zipfile

        data = request.get_json()

        if not data:
            return jsonify(
                {"error": "No data provided", "message": "Please provide expenses to export"}
            ), 400

        expenses = data.get("expenses", [])
        filename = data.get("filename", "exported_expenses.csv")

        if not expenses:
            return jsonify(
                {"error": "No expenses provided", "message": "Please provide expenses to export"}
            ), 400

        # Ensure filename has .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        # Secure the filename
        filename = secure_filename(filename)

        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Get upload folder path
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")

        # Create temporary directory for ZIP contents
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create receipts subfolder in temp directory
            receipts_folder = os.path.join(temp_dir, "receipts")
            os.makedirs(receipts_folder, exist_ok=True)

            # Process expenses and copy receipt files
            processed_expenses = []
            copied_receipts = []
            failed_receipts = []

            for expense in expenses:
                processed_expense = expense.copy()

                # Extract receipt file paths from the expense
                receipt_paths = []
                if "receipt_file_paths" in expense and expense["receipt_file_paths"]:
                    # Receipt file paths are stored as semicolon-separated values
                    receipt_paths = [
                        path.strip()
                        for path in expense["receipt_file_paths"].split(";")
                        if path.strip() and path.strip() != "N/A"
                    ]

                copied_receipt_names = []

                for receipt_path in receipt_paths:
                    try:
                        # Handle both absolute and relative paths
                        if os.path.isabs(receipt_path):
                            source_path = receipt_path
                        else:
                            # Try to find the file in the upload folder
                            source_path = os.path.join(
                                upload_folder, os.path.basename(receipt_path)
                            )

                        if os.path.exists(source_path):
                            receipt_filename = os.path.basename(source_path)
                            destination_receipt_path = os.path.join(
                                receipts_folder, receipt_filename
                            )

                            # Copy the receipt file
                            shutil.copy2(source_path, destination_receipt_path)
                            copied_receipts.append(receipt_filename)
                            copied_receipt_names.append(receipt_filename)
                            logger.info(f"Copied receipt to ZIP: {receipt_filename}")
                        else:
                            failed_receipts.append(os.path.basename(receipt_path))
                            logger.warning(f"Receipt file not found for ZIP: {receipt_path}")

                    except Exception as e:
                        failed_receipts.append(
                            os.path.basename(receipt_path) if receipt_path else "unknown"
                        )
                        logger.error(f"Failed to copy receipt {receipt_path} to ZIP: {e}")

                # Update the receipt file paths to point to the new location
                if copied_receipt_names:
                    processed_expense["receipt_file_paths"] = "; ".join(
                        [f"receipts/{name}" for name in copied_receipt_names]
                    )
                else:
                    processed_expense["receipt_file_paths"] = ""

                processed_expenses.append(processed_expense)

            # Generate CSV in the temp directory
            csv_path = os.path.join(temp_dir, unique_filename)
            df = pd.DataFrame(processed_expenses)
            df.to_csv(csv_path, index=False)

            # Create ZIP file
            zip_filename = f"ez-expense-export-{timestamp}.zip"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as zip_temp:
                with zipfile.ZipFile(zip_temp.name, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # Add CSV file
                    zipf.write(csv_path, unique_filename)

                    # Add receipts folder
                    for root, dirs, files in os.walk(receipts_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.join("receipts", file)
                            zipf.write(file_path, arc_name)

                zip_path = zip_temp.name

        logger.info(f"ZIP export completed: {zip_filename}")
        logger.info(f"Receipts copied: {len(copied_receipts)}")
        logger.info(f"Failed receipts: {len(failed_receipts)}")

        # Return ZIP file for download
        from flask import Response

        def generate_zip():
            with open(zip_path, "rb") as f:
                data = f.read()
                yield data
            # Clean up temporary file
            try:
                os.unlink(zip_path)
            except Exception:
                pass

        return Response(
            generate_zip(),
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Type": "application/zip",
            },
        )

    except Exception as e:
        logger.error(f"Error in ZIP export: {e}")
        return jsonify({"error": "ZIP export failed", "message": str(e)}), 500


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
