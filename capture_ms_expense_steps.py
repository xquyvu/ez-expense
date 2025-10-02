"""
Simple MS Expense Step Recorder
Captures user actions and HTML elements as you navigate through itemization
"""
import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

class MSExpenseStepRecorder:
    def __init__(self):
        self.steps = []
        self.step_count = 0
        
    async def record_steps(self):
        """Connect to your existing browser and record your actions"""
        async with async_playwright() as p:
            try:
                # Connect to existing debug browser
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                print("🔗 Connected to your browser")
                
                # Find MS Expense page
                pages = browser.contexts[0].pages
                ms_expense_page = None
                
                for page in pages:
                    try:
                        url = page.url
                        if "myexpense.operations.dynamics.com" in url:
                            ms_expense_page = page
                            print(f"📄 Found MS Expense page: {url}")
                            break
                    except:
                        continue
                
                if not ms_expense_page:
                    print("❌ No MS Expense page found")
                    return
                
                # Focus on the page
                await ms_expense_page.bring_to_front()
                print("\n🎬 RECORDING MODE ACTIVE")
                print("=" * 50)
                print("Now perform your itemization steps in MS Expense:")
                print("1. Click on an expense line item")
                print("2. Look for itemize button/option") 
                print("3. Click itemize")
                print("4. Interact with itemization form")
                print("\nPress ENTER after each major step to record it...")
                print("Type 'done' when finished")
                print("=" * 50)
                
                while True:
                    # Wait for user input
                    user_input = input(f"\nStep {self.step_count + 1} - Press ENTER to capture current state (or 'done' to finish): ")
                    
                    if user_input.lower() == 'done':
                        break
                    
                    # Capture current state
                    step = await self.capture_current_state(ms_expense_page)
                    self.steps.append(step)
                    self.step_count += 1
                    
                    print(f"✅ Captured step {self.step_count}")
                
                # Save results
                await self.save_results()
                print(f"\n🎉 Recorded {len(self.steps)} steps successfully!")
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def capture_current_state(self, page):
        """Capture the current state of the page"""
        try:
            # Get basic page info
            title = await page.title()
            url = page.url
            
            # Get current HTML (first 5000 chars to avoid huge dumps)
            html_content = await page.content()
            html_preview = html_content[:5000] + "..." if len(html_content) > 5000 else html_content
            
            # Look for common itemization elements
            selectors_to_check = [
                'button[title*="itemize" i]',
                'button[title*="split" i]', 
                'a[title*="itemize" i]',
                'input[name*="itemize" i]',
                '[data-testid*="itemize"]',
                '[aria-label*="itemize" i]',
                'button:has-text("Itemize")',
                'a:has-text("Itemize")',
                '.itemize',
                '#itemize'
            ]
            
            found_elements = []
            for selector in selectors_to_check:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements[:3]:  # Max 3 per selector
                            element_html = await element.inner_html()
                            outer_html = await element.evaluate('el => el.outerHTML')
                            found_elements.append({
                                'selector': selector,
                                'inner_html': element_html,
                                'outer_html': outer_html[:500] + "..." if len(outer_html) > 500 else outer_html
                            })
                except:
                    continue
            
            step = {
                'step_number': self.step_count + 1,
                'timestamp': datetime.now().isoformat(),
                'title': title,
                'url': url,
                'found_itemize_elements': found_elements,
                'html_preview': html_preview
            }
            
            return step
            
        except Exception as e:
            return {
                'step_number': self.step_count + 1,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    async def save_results(self):
        """Save the recorded steps"""
        filename = f"ms_expense_steps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.steps, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Steps saved to: {filename}")
        
        # Also create a summary
        summary_file = f"ms_expense_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("MS EXPENSE ITEMIZATION STEPS SUMMARY\n")
            f.write("=" * 40 + "\n\n")
            
            for i, step in enumerate(self.steps, 1):
                f.write(f"STEP {i}:\n")
                f.write(f"Title: {step.get('title', 'N/A')}\n")
                f.write(f"URL: {step.get('url', 'N/A')}\n")
                f.write(f"Itemize elements found: {len(step.get('found_itemize_elements', []))}\n")
                
                for elem in step.get('found_itemize_elements', []):
                    f.write(f"  - Selector: {elem['selector']}\n")
                    f.write(f"    HTML: {elem['outer_html'][:200]}...\n")
                
                f.write("\n" + "-" * 30 + "\n\n")
        
        print(f"📋 Summary saved to: {summary_file}")

async def main():
    recorder = MSExpenseStepRecorder()
    await recorder.record_steps()

if __name__ == "__main__":
    asyncio.run(main())