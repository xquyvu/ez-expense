"""
Enhanced script to start a debug browser with proper path detection
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from config import BROWSER, BROWSER_PORT

def find_browser_executable():
    """Find the browser executable on Windows"""
    
    browser_name = BROWSER.lower()
    
    if browser_name == "chrome":
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
    elif browser_name == "edge":
        possible_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        print(f"❌ Unsupported browser: {BROWSER}")
        return None
    
    for path in possible_paths:
        if Path(path).exists():
            print(f"✅ Found {browser_name} at: {path}")
            return path
    
    print(f"❌ Could not find {browser_name} executable")
    print("Tried these locations:")
    for path in possible_paths:
        print(f"  - {path}")
    return None

def start_debug_browser_manual():
    """Give instructions for manual browser start"""
    
    print("🔧 MANUAL BROWSER SETUP:")
    print("Since we can't auto-start the browser, please follow these steps:")
    print()
    
    if BROWSER.lower() == "edge":
        print("1️⃣ Open Command Prompt (cmd)")
        print("2️⃣ Run this command:")
        print(f'   msedge.exe --remote-debugging-port={BROWSER_PORT} --disable-web-security --user-data-dir=temp_edge_profile')
        print()
        print("3️⃣ Or try this if the above doesn't work:")
        print(f'   "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port={BROWSER_PORT} --disable-web-security --user-data-dir=temp_edge_profile')
    
    elif BROWSER.lower() == "chrome":
        print("1️⃣ Open Command Prompt (cmd)")  
        print("2️⃣ Run this command:")
        print(f'   chrome.exe --remote-debugging-port={BROWSER_PORT} --disable-web-security --user-data-dir=temp_chrome_profile')
        print()
        print("3️⃣ Or try this if the above doesn't work:")
        print(f'   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={BROWSER_PORT} --disable-web-security --user-data-dir=temp_chrome_profile')
    
    print()
    print("4️⃣ Navigate to: https://myexpense.operations.dynamics.com")
    print("5️⃣ Log in and open an expense report")
    print("6️⃣ Find an expense item and click 'Itemize' (if available)")
    print()

def start_debug_browser():
    """Start a browser in debug mode"""
    
    print(f"🔧 Setting up debug browser for MS Expense automation...")
    print(f"🔧 Browser: {BROWSER}")
    print(f"🔧 Port: {BROWSER_PORT}")
    print()
    
    # Try to find and start browser automatically
    browser_exe = find_browser_executable()
    
    if browser_exe:
        print(f"🔧 Starting {BROWSER} in debug mode...")
        
        browser_cmd = [
            browser_exe,
            f"--remote-debugging-port={BROWSER_PORT}",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            f"--user-data-dir=temp_{BROWSER.lower()}_profile",
            "https://myexpense.operations.dynamics.com"
        ]
        
        try:
            process = subprocess.Popen(browser_cmd)
            print(f"✅ Browser started with PID: {process.pid}")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"❌ Failed to start browser: {e}")
    
    # If automatic start failed, give manual instructions
    start_debug_browser_manual()
    return False

def test_connection():
    """Test if we can connect to the debug browser"""
    
    print("\n🔧 Testing connection to debug browser...")
    
    try:
        # Try to connect to the debug port
        import requests
        response = requests.get(f"http://localhost:{BROWSER_PORT}/json", timeout=5)
        
        if response.status_code == 200:
            tabs = response.json()
            print(f"✅ Connected! Found {len(tabs)} browser tabs:")
            
            for i, tab in enumerate(tabs[:5]):  # Show first 5 tabs
                title = tab.get('title', 'No title')[:50]
                url = tab.get('url', 'No URL')[:60] 
                print(f"   Tab {i+1}: {title} - {url}")
            
            # Look for MS Expense tabs
            ms_expense_tabs = [tab for tab in tabs if 'expense' in tab.get('url', '').lower() or 'expense' in tab.get('title', '').lower()]
            
            if ms_expense_tabs:
                print(f"\n🎯 Found {len(ms_expense_tabs)} MS Expense tabs!")
                return True
            else:
                print("\n⚠️  No MS Expense tabs found. Please navigate to MS Expense.")
                return False
        else:
            print(f"❌ Failed to connect (status: {response.status_code})")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 DEBUG BROWSER SETUP FOR HOTEL ITEMIZER")
    print("=" * 50)
    
    # Start the browser
    browser_started = start_debug_browser()
    
    if browser_started:
        print("\n⏳ Waiting 5 seconds for browser to fully start...")
        time.sleep(5)
    else:
        print("\n⏳ Please start the browser manually using the instructions above.")
        input("Press Enter when the debug browser is running...")
    
    # Test the connection
    if test_connection():
        print("\n🎉 SUCCESS! Debug browser is ready for automation!")
        print("\n📝 NEXT STEPS:")
        print("1. Make sure you're logged into MS Expense")
        print("2. Navigate to an expense report")
        print("3. Open an expense line item for editing")
        print("4. Look for 'Itemize' or itemization options")
        print("5. Test the hotel itemizer in your web app!")
        
    else:
        print("\n❌ Could not connect to debug browser.")
        print("Please check the browser is running with debug port enabled.")
    
    print(f"\n🔧 Debug browser should be running on port {BROWSER_PORT}")
    print("You can now test the hotel itemizer!")
    
    input("\nPress Enter to exit...")