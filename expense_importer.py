from pathlib import Path

import pandas as pd
from playwright.sync_api import Page

EXPENSE_LINE_NUMBER_COLUMN = "Line number"


def import_expense() -> pd.DataFrame:
    """
    Import expenses from a website and return them as a pandas DataFrame.
    """
    # Logic to interact with the website and fetch expenses
    # This is a placeholder for the actual implementation
    expenses = [
        {"Created ID": 4, "Amount": 100.0, "Description": "Office Supplies"},
        {"Created ID": 2, "Amount": 250.0, "Description": "Travel Expenses"},
    ]

    expense_df = pd.DataFrame(expenses)

    # No need to save to file since we return the DataFrame
    # The calling code can decide what to do with the data
    return expense_df


def import_expense_my_expense(page: Page, save_path: Path | None = None) -> pd.DataFrame:
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

    existing_expenses = pd.read_excel(download_info.value.url)

    if save_path:
        existing_expenses.to_csv(save_path, index=False)

    # endregion

    return existing_expenses
