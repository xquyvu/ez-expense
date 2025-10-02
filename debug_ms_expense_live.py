"""
Debug MS Expense Elements - Live Inspector
Shows what elements are actually available on the page
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_ms_expense_elements():
    """Connect and show all available elements"""
    async with async_playwright() as p:
        try:
            # Connect to existing browser
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            
            # Find MS Expense page
            pages = browser.contexts[0].pages
            ms_expense_page = None
            
            for page in pages:
                try:
                    url = page.url
                    if "myexpense.operations.dynamics.com" in url:
                        ms_expense_page = page
                        break
                except:
                    continue
            
            if not ms_expense_page:
                print("❌ No MS Expense page found")
                return
            
            await ms_expense_page.bring_to_front()
            
            print("🔍 MS EXPENSE LIVE ELEMENT DEBUG")
            print("=" * 50)
            print("Current URL:", ms_expense_page.url)
            print("Page Title:", await ms_expense_page.title())
            print()
            
            while True:
                print("\n" + "=" * 30)
                print("ELEMENT SEARCH OPTIONS:")
                print("1. Search for buttons")
                print("2. Search for inputs") 
                print("3. Search for elements containing 'New'")
                print("4. Search for elements containing 'subcategory'")
                print("5. Search for elements containing 'date'")
                print("6. Search for elements containing 'rate'")
                print("7. Search for elements containing 'quantity'")
                print("8. Custom selector search")
                print("9. Show all interactive elements")
                print("0. Exit")
                
                choice = input("\nChoice (0-9): ").strip()
                
                if choice == "0":
                    break
                elif choice == "1":
                    await search_elements(ms_expense_page, "button", "buttons")
                elif choice == "2":
                    await search_elements(ms_expense_page, "input", "inputs")
                elif choice == "3":
                    await search_by_text(ms_expense_page, "new", "New")
                elif choice == "4":
                    await search_by_text(ms_expense_page, "subcategory", "subcategory")
                elif choice == "5":
                    await search_by_text(ms_expense_page, "date", "date")
                elif choice == "6":
                    await search_by_text(ms_expense_page, "rate", "rate")
                elif choice == "7":
                    await search_by_text(ms_expense_page, "quantity", "quantity")
                elif choice == "8":
                    selector = input("Enter custom selector: ")
                    await search_elements(ms_expense_page, selector, f"custom selector '{selector}'")
                elif choice == "9":
                    await show_all_interactive(ms_expense_page)
                
        except Exception as e:
            print(f"❌ Error: {e}")

async def search_elements(page, selector, description):
    """Search for elements by selector"""
    try:
        print(f"\n🔍 Searching for {description}...")
        elements = await page.query_selector_all(selector)
        
        if not elements:
            print(f"❌ No {description} found")
            return
        
        print(f"✅ Found {len(elements)} {description}:")
        
        for i, element in enumerate(elements[:10], 1):  # Limit to 10
            try:
                tag_name = await element.evaluate('el => el.tagName')
                element_id = await element.get_attribute('id') or 'no-id'
                element_class = await element.get_attribute('class') or 'no-class'
                text_content = await element.text_content()
                text_preview = (text_content[:50] + "...") if text_content and len(text_content) > 50 else text_content
                
                print(f"  {i}. <{tag_name.lower()}>")
                print(f"     ID: {element_id}")
                print(f"     Class: {element_class}")
                print(f"     Text: {text_preview}")
                print()
                
            except Exception as e:
                print(f"  {i}. Error getting element info: {e}")
        
        if len(elements) > 10:
            print(f"... and {len(elements) - 10} more")
        
    except Exception as e:
        print(f"❌ Error searching for {description}: {e}")

async def search_by_text(page, text, description):
    """Search for elements containing specific text"""
    try:
        print(f"\n🔍 Searching for elements containing '{description}'...")
        
        # Search in various attributes and text content
        selectors_to_try = [
            f'*[id*="{text}" i]',
            f'*[class*="{text}" i]',
            f'*[name*="{text}" i]',
            f'*[title*="{text}" i]',
            f'*[aria-label*="{text}" i]',
            f'*:has-text("{text}")',
        ]
        
        all_found = []
        
        for selector in selectors_to_try:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements[:5]:  # Limit per selector
                    try:
                        element_info = await get_element_info(element)
                        all_found.append((selector, element_info))
                    except:
                        continue
            except:
                continue
        
        if not all_found:
            print(f"❌ No elements found containing '{description}'")
            return
        
        print(f"✅ Found {len(all_found)} elements:")
        for i, (selector, info) in enumerate(all_found[:15], 1):
            print(f"  {i}. Selector: {selector}")
            print(f"     Element: <{info['tag']}>")
            print(f"     ID: {info['id']}")
            print(f"     Class: {info['class']}")
            print(f"     Text: {info['text']}")
            print()
        
    except Exception as e:
        print(f"❌ Error: {e}")

async def show_all_interactive(page):
    """Show all interactive elements on the page"""
    try:
        print(f"\n🔍 Finding all interactive elements...")
        
        interactive_selectors = [
            'button',
            'input',
            'select',
            'textarea',
            'a[href]',
            '[onclick]',
            '[data-dyn-controlname]'
        ]
        
        all_interactive = []
        
        for selector in interactive_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        info = await get_element_info(element)
                        all_interactive.append((selector, info))
                    except:
                        continue
            except:
                continue
        
        if not all_interactive:
            print("❌ No interactive elements found")
            return
        
        print(f"✅ Found {len(all_interactive)} interactive elements:")
        for i, (selector_type, info) in enumerate(all_interactive[:20], 1):
            print(f"  {i}. Type: {selector_type}")
            print(f"     Element: <{info['tag']}>")
            print(f"     ID: {info['id']}")
            print(f"     Text: {info['text']}")
            print()
        
        if len(all_interactive) > 20:
            print(f"... and {len(all_interactive) - 20} more")
        
    except Exception as e:
        print(f"❌ Error: {e}")

async def get_element_info(element):
    """Get basic info about an element"""
    try:
        return {
            'tag': await element.evaluate('el => el.tagName.toLowerCase()'),
            'id': await element.get_attribute('id') or 'no-id',
            'class': await element.get_attribute('class') or 'no-class',
            'text': (await element.text_content() or '')[:50]
        }
    except:
        return {'tag': 'unknown', 'id': 'error', 'class': 'error', 'text': 'error'}

if __name__ == "__main__":
    asyncio.run(debug_ms_expense_elements())