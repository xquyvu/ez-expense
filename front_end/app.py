"""
Flask web application for invoice and receipt management.

This application provides a web interface for:
- Importing expenses from external sources
- Uploading and managing CSV expense data
- Matching receipts to expenses
- Exporting finalized expense data
"""

import logging
import os
import sys
import tempfile

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template
from flask_cors import CORS

load_dotenv()

# Add the parent directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import configuration
from config import ALLOWED_EXTENSIONS, FLASK_DEBUG, FRONTEND_PORT, MAX_CONTENT_LENGTH, SECRET_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = SECRET_KEY
    # Use system temporary directory for both temp operations and uploads
    app.config["TEMP_FOLDER"] = tempfile.gettempdir()
    # Store uploaded receipts in a temporary directory that will be cleaned up
    app.config["UPLOAD_FOLDER"] = os.path.join(tempfile.gettempdir(), "ez-expense-uploads")
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    logger.info(f"Using temporary upload folder: {app.config['UPLOAD_FOLDER']}")

    # Add cleanup function for old files (optional)
    def cleanup_old_uploads():
        """Clean up uploaded files older than 24 hours"""
        import time

        try:
            upload_folder = app.config["UPLOAD_FOLDER"]
            if os.path.exists(upload_folder):
                current_time = time.time()
                for filename in os.listdir(upload_folder):
                    filepath = os.path.join(upload_folder, filename)
                    if os.path.isfile(filepath):
                        # Delete files older than 24 hours (86400 seconds)
                        if current_time - os.path.getctime(filepath) > 86400:
                            os.remove(filepath)
                            logger.info(f"Cleaned up old upload: {filename}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old uploads: {e}")

    # Store cleanup function for potential use
    app.cleanup_old_uploads = cleanup_old_uploads

    # Allowed file extensions
    app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

    # Enable CORS for all routes
    CORS(app)

    # Cleanup handler for temporary files
    @app.teardown_appcontext
    def cleanup_temp_files(error):
        """Clean up any temporary files created during request processing."""
        if hasattr(g, "cleanup_functions"):
            for cleanup_func in g.cleanup_functions:
                try:
                    cleanup_func()
                except Exception as e:
                    logger.warning(f"Error during cleanup: {e}")

    @app.route("/")
    def index():
        """Render the main application page."""
        return render_template("index.html")

    @app.route("/health")
    def health_check():
        """Health check endpoint."""
        return jsonify({"status": "healthy", "message": "EZ Expense app is running"})

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Server Error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(413)
    def too_large(error):
        return jsonify({"error": "File too large"}), 413

    # Import and register route blueprints
    try:
        from routes.expense_routes import expense_bp

        app.register_blueprint(expense_bp, url_prefix="/api/expenses")
        logger.info("Expense routes registered successfully")
    except ImportError as e:
        logger.warning(f"Could not import expense routes: {e}")

    try:
        from routes.receipt_routes import receipt_bp

        app.register_blueprint(receipt_bp, url_prefix="/api/receipts")
        logger.info("Receipt routes registered successfully")
    except ImportError as e:
        logger.warning(f"Could not import receipt routes: {e}")

    return app


if __name__ == "__main__":
    app = create_app()

    logger.info(f"Starting EZ Expense Flask app on port {FRONTEND_PORT}")
    app.run(debug=FLASK_DEBUG, host="0.0.0.0", port=FRONTEND_PORT)
