from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Page

import playwright_manager
from config import DEBUG

load_dotenv()


def set_playwright_page(page: Page | None = None) -> None:
    """
    Set the global Playwright page instance for use by the expense importer.

    Args:
        page: The page instance to set
        playwright_instance: Legacy parameter, ignored (playwright_manager handles this)
    """
    # All page management is now handled by playwright_manager
    playwright_manager.set_current_page(page)


def get_playwright_page() -> Page | None:
    """Get the global Playwright page instance."""
    # All page management is now handled by playwright_manager
    return playwright_manager.get_current_page()


def import_expense_mock(page: Page | None = None) -> pd.DataFrame:
    """
    Import expenses from a website and return them as a pandas DataFrame.
    """
    # Logic to interact with the website and fetch expenses
    # This is a placeholder for the actual implementation
    expense_df = pd.read_csv("./tests/test_data/test_expense_report.csv")
    expense_df.replace({np.nan: None}, inplace=True)

    # No need to save to file since we return the DataFrame
    # The calling code can decide what to do with the data
    return expense_df


def import_expense_my_expense(page: Page, save_path: Path | None = None) -> pd.DataFrame:
    # region: Open the column selection dialog
    page.get_by_role("button", name="Grid options").click()
    page.get_by_text("Insert columns...").click()

    # Navigate to the column selection dialog - wait for it to appear
    page.wait_for_selector("div.dialog-popup-content", timeout=10000)
    dialog_content = page.query_selector("div.dialog-popup-content")

    # region: Show expense description / biz purpose
    expense_desc_column = next(
        row
        for row in dialog_content.query_selector_all("div.fixedDataTableCellGroupLayout_cellGroup")
        if "Additional information (Expense Description / Business Purpose)" in row.inner_html()
        and "Expense lines" in row.inner_html()
    )

    expense_desc_checkbox = expense_desc_column.query_selector("span.dyn-checkbox-span")

    if not expense_desc_checkbox.is_checked():
        expense_desc_checkbox.click()

    # endregion

    # region: Show the Created ID column, which we will use to identify which expense to

    # click on in the tool
    # Filter for the Created ID column
    page.fill('input[name="QuickFilterControl_Input"]', "Created ID")
    page.wait_for_selector("li.quickFilter-listItem.flyout-menuItem")
    page.keyboard.press("Enter")

    # Uncheck all Created ID columns
    created_id_columns = [
        row
        for row in dialog_content.query_selector_all("div.fixedDataTableCellGroupLayout_cellGroup")
        if "Created ID" in row.inner_html()
    ]

    for created_id_column in created_id_columns:
        created_id_checkbox = created_id_column.query_selector("span.dyn-checkbox-span")

        if "Expense lines" in created_id_column.inner_html():
            # Check the one that's corresponding to "Expense lines"
            created_id_checkbox.set_checked(True)
        else:
            # Uncheck everything else
            created_id_checkbox.set_checked(False)

    # endregion

    page.click('button[data-dyn-controlname="OK"]')

    # region: Export the list of existing expenses
    with page.expect_download() as download_info:
        page.click('button[name="MoreActions"]')
        page.get_by_text("Export to Microsoft Excel", exact=True).click()
        page.click('button[name="DownloadButton"]')

    existing_expenses = pd.read_excel(download_info.value.url)
    existing_expenses.replace({np.nan: None}, inplace=True)

    if save_path:
        existing_expenses.to_csv(save_path, index=False)

    # endregion

    return existing_expenses


def import_expense_wrapper(page: Page | None = None, save_path: Path | None = None) -> pd.DataFrame:
    """
    Wrapper function that handles both DEBUG and non-DEBUG modes.
    In DEBUG mode, it uses the mock function.
    In non-DEBUG mode, it uses the real implementation with the Playwright page.
    """
    if DEBUG:
        return import_expense_mock(page)

    # Use the provided page or get from the shared playwright manager
    playwright_page = page if page is not None else get_playwright_page()

    if playwright_page is None:
        raise RuntimeError(
            "Playwright page not available. Make sure the browser session is initialized."
        )
    return import_expense_my_expense(playwright_page, save_path)
