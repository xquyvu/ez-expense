"""
Receipt-related API routes for the Flask application.
"""

import logging
import os
import sys
from datetime import datetime

from quart import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

# Add parent directory to path for importing the invoice extractor
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from expense_matcher import match_receipts_with_expenses
from invoice_extractor import extract_invoice_details

# Create blueprint
receipt_bp = Blueprint("receipts", __name__)
logger = logging.getLogger(__name__)


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@receipt_bp.route("/upload", methods=["POST"])
async def upload_receipt():
    """
    Upload a receipt file.

    Expected form data:
    - file: Receipt file (PDF, PNG, JPG, JPEG, GIF)
    - expense_id: ID of the expense this receipt belongs to (optional)

    Returns:
    - JSON response with file information and upload status
    """
    try:
        # Check if file is present in request
        files = await request.files
        if "file" not in files:
            return jsonify(
                {"error": "No file provided", "message": "Please select a receipt file"}
            ), 400

        file = files["file"]

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
        await file.save(file_path)

        # Get expense ID if provided
        form = await request.form
        expense_id = form.get("expense_id")

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


@receipt_bp.route("/list", methods=["GET"])
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


@receipt_bp.route("/download/<filename>", methods=["GET"])
def download_receipt(filename):
    """
    Download a specific receipt file.

    Args:
        filename: Name of the file to download

    Returns:
        File download response
    """
    try:
        # Secure the filename
        filename = secure_filename(filename)

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        file_path = os.path.join(upload_folder, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify(
                {"error": "File not found", "message": "Receipt file does not exist"}
            ), 404

        # Check if it's an allowed file type
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}
        if not allowed_file(filename, allowed_extensions):
            return jsonify(
                {"error": "Invalid file type", "message": "File is not a valid receipt"}
            ), 400

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading receipt: {e}")
        return jsonify({"error": "Download failed", "message": str(e)}), 500


@receipt_bp.route("/preview/<filename>", methods=["GET"])
def preview_receipt(filename):
    """
    Preview a specific receipt file (serve for display).

    Args:
        filename: Name of the file to preview

    Returns:
        File response for preview
    """
    try:
        # Secure the filename
        filename = secure_filename(filename)

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        file_path = os.path.join(upload_folder, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify(
                {"error": "File not found", "message": "Receipt file does not exist"}
            ), 404

        # Check if it's an allowed file type
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}
        if not allowed_file(filename, allowed_extensions):
            return jsonify(
                {"error": "Invalid file type", "message": "File is not a valid receipt"}
            ), 400

        return send_file(file_path)

    except Exception as e:
        logger.error(f"Error previewing receipt: {e}")
        return jsonify({"error": "Preview failed", "message": str(e)}), 500


@receipt_bp.route("/delete/<filename>", methods=["DELETE"])
def delete_receipt(filename):
    """
    Delete a specific receipt file.

    Args:
        filename: Name of the file to delete

    Returns:
        JSON response with deletion status
    """
    try:
        # Secure the filename
        filename = secure_filename(filename)

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        file_path = os.path.join(upload_folder, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify(
                {"error": "File not found", "message": "Receipt file does not exist"}
            ), 404

        # Check if it's an allowed file type
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}
        if not allowed_file(filename, allowed_extensions):
            return jsonify(
                {"error": "Invalid file type", "message": "File is not a valid receipt"}
            ), 400

        # Delete the file
        os.remove(file_path)

        logger.info(f"Successfully deleted receipt: {filename}")

        return jsonify(
            {
                "success": True,
                "message": f"Receipt '{filename}' deleted successfully",
                "filename": filename,
            }
        )

    except Exception as e:
        logger.error(f"Error deleting receipt: {e}")
        return jsonify({"error": "Delete failed", "message": str(e)}), 500


@receipt_bp.route("/upload-multiple", methods=["POST"])
async def upload_multiple_receipts():
    """
    Upload multiple receipt files for a single expense.

    Expected form data:
    - files: Multiple receipt files (PDF, PNG, JPG, JPEG, GIF)
    - expense_id: ID of the expense these receipts belong to (optional)

    Returns:
    - JSON response with file information and upload status for each file
    """
    try:
        # Check if files are present in request
        request_files = await request.files
        if "files" not in request_files:
            return jsonify(
                {"error": "No files provided", "message": "Please select receipt files"}
            ), 400

        files = request_files.getlist("files")

        # Check if any files were actually selected
        if not files or all(file.filename == "" for file in files):
            return jsonify(
                {"error": "No files selected", "message": "Please select receipt files"}
            ), 400

        # Get expense ID if provided
        form = await request.form
        expense_id = form.get("expense_id")

        # Process each file
        results = []
        success_count = 0
        error_count = 0
        allowed_extensions = {"pdf", "png", "jpg", "jpeg", "gif"}

        for file in files:
            try:
                # Skip empty files
                if file.filename == "":
                    continue

                # Check file extension
                if not allowed_file(file.filename, allowed_extensions):
                    results.append(
                        {
                            "filename": file.filename,
                            "success": False,
                            "error": "Invalid file type",
                            "message": f"Only {', '.join(allowed_extensions).upper()} files are allowed",
                        }
                    )
                    error_count += 1
                    continue

                # Secure the filename
                filename = secure_filename(file.filename)

                # Add timestamp to prevent filename conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[
                    :-3
                ]  # Include microseconds for uniqueness
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}{ext}"

                # Save file to upload directory
                upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, unique_filename)
                await file.save(file_path)

                # Get file size
                file_size = os.path.getsize(file_path)

                # Add to results
                file_result = {
                    "success": True,
                    "message": "File uploaded successfully",
                    "file_info": {
                        "original_filename": file.filename,
                        "saved_filename": unique_filename,
                        "file_path": file_path,
                        "file_size": file_size,
                        "file_type": ext.lower(),
                    },
                }

                if expense_id:
                    file_result["expense_id"] = expense_id

                results.append(file_result)
                success_count += 1

                logger.info(f"Successfully uploaded receipt: {unique_filename} ({file_size} bytes)")

            except Exception as file_error:
                logger.error(f"Error uploading file {file.filename}: {file_error}")
                results.append(
                    {
                        "filename": file.filename,
                        "success": False,
                        "error": "Upload failed",
                        "message": str(file_error),
                    }
                )
                error_count += 1

        # Prepare response
        response_data = {
            "success": success_count > 0,
            "message": f"Uploaded {success_count} files successfully, {error_count} failed",
            "results": results,
            "summary": {
                "total_files": len(files),
                "success_count": success_count,
                "error_count": error_count,
            },
        }

        if expense_id:
            response_data["expense_id"] = expense_id

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in bulk upload: {e}")
        return jsonify({"error": "Bulk upload failed", "message": str(e)}), 500


@receipt_bp.route("/move", methods=["POST"])
async def move_receipt():
    """
    Move a receipt from one expense to another and recalculate confidence score.

    Expected JSON data:
    - receipt_data: The receipt object to move (includes filename, name, etc.)
    - from_expense_id: ID of the expense the receipt is currently attached to
    - to_expense_id: ID of the expense to move the receipt to
    - to_expense_data: The target expense data for confidence calculation

    Returns:
    - JSON response indicating success/failure of the move operation with updated confidence
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Invalid request", "message": "Request must be JSON"}), 400

        data = await request.get_json()

        # Validate required fields
        if not all(key in data for key in ["receipt_data", "from_expense_id", "to_expense_id"]):
            return jsonify(
                {
                    "error": "Missing required fields",
                    "message": "receipt_data, from_expense_id, and to_expense_id are required",
                }
            ), 400

        receipt_data = data["receipt_data"]
        from_expense_id = data["from_expense_id"]
        to_expense_id = data["to_expense_id"]
        to_expense_data = data.get("to_expense_data")

        # Validate expense IDs
        if from_expense_id == to_expense_id:
            return jsonify(
                {
                    "error": "Invalid move",
                    "message": "Cannot move receipt to the same expense",
                }
            ), 400

        # Validate receipt data has some form of filename or file path
        filename = receipt_data.get("filename") or receipt_data.get("name")
        file_path = receipt_data.get("filePath")

        if not filename and not file_path:
            return jsonify(
                {
                    "error": "Invalid receipt data",
                    "message": "Receipt filename or filePath is required",
                }
            ), 400

        # For this implementation, we're primarily managing the frontend state
        # The actual file doesn't need to be moved since we're just changing which expense it's associated with
        # The filename and file_path remain the same, only the association changes

        # Determine the actual file path to check
        if file_path:
            # Use the full file path if available (for uploaded receipts)
            actual_file_path = file_path
        else:
            # Fall back to constructing path from filename (for legacy compatibility)
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
            actual_file_path = os.path.join(upload_folder, filename)

        # Only verify file existence if we have a proper file path
        # Skip verification for receipts that might not be physically stored yet
        if actual_file_path and os.path.isabs(actual_file_path):
            if not os.path.exists(actual_file_path):
                logger.warning(
                    f"Receipt file not found at {actual_file_path}, but proceeding with move operation"
                )
                # Don't fail the operation - just log a warning
                # This allows for moving receipts that exist in frontend state but may not have been properly uploaded

        # Calculate new match score for the target expense
        if to_expense_data:
            match_score = None
            try:
                # Import receipt_match_score function
                from expense_matcher import receipt_match_score

                match_score = receipt_match_score(receipt_data, to_expense_data)

                logger.info(
                    f"Calculated new match score: {match_score}% for moving receipt to expense {to_expense_id}"
                )

            except ImportError:
                logger.warning(
                    "receipt_match_score function not available, skipping match score calculation"
                )
            except Exception as e:
                logger.warning(f"Error calculating match score: {e}")

        logger.info(
            f"Moving receipt '{filename or file_path}' from expense {from_expense_id} to expense {to_expense_id}"
        )

        # Prepare updated receipt data
        updated_receipt_data = receipt_data.copy()
        if match_score is not None:
            updated_receipt_data["confidence"] = match_score * 100

        # Return success response with the updated receipt data
        response_data = {
            "success": True,
            "message": f"Receipt '{receipt_data.get('name', filename)}' moved successfully",
            "receipt_data": updated_receipt_data,
            "from_expense_id": from_expense_id,
            "to_expense_id": to_expense_id,
            "new_confidence_score": match_score * 100 if match_score is not None else None,
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error moving receipt: {e}")
        return jsonify({"error": "Move failed", "message": str(e)}), 500


@receipt_bp.route("/extract_invoice_details", methods=["POST"])
async def extract_invoice_details_endpoint():
    """
    Extract invoice details from an uploaded receipt.

    This endpoint accepts either a new receipt file upload (form data with 'file')

    Returns: JSON response with extracted invoice details
    """
    try:
        # Handle different input methods
        files = await request.files
        if files and "file" in files:
            file = files["file"]

            # Check if file was actually selected
            if not file.filename:
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

            # Save file temporarily for processing
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            name, ext = os.path.splitext(filename)
            unique_filename = f"{name}_temp_{timestamp}{ext}"

            upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            await file.save(file_path)

        else:
            return jsonify(
                {
                    "error": "No file provided",
                    "message": "Provide either a file upload or file reference",
                }
            ), 400

        # Extract invoice details using the file path - now works with async!
        invoice_details = await extract_invoice_details(file_path)

        logger.info(f"Successfully extracted invoice details for: {filename}")

        response_data = {
            "success": True,
            "message": "Invoice details extracted successfully",
            "invoice_details": invoice_details,
            "filename": filename,
            "file_path": file_path,
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error extracting invoice details: {e}")
        return jsonify({"error": "Extraction failed", "message": str(e)}), 500


@receipt_bp.route("/match_bulk_receipts", methods=["POST"])
async def match_bulk_receipts():
    """
    Match bulk receipts with expense data using the receipt_match_score function.

    Expected JSON data:
    - bulk_receipts: Array of bulk receipt objects with file paths and extracted invoice details
    - expense_data: Array of expense data objects from the expense table

    Returns:
    - JSON response with matching results and scores
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Invalid request", "message": "Request must be JSON"}), 400

        data = await request.get_json()

        # Validate required fields
        if not all(key in data for key in ["bulk_receipts", "expense_data"]):
            return jsonify(
                {
                    "error": "Missing required fields",
                    "message": "bulk_receipts and expense_data are required",
                }
            ), 400

        bulk_receipts = data["bulk_receipts"]
        expense_data = data["expense_data"]

        # Validate input types
        if not isinstance(bulk_receipts, list) or not isinstance(expense_data, list):
            return jsonify(
                {
                    "error": "Invalid data format",
                    "message": "bulk_receipts and expense_data must be arrays",
                }
            ), 400

        # Log the data being passed to the matching function
        logger.info(
            f"Processing {len(bulk_receipts)} bulk receipts and {len(expense_data)} expenses"
        )

        # Call the receipt_match_score function with the gathered data
        try:
            matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
                bulk_receipts, expense_data
            )

            num_matched_receipts = len(bulk_receipts) - len(unmatched_receipts)
            logger.info(f"Receipt matching completed with {num_matched_receipts} matches found")
        except Exception as e:
            logger.error(f"Error in receipt_match_score function: {e}")
            return jsonify(
                {"error": "Matching failed", "message": "Error during matching process"}
            ), 500

        # Prepare response
        response_data = {
            "success": True,
            "message": "Bulk receipt matching completed successfully",
            "unmatched_receipts": unmatched_receipts,
            "matched_expense_data": matched_expense_data,
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in bulk receipt matching: {e}")
        return jsonify({"error": "Matching failed", "message": str(e)}), 500
