#!/usr/bin/env python3
"""
App Launcher for EZ Expense macOS App Bundle

This script is the main executable for the .app bundle on macOS.
It opens Terminal.app and runs the console version of ez-expense.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path


def setup_logging():
    """Setup logging to help debug issues"""
    log_file = Path.home() / "ez-expense-launcher.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


def show_error_dialog(message, title="EZ Expense Error"):
    """Show error dialog using AppleScript"""
    applescript = f'''
    display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK" with icon stop
    '''
    subprocess.run(["osascript", "-e", applescript])


def get_console_executable_path():
    """Get path to the console executable that sits alongside the .app bundle"""
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle (.app)
        # The console executable should be in the same directory as the .app bundle
        app_bundle_parent = Path(sys.executable).parent.parent.parent.parent
        console_exe = app_bundle_parent / "ez-expense"

        # If not found next to .app, try the dist directory
        if not console_exe.exists():
            dist_dir = app_bundle_parent.parent / "dist"
            console_exe = dist_dir / "ez-expense"

        return console_exe
    else:
        # Running in development - look for the built executable
        return Path(__file__).parent / "dist" / "ez-expense"


def main():
    """Main launcher function"""
    logger = setup_logging()
    logger.info("Starting EZ Expense Launcher")

    try:
        # Find the console executable
        console_exe = get_console_executable_path()

        if not console_exe.exists():
            error_msg = f"Console executable not found at: {console_exe}"
            logger.error(error_msg)
            show_error_dialog(error_msg)
            return 1

        logger.info(f"Found console executable at: {console_exe}")

        # Make sure it's executable
        os.chmod(console_exe, 0o755)

        # Create AppleScript to open Terminal and run the app
        applescript = f"""
        tell application "Terminal"
            set newWindow to do script "cd '{console_exe.parent}' && ./{console_exe.name}"
            activate
            set custom title of newWindow to "EZ Expense"
            set background color of newWindow to {{0, 0, 0}}
            set normal text color of newWindow to {{65535, 65535, 65535}}
        end tell
        """

        logger.info("Opening Terminal with ez-expense")
        result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = f"Failed to open Terminal: {result.stderr}"
            logger.error(error_msg)
            show_error_dialog(error_msg)
            return 1

        logger.info("Successfully launched ez-expense in Terminal")
        return 0

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        show_error_dialog(error_msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
