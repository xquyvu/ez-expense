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
