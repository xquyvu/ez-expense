"""
Centralized Playwright instance management for EZ Expense application.

This module provides a single source of truth for Playwright instances
and browser connections across the application.
"""

import logging

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from config import BROWSER_PORT

logger = logging.getLogger(__name__)

# Global variables for Playwright management
_playwright_instance: Playwright | None = None
_browser_connection: Browser | None = None
_current_page: Page | None = None


def start_playwright() -> Playwright:
    """
    Start a new Playwright instance.

    Returns:
        Playwright: The started Playwright instance

    Raises:
        RuntimeError: If Playwright is already running
    """
    global _playwright_instance

    if _playwright_instance is not None:
        raise RuntimeError("Playwright instance is already running. Call stop_playwright() first.")

    logger.info("Starting Playwright instance...")
    _playwright_instance = sync_playwright().start()
    logger.info("Playwright instance started successfully")

    return _playwright_instance


def connect_to_browser() -> Browser:
    """
    Connect to a browser running in debug mode.

    Returns:
        Browser: The browser connection

    Raises:
        RuntimeError: If no Playwright instance is running
        ConnectionError: If unable to connect to browser
    """
    global _browser_connection

    if _playwright_instance is None:
        raise RuntimeError("No Playwright instance available. Call start_playwright() first.")

    if _browser_connection is not None:
        logger.warning("Browser connection already exists. Returning existing connection.")
        return _browser_connection

    try:
        logger.info(f"Connecting to browser on port {BROWSER_PORT}...")
        _browser_connection = _playwright_instance.chromium.connect_over_cdp(
            f"http://localhost:{BROWSER_PORT}"
        )
        logger.info("Successfully connected to browser")
        return _browser_connection
    except Exception as e:
        logger.error(f"Failed to connect to browser: {e}")
        raise ConnectionError(f"Unable to connect to browser on port {BROWSER_PORT}: {e}")


def set_current_page(page: Page | None) -> None:
    """
    Set the current active page.

    Args:
        page: The page to set as current, or None to clear
    """
    global _current_page
    _current_page = page
    if page:
        logger.info("Current page set successfully")
    else:
        logger.info("Current page cleared")


def get_current_page() -> Page | None:
    """
    Get the current active page.

    Returns:
        Page or None: The current page instance
    """
    return _current_page


def get_playwright_instance() -> Playwright | None:
    """
    Get the current Playwright instance.

    Returns:
        Playwright or None: The current Playwright instance
    """
    return _playwright_instance


def get_browser_connection() -> Browser | None:
    """
    Get the current browser connection.

    Returns:
        Browser or None: The current browser connection
    """
    return _browser_connection


def cleanup_page() -> None:
    """Clean up the current page reference."""
    global _current_page
    if _current_page:
        logger.info("Clearing current page reference...")
        _current_page = None


def cleanup_browser() -> None:
    """Clean up the browser connection."""
    global _browser_connection
    if _browser_connection:
        try:
            logger.info("Closing browser connection...")
            _browser_connection.close()
            logger.info("Browser connection closed successfully")
        except Exception as e:
            logger.warning(f"Error closing browser connection: {e}")
        finally:
            _browser_connection = None


def stop_playwright() -> None:
    """
    Stop the Playwright instance and clean up all resources.
    """
    global _playwright_instance

    # Clean up page reference first
    cleanup_page()

    # Clean up browser connection
    cleanup_browser()

    # Stop Playwright instance
    if _playwright_instance:
        try:
            logger.info("Stopping Playwright instance...")
            _playwright_instance.stop()
            logger.info("Playwright instance stopped successfully")
        except Exception as e:
            logger.warning(f"Error stopping Playwright instance: {e}")
        finally:
            _playwright_instance = None
    else:
        logger.info("No Playwright instance to stop")


def is_playwright_running() -> bool:
    """
    Check if Playwright instance is currently running.

    Returns:
        bool: True if Playwright is running, False otherwise
    """
    return _playwright_instance is not None


def is_browser_connected() -> bool:
    """
    Check if browser is currently connected.

    Returns:
        bool: True if browser is connected, False otherwise
    """
    return _browser_connection is not None


def get_status() -> dict:
    """
    Get the current status of Playwright manager.

    Returns:
        dict: Status information
    """
    return {
        "playwright_running": is_playwright_running(),
        "browser_connected": is_browser_connected(),
        "page_available": _current_page is not None,
        "browser_port": BROWSER_PORT,
    }
