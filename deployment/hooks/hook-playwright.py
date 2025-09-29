# Runtime hook for Playwright
# This ensures Playwright uses the browser specified in .env when running as an executable

import os
import sys


def load_env_file():
    """Load .env file and return browser setting"""
    env_path = os.path.join(os.getcwd(), ".env")
    browser = None

    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("EZ_EXPENSE_BROWSER="):
                        browser = line.split("=", 1)[1].strip()
                        break
        except Exception as e:
            print(f"⚠️ Could not read .env file: {e}")

    return browser


def setup_playwright_env():
    """Setup Playwright environment for PyInstaller executable"""

    # Check if we're running from a PyInstaller bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # We're running from PyInstaller bundle

        # Load browser preference from .env
        browser = load_env_file()

        if browser:
            print(f"🎭 PyInstaller detected - using {browser} browser from .env")
        else:
            # Use system-installed browsers - no downloads needed
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

            # Skip any browser download attempts
            os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"

            print("✅ Playwright configured to use system browsers")
    else:
        # Running normally in development mode - no changes needed
        pass


# Run the setup
setup_playwright_env()
