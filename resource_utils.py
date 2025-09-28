"""
Utilities for handling resources in both development and PyInstaller environments.
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_resource_path(relative_path: str = "") -> Path:
    """
    Get the absolute path to a resource file.

    In development: relative to the script file
    In PyInstaller: relative to the executable directory (with special handling for macOS app bundles)

    Args:
        relative_path: Path relative to the application root

    Returns:
        Absolute path to the resource
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        # For .env and other user files, we want them relative to the executable, not the temp bundle
        if hasattr(sys, "executable") and sys.executable:
            # Get directory containing the executable
            base_path = Path(sys.executable).parent

            # Special handling for macOS app bundles
            # If the executable is inside .app/Contents/MacOS/,
            # look for .env files in the parent directory of the .app bundle
            if base_path.name == "MacOS" and base_path.parent.name == "Contents":
                app_bundle = base_path.parent.parent  # Go up to the .app directory
                if app_bundle.suffix == ".app":
                    # Look in the directory containing the .app bundle
                    base_path = app_bundle.parent
        else:
            # Fallback to current working directory
            base_path = Path.cwd()
    else:
        # Running in development
        # Get the directory containing the main script
        if hasattr(sys.modules["__main__"], "__file__"):
            base_path = Path(sys.modules["__main__"].__file__).parent
        else:
            base_path = Path.cwd()

    if relative_path:
        return base_path / relative_path
    else:
        return base_path


def load_env_file() -> bool:
    """
    Load environment variables from .env file located relative to the executable/script.

    Returns:
        True if .env file was loaded successfully, False otherwise
    """
    logger = logging.getLogger(__name__)

    # Debug info
    print(f"🔧 Debug: sys.frozen = {getattr(sys, 'frozen', False)}")
    print(f"🔧 Debug: sys.executable = {sys.executable}")
    print(f"🔧 Debug: current working dir = {Path.cwd()}")

    env_path = get_resource_path(".env")
    print(f"🔧 Debug: calculated .env path = {env_path}")

    # Try to load from the calculated path
    if env_path.exists():
        result = load_dotenv(env_path)
        if result:
            print(f"✅ Loaded .env from: {env_path}")
            logger.info(f"Successfully loaded .env from: {env_path}")
        else:
            print(f"⚠️  Failed to load .env from: {env_path}")
            logger.warning(f"Failed to load .env from: {env_path}")
        return result
    else:
        # Fallback to default behavior (current directory)
        print(f"⚠️  .env not found at: {env_path}, trying current directory...")
        logger.warning(f".env not found at: {env_path}, trying current directory...")
        result = load_dotenv()
        if result:
            print("✅ Loaded .env from current directory")
            logger.info("Loaded .env from current directory")
        else:
            print("❌ No .env file found")
            logger.error("No .env file found in any location")
        return result
