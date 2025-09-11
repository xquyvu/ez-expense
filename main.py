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

EXPENSE_ID_COLUMN = "Created ID"
EXPENSE_LINE_NUMBER_COLUMN = "Line number"
RECEIPT_PATHS_COLUMN = "Receipt files"

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

    # region: Open the column selection dialog
    page.get_by_role("button", name="Grid options").click()
    page.get_by_text("Insert columns...").click()

    # region: Show the Created ID column, which we will use to identify which expense to
    # click on in the tool
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

    expense_lines = page.get_by_role("textbox", name="Created ID", include_hidden=True).all()

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

    # endregion

    # region: Show the Line number column, which we will use as the ID for each expense
    page.fill('input[name="QuickFilterControl_Input"]', EXPENSE_LINE_NUMBER_COLUMN)
    page.wait_for_timeout(2000)
    page.keyboard.press("Enter")

    line_number_column = next(
        row
        for row in page.query_selector_all("div.fixedDataTableCellGroupLayout_cellGroup")
        if EXPENSE_LINE_NUMBER_COLUMN in row.inner_html() and "Expense lines" in row.inner_html()
    )

    line_number_checkbox = line_number_column.query_selector("span.dyn-checkbox-span")

    if not line_number_checkbox.is_checked():
        line_number_checkbox.click()

    # endregion

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
    existing_expenses.to_csv(existing_expenses_path, index=False)
    # endregion

    if existing_expenses.shape[0]:
        print("""Found existing expenses""")

        num_expenses_without_receipts = (existing_expenses["Receipts attached"] == "No").sum()

        if num_expenses_without_receipts:
            print(
                dedent(
                    f"""
                    Found {num_expenses_without_receipts} expense(s) without receipts
                    attached.

                    1. Please find the line number of each expense without receipt by
                       looking at the `{EXPENSE_LINE_NUMBER_COLUMN}` column in the
                       spreadsheet saved at {existing_expenses_path.absolute()}. Yes,
                       they are in increments of 2.

                    2. Gather the receipt file(s) you want to attach to the expense(s)
                       and put them in the {RECEIPTS_PATH.absolute()} directory.

                    3. Add the line number as prefix to the receipt file(s) that
                       corresponds to your expense. For example, if your expense with
                       line number `10` had 2 receipts files, `restaurant.jpg` and
                       `bar.jpg`, then rename the files to `10_restaurant.jpg` and
                       `10_bar.jpg`. """,
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
            expense_line_number = int(receipt_file_path.stem.split("_")[0])
            if expense_line_number in existing_expenses[EXPENSE_LINE_NUMBER_COLUMN].values:
                mapped_receipt_files.setdefault(expense_line_number, []).append(receipt_file_path)
            else:
                unmapped_receipt_files.append(receipt_file_path)
        except ValueError:
            unmapped_receipt_files.append(receipt_file_path)

    # Now join back to the pandas dataframe
    mapped_receipt_files_data = (
        pd.Series(mapped_receipt_files, name=RECEIPT_PATHS_COLUMN)
        .reset_index()
        .rename(columns={"index": EXPENSE_LINE_NUMBER_COLUMN})
    )

    existing_expenses_to_update = pd.merge(
        existing_expenses,
        mapped_receipt_files_data,
        on=EXPENSE_LINE_NUMBER_COLUMN,
        how="inner",
    )

    # Now, get all expense lines
    ids_of_expenses_to_update = existing_expenses_to_update["Created ID"].values
    expense_lines = page.get_by_role("textbox", name="Created ID", include_hidden=True).all()

    for expense_line in expense_lines:
        expense_line_id = int(expense_line.get_attribute("value"))

        if expense_line_id not in ids_of_expenses_to_update:
            continue

        # Select the expense line
        expense_line.dispatch_event("click")

        # Now we attach the receipts
        expense_details = existing_expenses_to_update.loc[
            existing_expenses_to_update["Created ID"] == expense_line_id
        ].squeeze()

        for receipt_file_path in expense_details[RECEIPT_PATHS_COLUMN]:
            page.click('a[name="EditReceipts"]')
            page.click('button[name="AddButton"]')

            # Upload receipt
            with page.expect_file_chooser() as file_chooser_info:
                page.click('button[name="UploadControlBrowseButton"]')

            file_chooser = file_chooser_info.value
            file_chooser.set_files(receipt_file_path)

            page.click('button[name="UploadControlUploadButton"]')
            page.click('button[name="OkButtonAddNewTabPage"]')
            page.click('button[name="CloseButton"]')

            page.get_by_text("Save and continue", exact=True).click()

    # # Create new expenses and attach receipts to them
    # page.click('button[name="NewExpenseButton"]')
    # page.wait_for_load_state("networkidle", timeout=10000)

    # page.fill('input[name="CategoryInput"]', category)
    # page.fill('input[name="AmountInput"]', amount)
    # page.fill('input[name="CurrencyInput"]', currency)
    # page.fill('input[name="MerchantInputNoLookup"]', merchant)
    # page.fill('input[name="DateInput"]', date_to_fill.strftime("%-m/%-d/%Y"))
    # page.fill('textarea[name="NotesInput"]', description)

    # page.click('button[name="SaveButton"]')
    # page.wait_for_timeout(3000)

    # # Now we add receipt to the expense
    # receipt_file_paths = ["screenshot.png"]

    # for receipt_file_path in receipt_file_paths:
    #     page.click('a[name="EditReceipts"]')
    #     page.click('button[name="AddButton"]')

    #     # Upload receipt
    #     with page.expect_file_chooser() as file_chooser_info:
    #         page.click('button[name="UploadControlBrowseButton"]')

    #     file_chooser = file_chooser_info.value
    #     file_chooser.set_files(receipt_file_path)

    #     page.click('button[name="UploadControlUploadButton"]')
    #     page.click('button[name="OkButtonAddNewTabPage"]')
    #     page.wait_for_timeout(1000)
    #     page.get_by_text("Close", exact=True).click()

    #     page.get_by_text("Save and continue", exact=True).click()
