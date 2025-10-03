import types

import pandas as pd
from playwright.async_api import Page


def prime_and_locals(coro):
    """
    Advance `coro` to its first await and return its locals without running the event loop.
    Useful to inspect internal state before any real async I/O happens.
    """
    if not isinstance(coro, types.CoroutineType):
        raise TypeError("Pass a coroutine object, e.g., some_async_fn(...), not the function.")
    try:
        # Run synchronously until the first `await` (or completion).
        coro.send(None)
    except StopIteration as e:
        return {"finished": True, "result": e.value, "locals": {}}
    frame = coro.cr_frame
    return {"finished": False, "locals": dict(frame.f_locals), "coro": coro}


async def itemize_hotel_invoice(page: Page, itemized_data: pd.DataFrame) -> None:
    pass


async def click_itemize_button(page: Page) -> None:
    # Click on the Actions button (try multiple selectors for reliability)
    try:
        # First try by accessible name
        await page.get_by_role("button", name="Actions").click()
    except Exception:
        try:
            # Fallback to name attribute
            await page.locator("button[name='CardBottomMenuFormMenuButtonControl']").click()
        except Exception:
            # Final fallback to ID
            await page.locator(
                "#ExpenseReportDetails_5_CardBottomMenuFormMenuButtonControl_button"
            ).click()

    itemize_button = page.get_by_role("menuitem", name="ItemizeExpenseButton")
    await itemize_button.wait_for(state="visible")
    await itemize_button.click()

    # Wait for the dialog popup to be visible
    await page.locator("div.dialog-popup.conductorContent").wait_for(state="visible")


def get_itemization_data():
    return pd.DataFrame(
        {"Subcategory": ["Hotel"], "Start date": ["1/10/2025"], "Amount": [500], "Quantity": [1]}
    )
