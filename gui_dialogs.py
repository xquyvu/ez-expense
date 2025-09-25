"""
Cross-platform GUI dialog utilities for EZ-Expense
"""

import platform
import subprocess
import sys
from typing import Optional


def show_browser_confirmation_dialog() -> bool:
    """
    Show a cross-platform confirmation dialog asking user if they want to restart their browser.

    Returns:
        bool: True if user confirmed, False if cancelled
    """
    system = platform.system()

    # Try platform-specific native dialogs first
    if system == "Darwin":
        result = _show_macos_dialog()
    elif system == "Windows":
        result = _show_windows_dialog()
    elif system == "Linux":
        result = _show_linux_dialog()
    else:
        result = None

    # Fall back to tkinter if native dialog failed
    if result is None:
        result = _show_tkinter_dialog()

    # Final fallback to console or auto-proceed
    if result is None:
        result = _show_console_fallback()

    return result


def _show_macos_dialog() -> Optional[bool]:
    """Show native macOS dialog using osascript"""
    try:
        applescript = """
        display dialog "EZ-Expense needs to restart your browser in debug mode.

This will close any existing browser windows and restart the browser.

Do you want to continue?" ¬
        with title "EZ-Expense Browser Setup" ¬
        with icon caution ¬
        buttons {"Cancel", "Continue"} ¬
        default button "Continue"
        """

        result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)

        # osascript returns 0 if user clicked "Continue", 1 if "Cancel"
        return result.returncode == 0

    except Exception:
        return None


def _show_windows_dialog() -> Optional[bool]:
    """Show native Windows dialog using ctypes"""
    try:
        import ctypes

        # MessageBox constants
        MB_YESNO = 0x4
        MB_ICONQUESTION = 0x20
        MB_DEFBUTTON2 = 0x100
        IDYES = 6

        result = ctypes.windll.user32.MessageBoxW(
            0,  # Parent window handle
            "EZ-Expense needs to restart your browser in debug mode.\n\n"
            "This will close any existing browser windows and restart the browser.\n\n"
            "Do you want to continue?",
            "EZ-Expense Browser Setup",
            MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2,
        )

        return result == IDYES

    except Exception:
        return None


def _show_linux_dialog() -> Optional[bool]:
    """Show Linux dialog using zenity, kdialog, or xmessage"""
    try:
        import shutil

        message = (
            "EZ-Expense needs to restart your browser in debug mode.\n\n"
            "This will close any existing browser windows and restart the browser.\n\n"
            "Do you want to continue?"
        )

        # Try zenity first (GNOME)
        if shutil.which("zenity"):
            result = subprocess.run(
                [
                    "zenity",
                    "--question",
                    "--title",
                    "EZ-Expense Browser Setup",
                    "--text",
                    message,
                    "--width",
                    "400",
                ],
                capture_output=True,
            )
            return result.returncode == 0

        # Try kdialog (KDE)
        elif shutil.which("kdialog"):
            result = subprocess.run(
                ["kdialog", "--yesno", message, "--title", "EZ-Expense Browser Setup"],
                capture_output=True,
            )
            return result.returncode == 0

        # Try xmessage as fallback
        elif shutil.which("xmessage"):
            result = subprocess.run(
                [
                    "xmessage",
                    "-center",
                    "-buttons",
                    "Continue:0,Cancel:1",
                    "-title",
                    "EZ-Expense Browser Setup",
                    message,
                ],
                capture_output=True,
            )
            return result.returncode == 0

        return None

    except Exception:
        return None


def _show_tkinter_dialog() -> Optional[bool]:
    """Show tkinter dialog (cross-platform fallback)"""
    try:
        import tkinter as tk
        from tkinter import messagebox

        # Create a root window but hide it
        root = tk.Tk()
        root.withdraw()  # Hide the main window

        # Show confirmation dialog
        result = messagebox.askyesno(
            "EZ-Expense Browser Setup",
            "EZ-Expense needs to restart your browser in debug mode.\n\n"
            "This will close any existing browser windows and restart the browser.\n\n"
            "Do you want to continue?",
            icon="question",
        )

        root.destroy()  # Clean up
        return result

    except ImportError:
        return None
    except Exception:
        return None


def _show_console_fallback() -> bool:
    """Final fallback: console prompt or auto-proceed"""
    try:
        if sys.stdin and sys.stdin.isatty():
            # We have a terminal, ask for user input
            response = (
                input("EZ-Expense needs to restart your browser. Continue? (Y/n): ").strip().lower()
            )
            return response in ["", "y", "yes"]
        else:
            # No terminal (GUI app), proceed automatically
            print("🔄 Running in GUI mode, automatically proceeding with browser restart...")
            return True
    except Exception:
        # If we can't determine anything, proceed automatically
        return True
