#!/usr/bin/env python3
"""
Launcher script that:
1. Sets up browser (closes existing, reopens in debug mode)
2. Attaches Playwright to it
3. Runs the front end Flask app
4. Opens the front end page in the browser
"""

import os
import subprocess
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
PORT = os.getenv("PORT", 9222)
FRONTEND_PORT = os.getenv("FRONTEND_PORT", 5000)
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"


def start_flask_app():
    """Start the Flask application"""
    print("🚀 Starting Flask application...")
    flask_path = Path("front_end/app.py")

    if not flask_path.exists():
        print(f"❌ Flask app not found at {flask_path.absolute()}")
        return None

    try:
        process = subprocess.Popen(
            ["uv", "run", str(flask_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(f"✅ Flask application started on port {FRONTEND_PORT}")
        return process
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
        return None


def wait_for_flask_to_start(max_wait=30):
    """Wait for Flask app to be ready"""
    print("⏳ Waiting for Flask app to be ready...")
    import urllib.error
    import urllib.request

    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            with urllib.request.urlopen(FRONTEND_URL, timeout=2) as response:
                if response.status == 200:
                    print("✅ Flask app is ready")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)

    print("❌ Flask app did not start within the timeout period")
    return False


def open_frontend_in_browser():
    """Open the frontend page in the browser using Playwright"""
    print("🌍 Opening frontend page in browser...")
    try:
        from main import connect_to_browser

        playwright_instance, browser = connect_to_browser()

        # Create a new page for the frontend
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(FRONTEND_URL)
        page.bring_to_front()

        print(f"✅ Frontend page opened: {FRONTEND_URL}")
        print(f"📄 Page title: {page.title()}")

        # Don't stop the playwright instance to keep browser windows open
        print("🌐 Browser windows will remain open after script exits")
        print("💡 You can continue using the browser or run more automation scripts")

        # Return the playwright instance without stopping it
        return playwright_instance
    except Exception as e:
        print(f"❌ Failed to open frontend in browser: {e}")
        # Fallback to system default browser
        print("🔄 Falling back to system default browser...")
        try:
            webbrowser.open(FRONTEND_URL)
            print(f"✅ Opened {FRONTEND_URL} in default browser")
            return None  # No playwright instance in fallback case
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return None


def main():
    """Main launcher function"""
    print("🎯 EZ-Expense Frontend Launcher")
    print("=" * 50)

    # Setup browser session
    print("\n📍 Setting up browser session...")
    from main import setup_browser_session

    browser_process = setup_browser_session()
    if browser_process is None:
        print("❌ Browser setup cancelled or failed")
        return

    print(f"✅ Browser session started on port {PORT}")

    # Start Flask app
    print("\n📍 Starting Flask application...")
    flask_process = start_flask_app()
    if not flask_process:
        print("❌ Cannot start Flask application")
        return

    # Wait for Flask to be ready
    print("\n📍 Waiting for Flask to be ready...")
    if not wait_for_flask_to_start():
        print("❌ Flask app is not responding")
        flask_process.terminate()
        return

    # Open frontend in browser
    print("\n📍 Opening frontend in browser...")
    playwright_instance = open_frontend_in_browser()

    print("\n🎉 All services are running!")
    print("=" * 50)
    print("📋 Services Status:")
    print(f"   • Browser Session: ✅ Running (Port {PORT})")
    print(f"   • Flask App: ✅ Running (Port {FRONTEND_PORT})")
    print(f"   • Frontend Page: ✅ Open at {FRONTEND_URL}")
    if playwright_instance:
        print("   • Playwright: ✅ Connected")
    print()
    print("💡 Available Actions:")
    print("   • Your frontend is ready to use!")
    print("   • Run expense automation: python main.py")
    print("   • Browser and pages will stay open when this script exits")
    print()
    print("🛑 Press Ctrl+C to stop Flask app (browser will remain open)")

    try:
        # Monitor Flask process
        while True:
            if flask_process.poll() is not None:
                print("❌ Flask app has stopped unexpectedly")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping Flask app...")
        flask_process.terminate()
        try:
            flask_process.wait(timeout=5)
            print("✅ Flask app stopped")
        except subprocess.TimeoutExpired:
            flask_process.kill()
            print("⚠️ Flask app force-killed")

        print("🌐 Browser and pages remain open for continued use")
        print("👋 Goodbye!")


if __name__ == "__main__":
    main()
