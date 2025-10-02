"""
Test script to debug Playwright connection with MS Expense
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright_manager import start_playwright, connect_to_browser, get_current_page
from config import BROWSER_PORT

async def test_playwright_connection():
    """Test the Playwright connection to MS Expense"""
    
    print("🔧 Testing Playwright Connection...")
    print(f"🔧 Configured browser port: {BROWSER_PORT}")
    
    try:
        # Step 1: Start playwright
        print("\n1️⃣ Starting Playwright...")
        playwright = await start_playwright()
        print("✅ Playwright started successfully")
        
        # Step 2: Try to connect to browser
        print("\n2️⃣ Connecting to browser...")
        browser = await connect_to_browser()
        print("✅ Browser connection established")
        
        # Step 3: Check existing pages (contexts)
        print("\n3️⃣ Checking browser contexts...")
        contexts = browser.contexts
        print(f"📄 Found {len(contexts)} browser contexts")
        
        all_pages = []
        for context in contexts:
            pages = context.pages
            all_pages.extend(pages)
            print(f"   Context has {len(pages)} pages")
        
        print(f"📄 Total pages across all contexts: {len(all_pages)}")
        
        for i, page in enumerate(all_pages[:10]):  # Show first 10 pages
            url = page.url
            title = await page.title()
            print(f"   Page {i+1}: {title} - {url}")
        
        # Step 4: Check if any page looks like MS Expense
        ms_expense_pages = []
        for page in all_pages:
            url = page.url.lower()
            if any(keyword in url for keyword in ['expense', 'myexpense', 'dynamics']):
                ms_expense_pages.append(page)
        
        if ms_expense_pages:
            print(f"\n✅ Found {len(ms_expense_pages)} MS Expense pages!")
            for i, page in enumerate(ms_expense_pages):
                print(f"   MS Expense Page {i+1}: {await page.title()} - {page.url}")
        else:
            print("\n⚠️  No MS Expense pages found")
            print("📝 Make sure you have MS Expense open in the browser")
        
        return {
            "success": True,
            "browser_connected": True,
            "total_pages": len(all_pages),
            "ms_expense_pages": len(ms_expense_pages),
            "pages": [(await p.title(), p.url) for p in all_pages]
        }
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    result = asyncio.run(test_playwright_connection())
    
    print("\n" + "="*50)
    print("📋 SUMMARY:")
    
    if result["success"]:
        print("✅ Playwright connection working")
        print(f"📄 Total pages: {result['total_pages']}")
        print(f"💼 MS Expense pages: {result['ms_expense_pages']}")
        
        if result['ms_expense_pages'] > 0:
            print("\n🎯 NEXT STEPS:")
            print("1. Try the hotel itemizer with a PDF")
            print("2. The automation should connect to your MS Expense page")
        else:
            print("\n⚠️  TO FIX:")
            print("1. Open MS Expense in your browser")
            print("2. Navigate to an expense report")
            print("3. Try the hotel itemizer again")
            
    else:
        print("❌ Connection failed")
        print(f"Error: {result['error']}")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Make sure browser is running in debug mode")
        print("2. Check if port 9222 is available")
        print("3. Try restarting the EZ-Expense main app")