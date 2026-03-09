"""
Flask web application for invoice and receipt management.

This application provides a web interface for:
- Importing expenses from external sources
- Matching receipts to expenses
- Exporting finalized expense data
"""

import logging
import os
import sys
import tempfile

from quart import Quart, g, jsonify, render_template
from quart_cors import cors

from config import (
    ALLOWED_EXTENSIONS,
    DEBUG_LOG_TARGET_FRONT_END,
    FLASK_DEBUG,
    FRONTEND_PORT,
    MAX_CONTENT_LENGTH,
    SECRET_KEY,
)

# Add the parent directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import resource utils and load environment
from resource_utils import get_resource_path, load_env_file

print("🔧 [Quart] Loading environment in front_end/app.py...")
env_loaded = load_env_file()
print(f"🔧 [Quart] Environment loaded: {env_loaded}")

# Import configuration

# Configure logging for frontend with separate log file
try:
    # Get absolute path for frontend log file relative to .env location
    frontend_log_path = get_resource_path(DEBUG_LOG_TARGET_FRONT_END.strip('"'))

    # Configure logging specifically for frontend modules
    frontend_logger = logging.getLogger("front_end")
    frontend_logger.setLevel(logging.DEBUG if FLASK_DEBUG else logging.INFO)

    # Only add handlers if they haven't been added yet
    if not frontend_logger.handlers:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        frontend_logger.addHandler(console_handler)

        # File handler for frontend
        file_handler = logging.FileHandler(str(frontend_log_path), mode="a")
        file_handler.setFormatter(formatter)
        frontend_logger.addHandler(file_handler)

        print(f"🔧 [Quart] Frontend logging configured to: {frontend_log_path}")

    # Don't propagate to root logger to avoid duplicate messages
    frontend_logger.propagate = False

except Exception as e:
    print(f"❌ [Quart] Failed to configure frontend logging: {e}")
    # Fallback to default logger
    frontend_logger = logging.getLogger(__name__)

# Use the frontend logger
logger = frontend_logger


def create_app():
    """Create and configure the Quart application."""
    print("🔧 [Quart] Creating Quart application...")
    logger.info("Creating Quart application")

    try:
        app = Quart(__name__)
        print("🔧 [Quart] Quart app instance created")

        # Configuration
        app.config["SECRET_KEY"] = SECRET_KEY
        print("🔧 [Quart] Secret key configured")

        # Use system temporary directory for both temp operations and uploads
        app.config["TEMP_FOLDER"] = tempfile.gettempdir()
        # Store uploaded receipts in a temporary directory that will be cleaned up
        app.config["UPLOAD_FOLDER"] = os.path.join(tempfile.gettempdir(), "ez-expense-uploads")
        app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
        print(f"🔧 [Quart] Upload folder: {app.config['UPLOAD_FOLDER']}")

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
        app.cleanup_old_uploads = cleanup_old_uploads  # type: ignore[attr-defined]

        # Allowed file extensions
        app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

        # Disable static file caching during development
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

        print("🔧 [Quart] Enabling CORS...")
        # Enable CORS for all routes
        app = cors(app)
        print("🔧 [Quart] CORS enabled")

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
        async def index():
            """Render the main application page."""
            import time

            return await render_template("index.html", cache_bust=int(time.time()))

        @app.route("/health")
        def health_check():
            """Health check endpoint."""
            return jsonify({"status": "healthy", "message": "EZ Expense app is running"})

        @app.route("/api/category-list")
        def get_category_list():
            """Get the list of valid expense categories."""
            try:
                from config import EXPENSE_CATEGORIES

                return jsonify({"categories": EXPENSE_CATEGORIES})
            except Exception as e:
                logger.error(f"Error reading category list: {e}")
                return jsonify({"error": "Failed to load category list"}), 500

        @app.route("/api/currency-list")
        def get_currency_list():
            """Get the list of valid currency codes."""
            try:
                from config import CURRENCY_CODES

                return jsonify({"currencies": CURRENCY_CODES})
            except Exception as e:
                logger.error(f"Error reading currency codes: {e}")
                return jsonify({"error": "Failed to load currency codes"}), 500

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
        print("🔧 [Quart] Registering blueprints...")
        try:
            from front_end.routes.expense_routes import expense_bp

            app.register_blueprint(expense_bp, url_prefix="/api/expenses")
            logger.info("Expense routes registered successfully")
            print("🔧 [Quart] Expense routes registered")
        except ImportError as e:
            logger.warning(f"Could not import expense routes: {e}")
            print(f"⚠️ [Quart] Could not import expense routes: {e}")

        try:
            from front_end.routes.receipt_routes import receipt_bp

            app.register_blueprint(receipt_bp, url_prefix="/api/receipts")
            logger.info("Receipt routes registered successfully")
            print("🔧 [Quart] Receipt routes registered")
        except ImportError as e:
            logger.warning(f"Could not import receipt routes: {e}")
            print(f"⚠️ [Quart] Could not import receipt routes: {e}")

        try:
            from front_end.routes.model_routes import model_bp

            app.register_blueprint(model_bp, url_prefix="/api/model")
            logger.info("Model routes registered successfully")
            print("🔧 [Quart] Model routes registered")
        except ImportError as e:
            logger.warning(f"Could not import model routes: {e}")
            print(f"⚠️ [Quart] Could not import model routes: {e}")

        # Add global error handlers for better exception visibility
        @app.errorhandler(500)
        def handle_internal_error(e):
            import traceback

            logger.error(f"Internal server error: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Return detailed error in debug mode, generic error in production
            if app.debug:
                return jsonify(
                    {
                        "error": "Internal server error",
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    }
                ), 500
            else:
                return jsonify(
                    {"error": "Internal server error", "message": "An unexpected error occurred"}
                ), 500

        @app.errorhandler(Exception)
        def handle_exception(e):
            import traceback

            logger.error(f"Unhandled exception: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Return detailed error in debug mode, generic error in production
            if app.debug:
                return jsonify(
                    {
                        "error": "Unhandled exception",
                        "message": str(e),
                        "exception_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    }
                ), 500
            else:
                return jsonify(
                    {"error": "An unexpected error occurred", "message": "Please try again later"}
                ), 500

        print("✅ [Quart] Application created successfully")
        logger.info("Quart application created successfully")
        return app

    except Exception as e:
        print(f"❌ [Quart] Error creating application: {e}")
        logger.error(f"Error creating application: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    app = create_app()

    logger.info(f"Starting EZ Expense Quart app on port {FRONTEND_PORT}")
    # Use hypercorn for Quart (ASGI) instead of Flask's built-in server
    import asyncio

    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = [f"0.0.0.0:{FRONTEND_PORT}"]
    config.debug = FLASK_DEBUG

    asyncio.run(hypercorn.asyncio.serve(app, config))
