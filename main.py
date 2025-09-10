import datetime
import os
import time
from logging import getLogger

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from browser import BrowserProcess

logger = getLogger(__name__)

load_dotenv()

PORT = os.getenv("PORT", 9222)
EXPENSE_APP_URL = "myexpense.operations.dynamics.com"

browser_process = BrowserProcess(browser_name="edge", port=PORT)
browser_process.close_browser_if_running()
browser_process.start_browser_debug_mode()
time.sleep(2)  # Give Edge time to start

with sync_playwright() as p:
    # Attach to the existing browser instance
    browser = p.chromium.connect_over_cdp(f"http://localhost:{PORT}")

    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else browser.new_context()

    for page in context.pages:
        if EXPENSE_APP_URL in page.url:
            page.bring_to_front()
            break
    else:
        page = context.new_page()
        page.goto(f"https://{EXPENSE_APP_URL}")

    # Wait for the user input
    input(
        """Press <Enter> after you have created a new expense report, or navigated
        to the expense report you want to fill. Press <Ctrl+C> to exit at any
        time."""
    )

    new_expense_button = page.get_by_text("New expense", exact=True)
    new_expense_button.click()
    page.wait_for_load_state("networkidle", timeout=10000)

    category = "Airfare"
    amount = "10"
    currency = "CHF"
    date_to_fill = datetime.datetime.now().date()
    merchant = "merchant"
    description = "desc"  # Expense description / Business purpose

    page.fill('input[name="CategoryInput"]', category)
    page.fill('input[name="AmountInput"]', amount)
    page.fill('input[name="CurrencyInput"]', currency)
    page.fill('input[name="MerchantInputNoLookup"]', merchant)
    page.fill('input[name="DateInput"]', date_to_fill.strftime("%-m/%-d/%Y"))
    page.fill('textarea[name="NotesInput"]', description)

    page.get_by_text("Save").click()
    page.wait_for_timeout(3000)

    # Now we add receipt to the expense
    receipt_file_paths = ["screenshot.png"]

    for receipt_file_path in receipt_file_paths:
        page.click('a[name="EditReceipts"]')
        page.click('button[name="AddButton"]')

        # Upload receipt
        with page.expect_file_chooser() as file_chooser_info:
            page.click('button[name="UploadControlBrowseButton"]')

        file_chooser = file_chooser_info.value
        file_chooser.set_files(receipt_file_path)

        page.click('button[name="UploadControlUploadButton"]')
        page.click('button[name="OkButtonAddNewTabPage"]')
        page.wait_for_timeout(1000)
        page.get_by_text("Close", exact=True).click()

        page.get_by_text("Save and continue", exact=True).click()
