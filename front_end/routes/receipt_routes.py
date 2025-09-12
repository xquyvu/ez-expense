"""
Receipt-related API routes for the Flask application.
"""

import logging
import os
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

# Create blueprint
receipt_bp = Blueprint("receipts", __name__)
logger = logging.getLogger(__name__)


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@receipt_bp.route("/upload", methods=["POST"])
def upload_receipt():
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
def upload_multiple_receipts():
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
        if "files" not in request.files:
            return jsonify(
                {"error": "No files provided", "message": "Please select receipt files"}
            ), 400

        files = request.files.getlist("files")

        # Check if any files were actually selected
        if not files or all(file.filename == "" for file in files):
            return jsonify(
                {"error": "No files selected", "message": "Please select receipt files"}
            ), 400

        # Get expense ID if provided
        expense_id = request.form.get("expense_id")

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
                file.save(file_path)

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
