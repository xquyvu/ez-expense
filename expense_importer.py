from pathlib import Path

import numpy as np
import pandas as pd
from playwright.async_api import Page

import playwright_manager
from config import DEBUG
from resource_utils import load_env_file

load_env_file()


def set_expense_page(page: Page | None = None) -> None:
    """
    Set the global Expense page instance for use by the expense importer.

    Args:
        page: The page instance to set
    """
    # All page management is now handled by playwright_manager
    playwright_manager.set_current_page(page)


def get_expense_page() -> Page | None:
    """Get the global Expense page instance."""
    # All page management is now handled by playwright_manager
    return playwright_manager.get_current_page()


def split_currency_and_amount(expense_df: pd.DataFrame) -> pd.DataFrame:
    expense_df[["Amount", "Currency"]] = expense_df["Amount"].str.split(" ", expand=True)
    expense_df["Amount"] = expense_df["Amount"].str.replace(",", "", regex=True).astype(float)

    return expense_df


def postprocess_expense_data(expense_df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-process the imported expense data to ensure it matches the expected format.

    Args:
        expense_df: DataFrame containing the raw imported expense data

    Returns:
        DataFrame containing the post-processed expense data
    """
    expense_df = expense_df.replace({np.nan: None})
    expense_df["Date"] = expense_df["Date"].dt.date.astype(str)

    expense_df = split_currency_and_amount(expense_df)

    return expense_df


def import_expense_mock(page: Page | None = None) -> pd.DataFrame:
    """
    Import expenses from a website and return them as a pandas DataFrame.
    """
    # Logic to interact with the website and fetch expenses
    # This is a placeholder for the actual implementation
    expense_df = pd.read_excel("./tests/test_data/test_expense_report.xlsx")
    expense_df = postprocess_expense_data(expense_df)

    # No need to save to file since we return the DataFrame
    # The calling code can decide what to do with the data
    return expense_df


async def import_expense_my_expense(page: Page, save_path: Path | None = None) -> pd.DataFrame:
    # Find the "New expense report button"
    if not await page.query_selector('*[data-dyn-controlname="NewExpenseButton"]'):
        raise ValueError("Please make sure you have navigated to an existing expense report")

    # region: Open the column selection dialog
    await page.get_by_role("button", name="Grid options").click()
    await page.get_by_title("Insert columns...").click()

    # Navigate to the column selection dialog - wait for it to appear
    await page.wait_for_selector("div.dialog-popup-content", timeout=10000)
    dialog_content = await page.query_selector("div.dialog-popup-content")

    # region: Show expense description / biz purpose
    expense_desc_rows = await dialog_content.query_selector_all(
        "div.fixedDataTableCellGroupLayout_cellGroup"
    )

    # Find the expense description column using async loop
    for row in expense_desc_rows:
        row_html = await row.inner_html()
        if (
            "Additional information (Expense Description / Business Purpose)" in row_html
            and "Expense lines" in row_html
        ):
            expense_desc_column = row
            break

    expense_desc_checkbox = await expense_desc_column.query_selector("span.dyn-checkbox-span")

    await expense_desc_checkbox.set_checked(True)

    # endregion

    # region: Show the Created ID column, which we will use to identify which expense to

    # click on in the tool
    # Filter for the Created ID column
    await page.fill('input[name="QuickFilterControl_Input"]', "Created ID")
    await page.wait_for_selector("li.quickFilter-listItem.flyout-menuItem")
    await page.keyboard.press("Enter")

    # Uncheck all Created ID columns
    dialog_content_rows = await dialog_content.query_selector_all(
        "div.fixedDataTableCellGroupLayout_cellGroup"
    )
    created_id_columns = []
    for row in dialog_content_rows:
        row_html = await row.inner_html()
        if "Created ID" in row_html:
            created_id_columns.append(row)

    for created_id_column in created_id_columns:
        created_id_checkbox = await created_id_column.query_selector("span.dyn-checkbox-span")
        column_html = await created_id_column.inner_html()

        if "Expense lines" in column_html:
            # Check the one that's corresponding to "Expense lines"
            await created_id_checkbox.set_checked(True)
        else:
            # Uncheck everything else
            await created_id_checkbox.set_checked(False)

    # endregion

    await page.click('button[data-dyn-controlname="OK"]')

    # region: Export the list of existing expenses
    async with page.expect_download() as download_info:
        await page.click('button[name="MoreActions"]')
        await page.click('button[name="ExportToExcel"]')
        await page.click('button[name="DownloadButton"]')

    download = await download_info.value
    existing_expenses = pd.read_excel(download.url)
    existing_expenses = postprocess_expense_data(existing_expenses)

    if save_path:
        existing_expenses.to_csv(save_path, index=False)

    # endregion

    # region: Uncheck the additional information column
    # Open the column selector again
    await page.get_by_role("button", name="Grid options").click()
    await page.get_by_title("Insert columns...").click()

    # Navigate to the column selection dialog - wait for it to appear
    await page.wait_for_selector("div.dialog-popup-content", timeout=10000)
    dialog_content = await page.query_selector("div.dialog-popup-content")

    expense_desc_rows = await dialog_content.query_selector_all(
        "div.fixedDataTableCellGroupLayout_cellGroup"
    )

    # Find the expense description column using async loop
    for row in expense_desc_rows:
        row_html = await row.inner_html()
        if (
            "Additional information (Expense Description / Business Purpose)" in row_html
            and "Expense lines" in row_html
        ):
            expense_desc_column = row
            break

    expense_desc_checkbox = await expense_desc_column.query_selector("span.dyn-checkbox-span")

    await expense_desc_checkbox.set_checked(False)
    await page.click('button[data-dyn-controlname="OK"]')

    # My Expense requires us to reload the page for some reason. This is the poor man's way to do it.
    await page.click('button[name="CommandButtonNext"]')

    # endregion

    return existing_expenses


async def import_expense_wrapper(
    page: Page | None = None, save_path: Path | None = None
) -> pd.DataFrame:
    """
    Wrapper function that handles both DEBUG and non-DEBUG modes.
    In DEBUG mode, it uses the mock function.
    In non-DEBUG mode, it uses the real implementation with the Expense page.
    """
    if DEBUG:
        return import_expense_mock(page)

    # Use the provided page or get from the shared playwright manager
    expense_page = page if page is not None else get_expense_page()

    if expense_page is None:
        raise RuntimeError(
            "Expense page not available. Make sure the browser session is initialized."
        )
    return await import_expense_my_expense(expense_page, save_path)
