"""
MS Expense UI Inspector - Help find selectors for automation
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright_manager import start_playwright, connect_to_browser

async def inspect_ms_expense_ui():
    """Interactive UI inspector for MS Expense"""
    
    print("🔍 MS EXPENSE UI INSPECTOR")
    print("=" * 50)
    
    try:
        # Connect to browser
        print("🔧 Connecting to debug browser...")
        playwright = await start_playwright()
        browser = await connect_to_browser()
        
        # Get MS Expense pages
        all_pages = []
        for context in browser.contexts:
            all_pages.extend(context.pages)
        
        ms_expense_pages = []
        for page in all_pages:
            url = page.url.lower()
            if any(keyword in url for keyword in ['expense', 'myexpense', 'dynamics']):
                ms_expense_pages.append(page)
        
        if not ms_expense_pages:
            print("❌ No MS Expense pages found!")
            print("Please navigate to MS Expense first.")
            return
        
        print(f"✅ Found {len(ms_expense_pages)} MS Expense pages:")
        for i, page in enumerate(ms_expense_pages):
            title = await page.title()
            print(f"   {i+1}. {title} - {page.url}")
        
        # Let user choose page
        if len(ms_expense_pages) > 1:
            choice = input(f"\nWhich page to inspect? (1-{len(ms_expense_pages)}): ")
            try:
                page_index = int(choice) - 1
                if page_index < 0 or page_index >= len(ms_expense_pages):
                    raise ValueError()
            except ValueError:
                print("Invalid choice, using first page")
                page_index = 0
        else:
            page_index = 0
        
        page = ms_expense_pages[page_index]
        print(f"\n🎯 Inspecting: {await page.title()}")
        
        # Interactive menu
        while True:
            print("\n" + "=" * 50)
            print("🔍 INSPECTION OPTIONS:")
            print("1. Search for 'itemize' elements")
            print("2. Search for form/input elements")  
            print("3. Search for dropdown/select elements")
            print("4. Search for button elements")
            print("5. Search for custom text")
            print("6. Get page HTML (save to file)")
            print("7. Switch to different MS Expense page")
            print("0. Exit")
            
            choice = input("\nChoose option (0-7): ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                await search_itemize_elements(page)
            elif choice == "2":
                await search_form_elements(page)
            elif choice == "3":
                await search_dropdown_elements(page)
            elif choice == "4":
                await search_button_elements(page)
            elif choice == "5":
                custom_text = input("Enter text to search for: ").strip()
                if custom_text:
                    await search_custom_text(page, custom_text)
            elif choice == "6":
                await save_page_html(page)
            elif choice == "7":
                # Switch page logic
                if len(ms_expense_pages) > 1:
                    for i, p in enumerate(ms_expense_pages):
                        title = await p.title()
                        print(f"   {i+1}. {title}")
                    new_choice = input(f"Switch to page (1-{len(ms_expense_pages)}): ")
                    try:
                        new_index = int(new_choice) - 1
                        if 0 <= new_index < len(ms_expense_pages):
                            page = ms_expense_pages[new_index]
                            print(f"✅ Switched to: {await page.title()}")
                    except ValueError:
                        print("Invalid choice")
                else:
                    print("Only one MS Expense page available")
            else:
                print("Invalid option")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def search_itemize_elements(page):
    """Search for itemize-related elements"""
    
    print("\n🔍 Searching for itemize elements...")
    
    selectors_to_try = [
        "button:has-text('itemize')",
        "button:has-text('Itemize')", 
        "a:has-text('itemize')",
        "a:has-text('Itemize')",
        "[aria-label*='itemiz']",
        "[title*='itemiz']",
        "[data-automation-id*='itemiz']",
        "button[id*='itemiz']",
        "a[id*='itemiz']",
        ".itemiz*",
    ]
    
    found_elements = []
    
    for selector in selectors_to_try:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"✅ Found {len(elements)} elements with selector: {selector}")
                for i, elem in enumerate(elements):
                    text = await elem.inner_text()
                    if text.strip():
                        print(f"   Element {i+1}: '{text[:100]}...'")
                        found_elements.append((selector, text.strip()))
        except Exception as e:
            print(f"❌ Error with selector '{selector}': {e}")
    
    if not found_elements:
        print("⚠️  No itemize elements found with standard selectors")
        print("\n💡 Try these manual steps:")
        print("1. Navigate to an expense line item")
        print("2. Right-click on 'Itemize' button/link")
        print("3. Select 'Inspect Element'")
        print("4. Copy the selector and share it")

async def search_form_elements(page):
    """Search for form input elements"""
    
    print("\n🔍 Searching for form elements...")
    
    # Look for common MS Expense form fields
    field_names = [
        "subcategory", "category", "dailyrate", "daily rate", "startdate", "start date", 
        "quantity", "amount", "rate", "days", "itemization"
    ]
    
    for field_name in field_names:
        print(f"\n🔍 Looking for '{field_name}' fields...")
        
        selectors = [
            f"input[name*='{field_name}' i]",
            f"select[name*='{field_name}' i]", 
            f"input[aria-label*='{field_name}' i]",
            f"select[aria-label*='{field_name}' i]",
            f"input[id*='{field_name}' i]",
            f"select[id*='{field_name}' i]",
            f"[data-automation-id*='{field_name}' i]"
        ]
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"   ✅ Found {len(elements)} elements: {selector}")
            except Exception as e:
                pass

async def search_dropdown_elements(page):
    """Search for dropdown/select elements"""
    
    print("\n🔍 Searching for dropdown elements...")
    
    selectors = [
        "select",
        "[role='combobox']",
        "[aria-expanded]",
        ".dropdown",
        "[data-automation-id*='dropdown']",
        "[data-automation-id*='combo']"
    ]
    
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"✅ Found {len(elements)} dropdowns: {selector}")
                for i, elem in enumerate(elements[:3]):  # Show first 3
                    try:
                        label = await elem.get_attribute("aria-label") or await elem.get_attribute("name") or "No label"
                        print(f"   Dropdown {i+1}: {label}")
                    except:
                        pass
        except Exception as e:
            pass

async def search_button_elements(page):
    """Search for button elements"""
    
    print("\n🔍 Searching for button elements...")
    
    try:
        buttons = await page.query_selector_all("button")
        print(f"✅ Found {len(buttons)} buttons total")
        
        # Show buttons with text
        for i, button in enumerate(buttons[:10]):  # Show first 10
            try:
                text = await button.inner_text()
                if text.strip():
                    aria_label = await button.get_attribute("aria-label") or ""
                    print(f"   Button {i+1}: '{text[:50]}' (aria-label: '{aria_label[:30]}')")
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error searching buttons: {e}")

async def search_custom_text(page, text):
    """Search for custom text"""
    
    print(f"\n🔍 Searching for text: '{text}'...")
    
    selectors = [
        f"text={text}",
        f"text*={text}",
        f"button:has-text('{text}')",
        f"a:has-text('{text}')",
        f"[aria-label*='{text}' i]",
        f"[title*='{text}' i]"
    ]
    
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"✅ Found {len(elements)} elements: {selector}")
        except Exception as e:
            pass

async def save_page_html(page):
    """Save page HTML to file"""
    
    try:
        html = await page.content()
        filename = "ms_expense_page.html"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Page HTML saved to: {filename}")
        print(f"📄 File size: {len(html):,} characters")
        
    except Exception as e:
        print(f"❌ Error saving HTML: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_ms_expense_ui())