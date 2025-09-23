import signal
import sys
import time
import webbrowser
from logging import getLogger
from threading import Timer

from dotenv import load_dotenv

import playwright_manager
from browser import BrowserProcess
from config import BROWSER_PORT, EXPENSE_APP_URL

logger = getLogger(__name__)

# Global variables for cleanup
_browser_process = None
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle graceful shutdown on signal reception"""
    global _shutdown_requested
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name} ({signum}). Initiating graceful shutdown...")
    print(f"\n🛑 Received {signal_name} signal. Shutting down gracefully...")

    _shutdown_requested = True

    # Clean up playwright instance using the manager
    if playwright_manager.is_playwright_running():
        try:
            print("🔄 Stopping Playwright instance...")
            # Clear the page reference before stopping
            playwright_manager.set_current_page(None)
            # For signal handler, we'll do sync cleanup only
            print("✅ Playwright instance cleanup initiated")
        except Exception as e:
            logger.error(f"Error stopping Playwright: {e}")
            print(f"⚠️  Error stopping Playwright: {e}")

    # Clean up browser process
    if _browser_process:
        try:
            print("🔄 Closing browser process...")
            _browser_process.close_browser_gracefully()
            print("✅ Browser process closed")
        except Exception as e:
            logger.error(f"Error closing browser process: {e}")
            print(f"⚠️  Error closing browser process: {e}")

    print("👋 Shutdown complete. Exiting...")
    sys.exit(0)


load_dotenv()

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Process termination (e.g., debugger stop)


def setup_browser_session():
    """Set up the browser session and return the page object"""
    global _browser_process

    _browser_process = BrowserProcess(browser_name="edge", port=BROWSER_PORT)

    # Try to close existing browser gracefully
    if not _browser_process.close_browser_if_running():
        logger.error("Browser setup cancelled by user")
        return None

    _browser_process.start_browser_debug_mode()
    time.sleep(2)  # Give Edge time to start

    return _browser_process


async def connect_to_browser():
    """
    Connect to an existing browser session running in debug mode.
    Returns the browser connection.
    """
    try:
        await playwright_manager.start_playwright()
        browser = await playwright_manager.connect_to_browser()
        return browser
    except Exception as e:
        logger.error(f"Failed to connect to browser: {e}")
        return None


async def get_expense_page_from_browser(browser):
    """
    Get the expense management page from an existing browser connection.
    This function assumes the browser is already connected via connect_to_browser().
    """
    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else await browser.new_context()

    page = await context.new_page()
    await page.goto(f"https://{EXPENSE_APP_URL}")
    return page


async def start_quart_app():
    """Start Quart app with hypercorn (supports async natively)"""
    try:
        from front_end.app import create_app

        app = create_app()
        print("🚀 Starting Quart application on port 5001...")
        print("🌐 Access the web interface at http://127.0.0.1:5001")

        def _open_browser():
            webbrowser.open_new("http://127.0.0.1:5001")

        Timer(1, _open_browser).start()

        # Use hypercorn (Quart's recommended ASGI server) instead of Flask's built-in server
        import hypercorn.asyncio
        from hypercorn import Config

        config = Config()
        config.bind = ["0.0.0.0:5001"]
        config.use_reloader = False

        # Run the async server directly - we're already in async context
        await hypercorn.asyncio.serve(app, config)

    except Exception as e:
        logger.error(f"Failed to start Quart app: {e}")
        print(f"❌ Failed to start Quart app: {e}")


async def run_expense_automation():
    """Run the expense automation workflow with async architecture"""
    global _shutdown_requested

    # Setup browser session
    browser_process = setup_browser_session()
    if browser_process is None:
        logger.error("❌ Cannot proceed without browser session")
        return

    # Connect to the browser
    browser = await connect_to_browser()
    if not browser:
        print("❌ Failed to connect to browser")
        return

    try:
        # Get the expense management page
        page = await get_expense_page_from_browser(browser)

        # Set the page in the playwright manager (Quart routes will use this)
        playwright_manager.set_current_page(page)

        print("\n✅ Browser setup complete. Starting Quart web interface...")

        # Start Quart in async context
        await start_quart_app()

    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received. Exiting gracefully...")
    except Exception as e:
        logger.error(f"An error occurred during automation: {e}")
        print(f"❌ An error occurred: {e}")
    finally:
        # Clear the page reference when exiting
        playwright_manager.set_current_page(None)
        if not _shutdown_requested:
            print("🌐 Browser windows will remain open")
            print("💡 You can continue using the browser or run more automation scripts")


if __name__ == "__main__":
    try:
        import asyncio

        asyncio.run(run_expense_automation())
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        print(f"❌ Unexpected error: {e}")
    finally:
        # Ensure cleanup happens even if the signal handler wasn't called
        if playwright_manager.is_playwright_running() or _browser_process:
            signal_handler(signal.SIGTERM, None)
