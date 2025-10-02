"""
MS Expense Itemizer Automation
Based on recorded user steps: Actions -> Itemize -> New -> Fill form
"""
import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

class MSExpenseAutomator:
    def __init__(self):
        self.page = None
        self.browser = None
        
    async def connect_to_browser(self):
        """Connect to existing browser"""
        try:
            playwright = await async_playwright().start()
            # Try both Chrome and Edge
            for browser_type in ['chromium', 'msedge']:
                try:
                    self.browser = await getattr(playwright, browser_type).connect_over_cdp("http://localhost:9222")
                    print(f"✅ Connected to {browser_type}")
                    break
                except:
                    continue
            
            if not self.browser:
                print("❌ Could not connect to browser. Please start debug browser first.")
                return False
                
            # Find MS Expense page
            pages = self.browser.contexts[0].pages
            for page in pages:
                try:
                    if "myexpense.operations.dynamics.com" in page.url:
                        self.page = page
                        await page.bring_to_front()
                        print(f"📄 Found MS Expense: {page.url}")
                        return True
                except:
                    continue
                    
            print("❌ No MS Expense page found")
            return False
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def wait_for_user(self, message):
        """Wait for user confirmation"""
        return input(f"\n⏳ {message}\nPress ENTER when ready...")
    
    async def find_and_click_element(self, selectors, description, wait_time=5000):
        """Try multiple selectors to find and click an element"""
        print(f"🔍 Looking for {description}...")
        
        for selector in selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=wait_time)
                element = await self.page.query_selector(selector)
                if element:
                    await element.click()
                    print(f"✅ Clicked {description} using: {selector}")
                    return True
            except:
                continue
        
        print(f"❌ Could not find {description}")
        print("Available selectors tried:", selectors)
        return False
    
    async def itemize_hotel_expense(self, hotel_data):
        """Automate the hotel expense itemization process"""
        try:
            print("🏨 STARTING HOTEL ITEMIZATION AUTOMATION")
            print("=" * 50)
            
            # Step 1: User navigates to expense report manually
            await self.wait_for_user("Navigate to your expense report and click on the hotel expense line item")
            
            # Step 2: Look for Actions menu or Itemize button
            print("\n🔍 Step 2: Looking for Actions menu or Itemize option...")
            
            actions_selectors = [
                'button[title*="Actions" i]',
                'button[aria-label*="Actions" i]',
                'button:has-text("Actions")',
                '[data-dyn-controlname*="Actions"]',
                '.dyn-action-button',
                'button[data-testid*="actions"]'
            ]
            
            if not await self.find_and_click_element(actions_selectors, "Actions menu"):
                await self.wait_for_user("Please click on the Actions menu manually")
            
            # Step 3: Click Itemize option
            print("\n📋 Step 3: Looking for Itemize option...")
            
            itemize_selectors = [
                'button[title*="Itemize" i]',
                'a[title*="Itemize" i]',
                'button:has-text("Itemize")',
                'a:has-text("Itemize")',
                '[data-dyn-controlname*="Itemize"]',
                'menuitem[title*="Itemize" i]'
            ]
            
            if not await self.find_and_click_element(itemize_selectors, "Itemize option"):
                await self.wait_for_user("Please click on Itemize manually")
            
            # Step 4: Wait for itemization view to load
            await self.wait_for_user("Itemization view should now be open. You should see subcategory, start date, daily rate, quantity fields")
            
            # Step 5: Click New button to add itemization
            print("\n➕ Step 5: Looking for New button...")
            
            new_selectors = [
                '#ExpenseItemizeExpense_3_NewButtonItemizationGroup',
                'button[title*="New" i]',
                'button[aria-label*="New" i]',
                'button:has-text("New")',
                '[data-dyn-controlname*="New"]',
                'button[data-testid*="new"]',
                '.dyn-new-button'
            ]
            
            if not await self.find_and_click_element(new_selectors, "New button"):
                await self.wait_for_user("Please click the New button to add an itemization manually")
            
            # Step 6: Fill itemization form
            print("\n📝 Step 6: Filling itemization form...")
            
            # Fill subcategory
            await self.fill_form_field("Subcategory", hotel_data.get('subcategory', 'Room charges'), [
                '#ExpenseItemizationTransTmp_SubCategoryRecId_306_0_0_ExpenseItemizationTransTmp_SubCategoryRecId_TrvSharedSubCategory_Name_input',
                'select[data-dyn-controlname*="subcategory" i]',
                'input[data-dyn-controlname*="subcategory" i]',
                'select[name*="subcategory" i]',
                'input[name*="subcategory" i]'
            ])
            
            # Fill start date
            await self.fill_form_field("Start Date", hotel_data.get('start_date', ''), [
                '#ExpenseItemizationTransTmp_StartDate_306_0_0_input',
                'input[data-dyn-controlname*="startdate" i]',
                'input[data-dyn-controlname*="date" i]',
                'input[name*="startdate" i]',
                'input[type="date"]'
            ])
            
            # Fill daily rate
            await self.fill_form_field("Daily Rate", str(hotel_data.get('daily_rate', '0')), [
                '#ExpenseItemizationTransTmp_DailyRate_306_0_0_input',
                'input[data-dyn-controlname*="rate" i]',
                'input[data-dyn-controlname*="amount" i]',
                'input[name*="rate" i]',
                'input[type="number"]'
            ])
            
            # Fill quantity
            await self.fill_form_field("Quantity", str(hotel_data.get('quantity', '1')), [
                '#ExpenseItemizationTransTmp_Quantity_306_0_0_input',
                'input[data-dyn-controlname*="quantity" i]',
                'input[data-dyn-controlname*="qty" i]',
                'input[name*="quantity" i]'
            ])
            
            print("\n✅ Hotel itemization automation completed!")
            print("Please review and save the itemization manually.")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in itemization: {e}")
            return False
    
    async def fill_form_field(self, field_name, value, selectors):
        """Fill a form field with the given value"""
        print(f"  📝 Filling {field_name}: {value}")
        
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    # Check if it's a select element
                    tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                    if tag_name == 'select':
                        await element.select_option(value)
                    else:
                        await element.clear()
                        await element.fill(value)
                    
                    print(f"    ✅ Filled {field_name} using: {selector}")
                    return True
            except:
                continue
        
        print(f"    ❌ Could not fill {field_name}")
        input(f"    Please fill {field_name} with '{value}' manually and press ENTER...")
        return False

async def main():
    """Test the automation with sample hotel data"""
    
    # Sample hotel data
    hotel_data = {
        'subcategory': 'Room charges',
        'start_date': '2025-09-29',
        'daily_rate': '150.00',
        'quantity': '2'
    }
    
    print("🏨 MS EXPENSE HOTEL ITEMIZATION AUTOMATION")
    print("=" * 50)
    print("\nThis will help you itemize a hotel expense in MS Expense")
    print("Make sure you have:")
    print("1. MS Expense open in your browser")
    print("2. Navigated to an expense report") 
    print("3. Ready to click on a hotel expense line item")
    print()
    
    automator = MSExpenseAutomator()
    
    if await automator.connect_to_browser():
        await automator.itemize_hotel_expense(hotel_data)
    else:
        print("❌ Could not connect to browser")
        print("Please start the debug browser first with: python setup_debug_browser.py")

if __name__ == "__main__":
    asyncio.run(main())