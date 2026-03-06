import logging
import os
import signal
import sys
import time
import webbrowser
from logging import getLogger
from threading import Timer

try:
    import playwright_manager
    from browser import BrowserProcess
    from config import (
        BROWSER,
        BROWSER_PORT,
        DEBUG_LOG_TARGET,
        EXPENSE_APP_URL,
        FRONTEND_PORT,
        IMPORT_EXPENSE_MOCK,
    )
    from resource_utils import get_resource_path, load_env_file
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

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


# Load environment variables from the correct location
print("🔧 Loading environment variables...")
env_loaded = load_env_file()
print(f"🔧 Environment loaded: {env_loaded}")

# Configure logging for better debugging

try:
    # Get absolute path for log file relative to .env location
    log_path = get_resource_path(DEBUG_LOG_TARGET.strip('"'))

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    print(f"🔧 Logging configured to: {log_path}")
except Exception as e:
    print(f"❌ Failed to configure logging: {e}")
    # Fallback to console only
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

# Silence verbose OpenAI base client debug logs (dumps full request payloads including base64 images)
logging.getLogger("openai._base_client").setLevel(logging.INFO)

print(f"🔧 Import Expense Mock: {IMPORT_EXPENSE_MOCK}")
print(f"🔧 Browser: {BROWSER}")

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Process termination (e.g., debugger stop)
print("🔧 Signal handlers registered")


def setup_browser_session():
    """Set up the browser session and return the page object"""
    global _browser_process

    print("🔧 Setting up browser session...")
    logger.info("Setting up browser session")

    try:
        browser_name = BROWSER
        print(f"🔧 Using browser: {browser_name}")
        logger.info(f"Using browser: {browser_name}")

        _browser_process = BrowserProcess(browser_name=browser_name, port=BROWSER_PORT)
        print("🔧 BrowserProcess created")

        # If the debug port is already active, skip closing/restarting
        if _browser_process.is_debug_port_active():
            print(f"✅ Browser already running in debug mode on port {BROWSER_PORT}, reusing.")
            logger.info(f"Browser already running in debug mode on port {BROWSER_PORT}")
        else:
            # Try to close existing browser gracefully
            print("🔧 Closing existing browser instances...")
            if not _browser_process.close_browser_if_running():
                logger.error("Browser setup cancelled by user")
                print("❌ Browser setup cancelled by user")
                return None

            print("🔧 Starting browser in debug mode...")
            _browser_process.start_browser_debug_mode()
            print("🔧 Browser started, waiting 2 seconds...")
            time.sleep(2)  # Give Browser time to start

        print("🔧 Browser setup complete")

        return _browser_process
    except Exception as e:
        logger.error(f"Error in setup_browser_session: {e}")
        print(f"❌ Error in setup_browser_session: {e}")
        import traceback

        traceback.print_exc()
        return None


async def connect_to_browser():
    """
    Connect to an existing browser session running in debug mode.
    Returns the browser connection.
    """
    print("🔧 Connecting to browser...")
    logger.info("Connecting to browser")
    try:
        print("🔧 Starting Playwright...")
        await playwright_manager.start_playwright()
        print("🔧 Playwright started, connecting to browser...")
        browser = await playwright_manager.connect_to_browser()
        print("🔧 Connected to browser successfully")
        logger.info("Connected to browser successfully")
        return browser
    except Exception as e:
        logger.error(f"Failed to connect to browser: {e}")
        print(f"❌ Failed to connect to browser: {e}")
        import traceback

        traceback.print_exc()
        return None


async def get_expense_page_from_browser(browser):
    """
    Get the expense management page from an existing browser connection.
    This function assumes the browser is already connected via connect_to_browser().
    """
    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = await context.new_page()
    # Wait a moment for the page to be fully created
    await page.wait_for_load_state("domcontentloaded")
    await page.goto(f"https://{EXPENSE_APP_URL}")
    return page


async def start_quart_app():
    """Start the Quart web application"""
    print("🔧 Initializing Quart application...")
    logger.info("Starting Quart application")

    try:
        from front_end.app import create_app

        app = create_app()
        print(f"🚀 Starting Quart application on port {FRONTEND_PORT}...")
        print(f"🌐 Access the web interface at http://127.0.0.1:{FRONTEND_PORT}")
        logger.info(f"Quart app starting on port {FRONTEND_PORT}")

        def _open_browser():
            print("🔧 Opening browser to web interface...")
            webbrowser.open_new(f"http://127.0.0.1:{FRONTEND_PORT}")

            # Show notification that the app is ready
            try:
                import subprocess

                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'display notification "Web interface is now available at http://127.0.0.1:{FRONTEND_PORT}" with title "EZ-Expense Ready!" sound name "default"',
                    ],
                    check=False,
                    capture_output=True,
                )
            except Exception:
                pass  # Silently ignore notification failures

        Timer(1, _open_browser).start()

        # Use hypercorn (Quart's recommended ASGI server) instead of Flask's built-in server
        import hypercorn.asyncio
        from hypercorn import Config

        config = Config()
        config.bind = [f"0.0.0.0:{FRONTEND_PORT}"]
        config.use_reloader = False

        print("🔧 Starting hypercorn server...")
        logger.info("Starting hypercorn server")

        # Run the async server directly - we're already in async context
        await hypercorn.asyncio.serve(app, config)

    except Exception as e:
        logger.error(f"Failed to start Quart app: {e}")
        print(f"❌ Failed to start Quart app: {e}")
        import traceback

        traceback.print_exc()
        raise


async def run_expense_automation():
    """Run the expense automation workflow with async architecture"""
    global _shutdown_requested

    print("🚀 Starting EZ-Expense application...")
    logger.info("Starting EZ-Expense application")
    print(f"🔧 Using ports - Browser: {BROWSER_PORT}, Frontend: {FRONTEND_PORT}")

    try:
        # Setup browser session
        print("🔧 Step 1: Setting up browser session...")
        browser_process = setup_browser_session()
        if browser_process is None:
            logger.error("❌ Cannot proceed without browser session")
            print("❌ Cannot proceed without browser session")
            return

        print("🔧 Step 2: Connecting to browser...")
        # Connect to the browser
        browser = await connect_to_browser()
        if not browser:
            print("❌ Failed to connect to browser")
            logger.error("Failed to connect to browser")
            return

        try:
            print("🔧 Step 3: Getting expense page...")
            # Get the expense management page
            page = await get_expense_page_from_browser(browser)

            # Set the page in the playwright manager (Quart routes will use this)
            playwright_manager.set_current_page(page)

            print("\n✅ Browser setup complete. Starting Quart web interface...")
            logger.info("Browser setup complete, starting Quart web interface")

            # Start Quart in async context
            await start_quart_app()

        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received. Exiting gracefully...")
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"An error occurred during automation: {e}")
            print(f"❌ An error occurred: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Clear the page reference when exiting
            playwright_manager.set_current_page(None)
            if not _shutdown_requested:
                print("🌐 Browser windows will remain open")
                print("💡 You can continue using the browser or run more automation scripts")

    except Exception as e:
        logger.error(f"Critical error in run_expense_automation: {e}")
        print(f"❌ Critical error in run_expense_automation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 EZ-Expense starting...")
    print(f"🔧 Python executable: {sys.executable}")
    print(f"🔧 Current working directory: {os.getcwd()}")
    print(f"🔧 Script path: {__file__ if '__file__' in globals() else 'Unknown'}")

    # Show a macOS notification that the app is starting
    try:
        import subprocess

        subprocess.run(
            [
                "osascript",
                "-e",
                'display notification "EZ-Expense is starting up..." with title "EZ-Expense" sound name "default"',
            ],
            check=False,
            capture_output=True,
        )
    except Exception:
        pass  # Silently ignore notification failures

    # Log startup information
    logger.info("EZ-Expense application starting...")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script path: {__file__ if '__file__' in globals() else 'Unknown'}")
    logger.info(f"Log file: {log_path}")

    try:
        import asyncio

        print("🔧 Starting asyncio event loop...")
        logger.info("Starting asyncio event loop...")
        asyncio.run(run_expense_automation())
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user")
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("🔧 Cleanup phase...")
        # Ensure cleanup happens even if the signal handler wasn't called
        if playwright_manager.is_playwright_running() or _browser_process:
            print("🔧 Performing final cleanup...")
            signal_handler(signal.SIGTERM, None)
