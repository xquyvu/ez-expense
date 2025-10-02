"""
Simple script to start a debug browser for MS Expense automation
"""

import subprocess
import sys
import time
import webbrowser
from config import BROWSER, BROWSER_PORT

def start_debug_browser():
    """Start a browser in debug mode"""
    
    print(f"🔧 Starting {BROWSER} browser in debug mode on port {BROWSER_PORT}...")
    
    if BROWSER.lower() == "chrome":
        browser_cmd = [
            "chrome.exe",
            f"--remote-debugging-port={BROWSER_PORT}",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--user-data-dir=temp_chrome_profile",
            "about:blank"
        ]
    elif BROWSER.lower() == "edge":
        browser_cmd = [
            "msedge.exe", 
            f"--remote-debugging-port={BROWSER_PORT}",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor", 
            "--user-data-dir=temp_edge_profile",
            "about:blank"
        ]
    else:
        print(f"❌ Unsupported browser: {BROWSER}")
        return False
    
    try:
        # Start the browser process
        process = subprocess.Popen(browser_cmd)
        print(f"✅ Browser started with PID: {process.pid}")
        
        # Wait a moment for browser to start
        time.sleep(3)
        
        # Open MS Expense
        print("🔧 Opening MS Expense...")
        ms_expense_url = "https://myexpense.operations.dynamics.com"
        webbrowser.open(ms_expense_url)
        
        print("✅ Debug browser started successfully!")
        print(f"📋 Browser is running on port {BROWSER_PORT}")
        print(f"🌐 MS Expense should be opening at: {ms_expense_url}")
        print()
        print("📝 NEXT STEPS:")
        print("1. Navigate to an expense report in MS Expense")
        print("2. Open an expense item for editing") 
        print("3. Look for the 'Itemize' button/option")
        print("4. Click it to enter itemization mode")
        print("5. Then test the hotel itemizer!")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start browser: {e}")
        return False

if __name__ == "__main__":
    if start_debug_browser():
        print("\n🎯 Browser is ready! You can now test the hotel itemizer.")
        input("Press Enter when you're ready to close this browser...")
    else:
        print("❌ Failed to start debug browser")
        sys.exit(1)