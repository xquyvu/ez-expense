from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Page

import playwright_manager
from config import DEBUG, EXPENSE_LINE_NUMBER_COLUMN

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


def cleanup_playwright_connection():
    """Clean up the existing Playwright connection."""
    # All cleanup is now handled by playwright_manager
    playwright_manager.stop_playwright()


def import_expense_mock(page: Page | None = None) -> pd.DataFrame:
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


def import_expense_wrapper(page: Page | None = None, save_path: Path | None = None) -> pd.DataFrame:
    """
    Wrapper function that handles both DEBUG and non-DEBUG modes.
    In DEBUG mode, it uses the mock function.
    In non-DEBUG mode, it uses the real implementation with the Playwright page.
    """
    if DEBUG:
        return import_expense_mock(page)

    # Get the page from parameter or global state
    playwright_page = page if page is not None else get_playwright_page()

    # If we have a cached page, try to validate it's still usable
    if playwright_page is not None:
        try:
            # Simple check to see if the page is still responsive
            _ = playwright_page.url
        except Exception:
            # Page is no longer valid, clear it and reconnect
            playwright_page = None
            cleanup_playwright_connection()

    # If no page is available or the cached page failed, try to connect to the browser session
    if playwright_page is None:
        playwright_page = _try_connect_to_browser()

    if playwright_page is None:
        raise RuntimeError(
            "Playwright page not available. Make sure the browser session is initialized."
        )
    return import_expense_my_expense(playwright_page, save_path)


def _try_connect_to_browser() -> Page | None:
    """
    Attempt to connect to an existing browser session running in debug mode.
    This allows the Flask subprocess to access the browser started by main.py.
    Uses the centralized playwright_manager to prevent threading issues.
    """
    try:
        from config import EXPENSE_APP_URL

        # Clean up any existing connections first
        cleanup_playwright_connection()

        # Use playwright manager to create and connect
        if not playwright_manager.is_playwright_running():
            playwright_manager.start_playwright()

        browser = playwright_manager.connect_to_browser()

        # Find the expense management page
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        for page in context.pages:
            if EXPENSE_APP_URL in page.url:
                # Set the page using playwright_manager
                set_playwright_page(page)
                return page

        # If no existing page found, create a new one
        page = context.new_page()
        page.goto(f"https://{EXPENSE_APP_URL}")
        set_playwright_page(page)
        return page

    except Exception as e:
        # Clean up on failure
        cleanup_playwright_connection()

        # Log the error but don't crash - let the caller handle it
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to connect to browser from Flask process: {e}")
        return None
