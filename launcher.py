#!/usr/bin/env python3
"""
Launcher script to run both the browser automation session and Flask app concurrently.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from main import setup_browser_session

load_dotenv()

PORT = os.getenv("PORT", 9222)
FRONTEND_PORT = os.getenv("FRONTEND_PORT", 5001)


def start_browser_session():
    """Start the browser session for Playwright automation"""
    print("🌐 Starting browser session...")
    try:
        setup_browser_session()
        print("✅ Browser session started successfully!")
        print(f"🔗 Browser is now available at port {PORT} for Playwright automation")
        return True
    except Exception as e:
        print(f"❌ Failed to start browser session: {e}")
        return False


def start_flask_app():
    """Start the Flask application"""
    print("🚀 Starting Flask application...")
    flask_path = Path("front_end/app.py")

    if not flask_path.exists():
        print(f"❌ Flask app not found at {flask_path.absolute()}")
        return None

    try:
        # Use uv to run the Flask app
        process = subprocess.Popen(
            ["uv", "run", str(flask_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("✅ Flask application started!")
        print(f"🌍 Flask app should be available at http://localhost:{FRONTEND_PORT}")
        return process
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
        return None


def main():
    """Main launcher function"""
    print("🎯 EZ-Expense Launcher")
    print("=" * 50)

    # Start browser session first
    if not start_browser_session():
        print("❌ Cannot continue without browser session")
        sys.exit(1)

    print()

    # Start Flask app
    flask_process = start_flask_app()
    if not flask_process:
        print("❌ Cannot start Flask application")
        sys.exit(1)

    print()
    print("🎉 Both services are now running!")
    print()
    print("📋 Services Status:")
    print(f"   • Browser Session: ✅ Running (Port {PORT})")
    print(f"   • Flask App: ✅ Running (Port {FRONTEND_PORT})")
    print()
    print("💡 Usage:")
    print(f"   • Access your web app at: http://localhost:{FRONTEND_PORT}")
    print("   • Run Playwright automation with: python main.py")
    print(f"   • Browser is ready for Playwright connection on port {PORT}")
    print()
    print("🛑 Press Ctrl+C to stop all services")

    def signal_handler(sig, frame):
        print("\n🛑 Shutting down services...")
        if flask_process:
            flask_process.terminate()
            try:
                flask_process.wait(timeout=5)
                print("✅ Flask app stopped")
            except subprocess.TimeoutExpired:
                flask_process.kill()
                print("⚠️ Flask app force-killed")

        print("🌐 Browser session will remain open for manual closure")
        print("👋 Goodbye!")
        sys.exit(0)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Keep the script running and monitor the Flask process
        while True:
            if flask_process.poll() is not None:
                print("❌ Flask app has stopped unexpectedly")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
