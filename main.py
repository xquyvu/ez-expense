import datetime
import os
import time
from logging import getLogger
from pathlib import Path
from textwrap import dedent

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from browser import BrowserProcess

logger = getLogger(__name__)

load_dotenv()

PORT = os.getenv("PORT", 9222)
EXPENSE_APP_URL = "myexpense.operations.dynamics.com"

INPUT_DATA_PATH = Path("./input_data")
INPUT_DATA_PATH.mkdir(exist_ok=True)

RECEIPTS_PATH = INPUT_DATA_PATH / "receipts"
RECEIPTS_PATH.mkdir(exist_ok=True)

EXPENSE_ID_COLUMN = "EXPENSE_ID"

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
        page.get_by_text("Expense management", exact=True).click()

    # Wait for the user input
    input(
        """Press <Enter> after you have created a new expense report, or navigated
        to the expense report you want to fill. Press <Ctrl+C> to exit at any
        time."""
    )

    category = "Airfare"
    amount = "10"
    currency = "CHF"
    date_to_fill = datetime.datetime.now().date()
    merchant = "merchant"
    description = "desc"  # Expense description / Business purpose

    # region: Show the Created ID column
    page.get_by_role("button", name="Grid options").click()
    page.get_by_text("Insert columns...").click()

    # Filter for the Created ID column
    page.fill('input[name="QuickFilterControl_Input"]', "Created ID")
    page.wait_for_timeout(2000)
    page.keyboard.press("Enter")

    # Uncheck all Created ID columns
    created_id_columns = [
        row
        for row in page.query_selector_all("div.fixedDataTableCellGroupLayout_cellGroup")
        if "Created ID" in row.inner_html() and "Number" in row.inner_html()
    ]

    for created_id_column in created_id_columns:
        created_id_checkbox = created_id_column.query_selector("span.dyn-checkbox-span")
        if created_id_checkbox.is_checked():
            created_id_checkbox.click()

    # Then check the one that's corresponding to "Expense lines"
    expense_line_created_id_column = next(
        row for row in created_id_columns if "Expense lines" in row.inner_html()
    )

    created_id_checkbox = expense_line_created_id_column.query_selector("span.dyn-checkbox-span")
    if not created_id_checkbox.is_checked():
        created_id_checkbox.click()

    page.click('button[data-dyn-controlname="OK"]')
    # endregion

    # region: Export the list of existing expenses
    with page.expect_download() as download_info:
        page.click('button[name="MoreActions"]')
        page.get_by_text("Export to Microsoft Excel", exact=True).click()
        page.click('button[name="DownloadButton"]')

    existing_expenses_path = INPUT_DATA_PATH / "existing_expenses.csv"

    # Add ID column to the expense report
    existing_expenses = pd.read_excel(download_info.value.url)
    existing_expenses[EXPENSE_ID_COLUMN] = existing_expenses.index + 1
    existing_expenses.to_csv(existing_expenses_path, index=False)
    # endregion

    if existing_expenses.shape[0]:
        print("""Found existing expenses""")

        num_expenses_without_receipts = (existing_expenses["Receipts attached"] == "No").sum()

        if num_expenses_without_receipts:
            print(
                dedent(
                    f"""
                    Found {num_expenses_without_receipts} expense(s) without receipts attached.

                    1. Please find the ID of each expense without receipt by either:
                       - Look at the `{EXPENSE_ID_COLUMN}` column in the spreadsheet saved at
                         {existing_expenses_path.absolute()}; or
                       - Use the row number of the expense in the Expense management app
                         (starting from 1).

                    2. Gather the receipt file(s) you want to attach to the expense(s)
                       and put them in the {RECEIPTS_PATH.absolute()} directory.

                    3. Add the expense ID as prefix to the receipt file(s) that corresponds
                       to your expense. For example, if your expense with ID `10` had 2
                       receipts files, `restaurant.jpg` and `bar.jpg`, then rename the files
                       to `10_restaurant.jpg` and `10_bar.jpg`. """,
                )
            )
            input("Press <Enter> when you are done, or <Ctrl+C> to exit.")

    # Now we add receipts to the expenses. Reload the existing expenses file because it may have been updated
    existing_expenses = pd.read_csv(existing_expenses_path)

    receipt_file_paths = list(RECEIPTS_PATH.glob("*"))

    mapped_receipt_files: dict[int, list[Path]] = {}
    unmapped_receipt_files = []

    for receipt_file_path in receipt_file_paths:
        try:
            expense_id = int(receipt_file_path.stem.split("_")[0])
            if expense_id in existing_expenses[EXPENSE_ID_COLUMN].values:
                mapped_receipt_files.setdefault(expense_id, []).append(receipt_file_path)
            else:
                unmapped_receipt_files.append(receipt_file_path)
        except ValueError:
            unmapped_receipt_files.append(receipt_file_path)

    # Now join back to the pandas dataframe
    mapped_receipt_files_data = (
        pd.Series(mapped_receipt_files, name="Receipt files")
        .reset_index()
        .rename(columns={"index": EXPENSE_ID_COLUMN})
    )

    existing_expenses_to_update = pd.merge(
        existing_expenses,
        mapped_receipt_files_data,
        on=EXPENSE_ID_COLUMN,
        how="inner",
    )

    # Now, we go over each expense that needs receipts attached

    # Attach receipts to the expenses
    page.click('button[name="NewExpenseButton"]')
    page.wait_for_load_state("networkidle", timeout=10000)

    page.fill('input[name="CategoryInput"]', category)
    page.fill('input[name="AmountInput"]', amount)
    page.fill('input[name="CurrencyInput"]', currency)
    page.fill('input[name="MerchantInputNoLookup"]', merchant)
    page.fill('input[name="DateInput"]', date_to_fill.strftime("%-m/%-d/%Y"))
    page.fill('textarea[name="NotesInput"]', description)

    page.click('button[name="SaveButton"]')
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
