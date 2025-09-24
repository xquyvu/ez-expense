"""
Centralized configuration module for EZ Expense application.

This module provides a single source of truth for configuration values
that need to be shared across different components of the application.
"""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debug and development settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# Port configurations
BROWSER_PORT = int(os.getenv("PORT", 9222))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 5001))

# Application URLs
EXPENSE_APP_URL = "myexpense.operations.dynamics.com"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

# CSV column names
EXPENSE_ID_COLUMN = "Created ID"
EXPENSE_LINE_NUMBER_COLUMN = "Line number"
RECEIPT_PATHS_COLUMN = "Receipt files"

# Flask configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {"csv", "pdf", "png", "jpg", "jpeg", "gif"}


def get_debug_info():
    """Get debug information for troubleshooting."""
    return {
        "DEBUG": DEBUG,
        "FLASK_DEBUG": FLASK_DEBUG,
        "BROWSER_PORT": BROWSER_PORT,
        "FRONTEND_PORT": FRONTEND_PORT,
        "FRONTEND_URL": FRONTEND_URL,
    }


def is_debug_mode():
    """Check if application is running in debug mode."""
    return DEBUG


def is_flask_debug_mode():
    """Check if Flask is running in debug mode."""
    return FLASK_DEBUG
