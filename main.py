import signal
import sys
import time
from logging import getLogger

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from browser import BrowserProcess
from config import BROWSER_PORT, EXPENSE_APP_URL
from expense_importer import cleanup_playwright_connection, set_playwright_page
from front_end_launcher import open_frontend_in_browser, start_flask_app, wait_for_flask_to_start

logger = getLogger(__name__)

# Global variables for cleanup
_playwright_instance = None
_browser_process = None
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle graceful shutdown on signal reception"""
    global _shutdown_requested
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name} ({signum}). Initiating graceful shutdown...")
    print(f"\n🛑 Received {signal_name} signal. Shutting down gracefully...")

    _shutdown_requested = True

    # Clean up playwright instance
    if _playwright_instance:
        try:
            print("🔄 Stopping Playwright instance...")
            # Clear the global page reference before stopping
            set_playwright_page(None)
            _playwright_instance.stop()
            print("✅ Playwright instance stopped")
        except Exception as e:
            logger.error(f"Error stopping Playwright: {e}")
            print(f"⚠️  Error stopping Playwright: {e}")

    # Also clean up any Flask subprocess Playwright connections
    try:
        cleanup_playwright_connection()
    except Exception as e:
        logger.error(f"Error cleaning up Flask Playwright connection: {e}")
        print(f"⚠️  Error cleaning up Flask Playwright connection: {e}")

    # Clean up browser process
    if _browser_process:
        try:
            print("🔄 Closing browser process...")
            _browser_process.close_browser_if_running()
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


def connect_to_browser():
    """
    Connect to an existing browser session running in debug mode.
    Returns the sync_playwright instance and browser connection.
    Use this in a 'with' statement to maintain the connection.
    """
    global _playwright_instance

    _playwright_instance = sync_playwright().start()
    try:
        browser = _playwright_instance.chromium.connect_over_cdp(f"http://localhost:{BROWSER_PORT}")
        return _playwright_instance, browser
    except Exception:
        _playwright_instance.stop()
        _playwright_instance = None
        raise


def get_expense_page_from_browser(browser):
    """
    Get the expense management page from an existing browser connection.
    This function assumes the browser is already connected via connect_to_browser().
    """
    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else browser.new_context()

    for page in context.pages:
        if EXPENSE_APP_URL in page.url:
            page.bring_to_front()
            return page
    else:
        page = context.new_page()
        page.goto(f"https://{EXPENSE_APP_URL}")
        return page


def run_expense_automation():
    """Run the expense automation workflow"""
    global _shutdown_requested

    browser_process = setup_browser_session()

    if browser_process is None:
        logger.error("❌ Cannot proceed without browser session")
        return

    # Connect to the browser using our helper function
    _, browser = connect_to_browser()

    try:
        # Get the expense management page
        page = get_expense_page_from_browser(browser)

        # Set the Playwright page for use by the Flask app
        set_playwright_page(page)

        # Wait for the user input
        print("Press <Enter> after you have created a new expense report, or navigated")
        print("to the expense report you want to fill. Press <Ctrl+C> to exit at any")
        print("time.")

        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n🛑 User interrupted. Exiting gracefully...")
            return

        start_flask_app()
        wait_for_flask_to_start()
        open_frontend_in_browser()

        print("\n🚀 Automation is running. Press <Ctrl+C> to stop and exit.")
        while not _shutdown_requested:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received. Exiting gracefully...")
    except Exception as e:
        logger.error(f"An error occurred during automation: {e}")
        print(f"❌ An error occurred: {e}")
    finally:
        # Clear the global page reference when exiting
        set_playwright_page(None)
        if not _shutdown_requested:
            # Don't stop the playwright instance to keep browser windows open
            # Only print these messages if we're not shutting down
            print("🌐 Browser windows will remain open")
            print("💡 You can continue using the browser or run more automation scripts")


if __name__ == "__main__":
    try:
        run_expense_automation()
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        print(f"❌ Unexpected error: {e}")
    finally:
        # Ensure cleanup happens even if the signal handler wasn't called
        if _playwright_instance or _browser_process:
            signal_handler(signal.SIGTERM, None)

    # # Create new expenses and attach receipts to them
    # page.click('button[name="NewExpenseButton"]')
    # page.wait_for_load_state("networkidle", timeout=10000)

    # page.fill('input[name="CategoryInput"]', category)
    # page.fill('input[name="AmountInput"]', amount)
    # page.fill('input[name="CurrencyInput"]', currency)
    # page.fill('input[name="MerchantInputNoLookup"]', merchant)
    # page.fill('input[name="DateInput"]', date_to_fill.strftime("%-m/%-d/%Y"))
    # page.fill('textarea[name="NotesInput"]', description)

    # page.click('button[name="SaveButton"]')
    # page.wait_for_timeout(3000)

    # # Now we add receipt to the expense
    # receipt_file_paths = ["screenshot.png"]

    # for receipt_file_path in receipt_file_paths:
    #     page.click('a[name="EditReceipts"]')
    #     page.click('button[name="AddButton"]')

    #     # Upload receipt
    #     with page.expect_file_chooser() as file_chooser_info:
    #         page.click('button[name="UploadControlBrowseButton"]')

    #     file_chooser = file_chooser_info.value
    #     file_chooser.set_files(receipt_file_path)

    #     page.click('button[name="UploadControlUploadButton"]')
    #     page.click('button[name="OkButtonAddNewTabPage"]')
    #     page.wait_for_timeout(1000)
    #     page.get_by_text("Close", exact=True).click()

    #     page.get_by_text("Save and continue", exact=True).click()
