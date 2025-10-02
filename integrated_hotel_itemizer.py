"""
Integrated Hotel Itemizer + MS Expense Automation
Gets data from hotel itemizer and pushes to MS Expense
"""
import asyncio
import requests
import json
from ms_expense_itemizer import MSExpenseAutomator

class IntegratedHotelItemizer:
    def __init__(self):
        self.hotel_itemizer_url = "http://localhost:5001"
        self.automator = MSExpenseAutomator()
        
    async def get_hotel_data_from_pdf(self, pdf_path=None):
        """Get hotel itemization data from the hotel itemizer service"""
        try:
            if pdf_path:
                # Upload PDF to hotel itemizer
                with open(pdf_path, 'rb') as f:
                    files = {'file': f}
                    response = requests.post(f"{self.hotel_itemizer_url}/api/hotel/upload", files=files)
                
                if response.status_code == 200:
                    return response.json()
            else:
                # Use sample data for testing
                return {
                    'line_items': [
                        {
                            'subcategory': 'Room charges',
                            'start_date': '2025-09-29',
                            'daily_rate': 150.00,
                            'quantity': 2,
                            'total_amount': 300.00
                        },
                        {
                            'subcategory': 'Meals',
                            'start_date': '2025-09-29',
                            'daily_rate': 45.00,
                            'quantity': 2,
                            'total_amount': 90.00
                        },
                        {
                            'subcategory': 'Incidentals',
                            'start_date': '2025-09-29',
                            'daily_rate': 15.00,
                            'quantity': 2,
                            'total_amount': 30.00
                        }
                    ],
                    'total_amount': 420.00
                }
        except Exception as e:
            print(f"❌ Error getting hotel data: {e}")
            return None
    
    async def itemize_hotel_in_ms_expense(self, pdf_path=None):
        """Complete workflow: Extract hotel data and itemize in MS Expense"""
        print("🏨 INTEGRATED HOTEL ITEMIZER + MS EXPENSE AUTOMATION")
        print("=" * 60)
        
        # Step 1: Get hotel data
        print("📄 Step 1: Getting hotel itemization data...")
        hotel_data = await self.get_hotel_data_from_pdf(pdf_path)
        
        if not hotel_data or not hotel_data.get('line_items'):
            print("❌ No hotel data available")
            return False
        
        print(f"✅ Found {len(hotel_data['line_items'])} hotel line items")
        for i, item in enumerate(hotel_data['line_items'], 1):
            print(f"   {i}. {item['subcategory']}: ${item['daily_rate']}/day × {item['quantity']} days = ${item['total_amount']}")
        
        # Step 2: Connect to MS Expense
        print("\n🌐 Step 2: Connecting to MS Expense...")
        if not await self.automator.connect_to_browser():
            print("❌ Could not connect to MS Expense")
            return False
        
        print("✅ Connected to MS Expense")
        
        # Step 3: Navigate to expense and open itemization
        await self.automator.wait_for_user("Navigate to your expense report and click on the hotel expense line item")
        
        # Click Actions > Itemize
        actions_selectors = [
            'button[aria-label*="Actions" i]',
            'button[title*="Actions" i]',
            'button:has-text("Actions")',
            '[data-dyn-controlname*="Actions"]'
        ]
        
        if not await self.automator.find_and_click_element(actions_selectors, "Actions menu"):
            await self.automator.wait_for_user("Please click on the Actions menu manually")
        
        itemize_selectors = [
            '[data-dyn-controlname*="Itemize"]',
            'button[title*="Itemize" i]',
            'a[title*="Itemize" i]',
            'button:has-text("Itemize")',
            'a:has-text("Itemize")'
        ]
        
        if not await self.automator.find_and_click_element(itemize_selectors, "Itemize option"):
            await self.automator.wait_for_user("Please click on Itemize manually")
        
        await self.automator.wait_for_user("Itemization view should now be open")
        
        # Step 4: Add each line item from hotel data
        print(f"\n📝 Step 4: Adding {len(hotel_data['line_items'])} itemization entries...")
        
        for i, item in enumerate(hotel_data['line_items'], 1):
            print(f"\n➕ Adding item {i}/{len(hotel_data['line_items'])}: {item['subcategory']}")
            
            # Click New button
            new_selectors = [
                '#ExpenseItemizeExpense_3_NewButtonItemizationGroup',
                'button[title*="New" i]',
                'button[aria-label*="New" i]',
                'button:has-text("New")'
            ]
            
            if not await self.automator.find_and_click_element(new_selectors, "New button"):
                input(f"Please click the New button for item {i} and press ENTER...")
            
            # Fill form fields with hotel data
            await self.fill_itemization_form(item)
            
            # Wait before adding next item
            if i < len(hotel_data['line_items']):
                input("Press ENTER to add the next itemization...")
        
        print("\n🎉 Hotel itemization completed!")
        print("Please review and save the itemizations in MS Expense.")
        
        return True
    
    async def fill_itemization_form(self, item_data):
        """Fill the itemization form with hotel line item data"""
        # Fill subcategory
        await self.automator.fill_form_field("Subcategory", item_data.get('subcategory', ''), [
            '#ExpenseItemizationTransTmp_SubCategoryRecId_306_0_0_ExpenseItemizationTransTmp_SubCategoryRecId_TrvSharedSubCategory_Name_input'
        ])
        
        # Fill start date
        await self.automator.fill_form_field("Start Date", item_data.get('start_date', ''), [
            '#ExpenseItemizationTransTmp_StartDate_306_0_0_input'
        ])
        
        # Fill daily rate
        await self.automator.fill_form_field("Daily Rate", str(item_data.get('daily_rate', '0')), [
            '#ExpenseItemizationTransTmp_DailyRate_306_0_0_input'
        ])
        
        # Fill quantity
        await self.automator.fill_form_field("Quantity", str(item_data.get('quantity', '1')), [
            '#ExpenseItemizationTransTmp_Quantity_306_0_0_input'
        ])

async def main():
    """Run the integrated hotel itemizer"""
    itemizer = IntegratedHotelItemizer()
    
    print("🏨 Welcome to the Integrated Hotel Itemizer!")
    print("This will:")
    print("1. Get hotel itemization data (from sample or PDF)")
    print("2. Connect to MS Expense in your browser")
    print("3. Automatically fill itemization forms")
    print()
    
    pdf_path = input("Enter path to hotel PDF (or press ENTER for sample data): ").strip()
    if not pdf_path:
        pdf_path = None
    
    await itemizer.itemize_hotel_in_ms_expense(pdf_path)

if __name__ == "__main__":
    asyncio.run(main())