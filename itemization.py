import asyncio
import logging
import time
import types

import pandas as pd
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Selector for the itemization dialog's popup pane (the modal containing the grid).
_POPUP_PANE_SELECTOR = (
    "div.rootLayout.rootLayout-dialog.fill-width.fill-height.layout-container.layout-vertical"
)
# Columns we fill on each itemization row, matching the dialog's input aria-labels.
_ITEMIZATION_FIELDS = ["Subcategory", "Start date", "Daily rate", "Quantity"]


async def _wait_for_shell_unblocked(page: Page, timeout: float = 10_000) -> None:
    """Wait for Dynamics' ShellBlockingDiv loading overlay to clear.

    While that overlay is present the page swallows clicks (Actions, Itemize, Browse, etc.),
    so we wait for it to disappear before interacting. Mirrors the helper the fill flow uses;
    if the overlay isn't present this resolves immediately.
    """
    try:
        await page.wait_for_selector(
            '[class*="ShellBlockingDiv"]', state="hidden", timeout=timeout
        )
    except Exception:
        # Overlay may simply not exist on this page/state; proceed regardless.
        pass


async def _overlay_visible(page: Page) -> bool:
    """True while the Dynamics blocking overlay is shown (a server op is in flight).

    Uses ``getComputedStyle`` + ``offsetParent`` so a hidden-but-present overlay node
    (Dynamics keeps it in the DOM) is correctly reported as not blocking.
    """
    try:
        return await page.evaluate(
            """() => {
                const e = document.querySelector('#ShellBlockingDiv')
                    || document.querySelector('[class*="ShellBlockingDiv"]');
                if (!e) return false;
                const s = getComputedStyle(e);
                return s.display !== 'none' && s.visibility !== 'hidden' && e.offsetParent !== null;
            }"""
        )
    except Exception:
        return False



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


def _format_field_value(value) -> str:
    """Render a cell value as the dialog expects (drop trailing .0 on whole numbers)."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


async def _itemization_data_row_count(popup_pane) -> int:
    """Return the count of data rows in the itemization grid (excluding the header row).

    The grid renders ``fixedDataTableRowLayout_body`` per logical row, plus one for the
    header. So data rows = total bodies − 1.
    """
    total = await popup_pane.locator(
        "div.fixedDataTableLayout_rowsContainer div.fixedDataTableRowLayout_body"
    ).count()
    return max(0, total - 1)


async def _wait_for_itemization_row_count_below(
    popup_pane, threshold: int, timeout: float = 30_000
) -> int:
    """Poll until the dialog's data-row count drops below ``threshold``, returning the new count.

    Raises ``PlaywrightTimeoutError`` if the count never drops within ``timeout`` ms — the
    caller must surface this rather than silently closing the dialog with stale rows (that
    would commit a partial itemization the parent expense re-saves as an orphan group).
    """
    deadline = time.monotonic() + (timeout / 1000)
    last = await _itemization_data_row_count(popup_pane)
    while time.monotonic() < deadline:
        if last < threshold:
            return last
        await asyncio.sleep(0.25)
        last = await _itemization_data_row_count(popup_pane)
    if last < threshold:
        return last
    raise PlaywrightTimeoutError(
        f"Itemization row count did not drop below {threshold} within {timeout:.0f}ms "
        f"(still {last})"
    )


async def _clear_existing_itemization_rows(
    page: Page, popup_pane, max_iterations: int = 100
) -> int:
    """Delete every existing itemization row until the grid contains only the header.

    Returns the number of rows deleted. Loops on the *current* data-row count (re-read
    each iteration), not a pre-computed total — so we drain reliably regardless of how
    many rows the dialog opened with.

    Reliability strategy (no retries, no stall heuristics):
    1. Before each click, wait for Dynamics' ShellBlockingDiv overlay to clear — while
       it's up the click is silently swallowed and we'd "delete" 0 rows but think we
       deleted N.
    2. After clicking Delete + confirming "Yes", **wait for the data-row count to
       actually drop** below the value we observed before the click. That's the only
       reliable signal the delete was committed by the server (the confirm dialog
       closes synchronously, but the grid only re-renders once the server replies).
    3. If the count never drops within ``_delete_settle_timeout``, raise — never close
       the dialog with stale rows, because the parent expense re-saves them under a
       fresh itemization batch ID and they reappear in the report grid as orphans.
    """
    delete_button = popup_pane.locator("button[name='DeleteButtonItemizationGroup']")
    rows = popup_pane.locator(
        "div.fixedDataTableLayout_rowsContainer div.fixedDataTableRowLayout_body"
    )
    # Per-delete timeout: Dynamics' server commit for a saved itemization row can take
    # 5–15s under load. 30s gives generous headroom without hanging the fill forever.
    _delete_settle_timeout = 30_000

    initial = await _itemization_data_row_count(popup_pane)
    if initial == 0:
        return 0
    logger.info(
        "[itemize] Found %d existing itemization row(s); draining before fill", initial
    )

    deletions = 0
    for iteration in range(max_iterations):
        # Step 1: ensure the page isn't blocked on a prior server op.
        await _wait_for_shell_unblocked(page, timeout=_delete_settle_timeout)

        # Step 2: re-read the current row count (loop terminator).
        current = await _itemization_data_row_count(popup_pane)
        if current == 0:
            break

        # Step 3: activate the first data row. The "Created ID" cell is a hidden input,
        # so we click any visible input inside the row's body to drive Dynamics'
        # row-selection state. nth(0) is the header, so nth(1) is the first data row.
        # Generous timeout because the ShellBlockingDiv from a prior server commit can
        # transiently intercept pointer events; Playwright auto-retries through it.
        try:
            await rows.nth(1).locator("input").first.click(timeout=15_000)
        except Exception as exc:
            logger.warning(
                "[itemize] Could not activate first data row on iteration %d "
                "(rows still showing: %d): %s",
                iteration + 1,
                current,
                exc,
            )
            # Brief settle, then re-loop; we re-read the count and will retry the
            # same iteration. If activation keeps failing across iterations the
            # row-count-drop wait below will catch it the next time.
            await page.wait_for_timeout(500)
            continue

        # Step 4: click the group Delete button. Generous timeout so Playwright's
        # auto-retry sees through any ShellBlockingDiv that briefly intercepts events
        # right after row selection.
        try:
            await delete_button.click(timeout=15_000)
        except Exception as exc:
            logger.warning(
                "[itemize] Delete button click failed on iteration %d "
                "(rows still showing: %d): %s",
                iteration + 1,
                current,
                exc,
            )
            await page.wait_for_timeout(500)
            continue

        # Step 5: confirm "Yes" if Dynamics asks (committed rows trigger this; the
        # auto-populated unsaved first row does not). Wait long enough that a slow
        # confirm dialog doesn't get missed — if we proceed without clicking Yes, the
        # delete is silently cancelled.
        try:
            yes_button = page.get_by_role("button", name="Yes", exact=True)
            await yes_button.wait_for(state="visible", timeout=5_000)
            await yes_button.click()
        except Exception:
            # Unsaved row: no confirmation dialog. Continue.
            pass

        # Step 6: WAIT for the row count to actually drop. This is the only reliable
        # signal that the server committed the deletion. Closing the dialog before
        # this commit lands re-saves the parent expense with the stale rows.
        try:
            new_count = await _wait_for_itemization_row_count_below(
                popup_pane, threshold=current, timeout=_delete_settle_timeout
            )
        except PlaywrightTimeoutError as exc:
            still = await _itemization_data_row_count(popup_pane)
            overlay_up = await _overlay_visible(page)
            logger.error(
                "[itemize] Row count did not drop after delete on iteration %d "
                "(was %d, still %d, overlay=%s, deletions so far=%d). Refusing to "
                "close the dialog with stale rows — caller must handle.",
                iteration + 1,
                current,
                still,
                overlay_up,
                deletions,
                exc_info=False,
            )
            raise RuntimeError(
                f"Itemization delete did not commit (row count stuck at {still}). "
                f"Successfully deleted {deletions} of {initial} rows before failure."
            ) from exc

        deletions += 1
        logger.debug(
            "[itemize] Delete iteration %d ok: %d → %d rows (%d total deleted)",
            iteration + 1,
            current,
            new_count,
            deletions,
        )
    else:
        # max_iterations exhausted without count == 0. Should never happen for a real
        # itemization, but raise loudly rather than commit a partial.
        final = await _itemization_data_row_count(popup_pane)
        raise RuntimeError(
            f"Did not reach 0 itemization rows after {max_iterations} iterations "
            f"(deleted {deletions}, {final} still remain)"
        )

    final = await _itemization_data_row_count(popup_pane)
    logger.info(
        "[itemize] Cleared %d existing itemization row(s); %d remain (target: 0)",
        deletions,
        final,
    )
    return deletions


async def itemize_hotel_invoice(page: Page, itemized_data: pd.DataFrame) -> None:
    """Fill the (already open) itemization dialog from a DataFrame of itemized charges.

    Expects the dialog opened by :func:`click_itemize_button`. ``itemized_data`` columns should
    be a subset of ``Subcategory``, ``Start date``, ``Daily rate``, ``Quantity``. Any existing
    rows are cleared first, then one row is added and filled per record.
    """
    popup_pane = page.locator(_POPUP_PANE_SELECTOR)
    await popup_pane.wait_for(state="visible")

    await _clear_existing_itemization_rows(page, popup_pane)

    new_item_button = popup_pane.locator("button[name='NewButtonItemizationGroup']")

    records = itemized_data.to_dict("records")
    logger.info("Filling %s itemization row(s)", len(records))

    for record in records:
        await new_item_button.click()
        await page.wait_for_load_state("domcontentloaded")

        # The newly added row is the second body row (index 1), after the header row.
        current_row = (
            popup_pane.locator("div.fixedDataTableLayout_rowsContainer")
            .locator("div.fixedDataTableRowLayout_body")
            .nth(1)
        )

        for field in _ITEMIZATION_FIELDS:
            if field not in record:
                continue
            value = _format_field_value(record[field])
            cell = current_row.locator(f'input[aria-label="{field}"]')
            await cell.click()
            await cell.fill(value, timeout=2000)

    # Close the dialog (commits the rows back to the expense line).
    close_button = popup_pane.locator("button[name='CloseButton']")
    try:
        await close_button.wait_for(state="visible", timeout=5000)
    except Exception:
        close_button = page.get_by_role("button", name="Close", exact=True)
    await close_button.click()


async def click_itemize_button(page: Page) -> None:
    """Open the Itemize dialog by clicking Actions → Itemize on the open expense line.

    Reliability hardening (mirrors patterns the fill flow uses for Save and Browse):
    1. Wait for the Dynamics ``ShellBlockingDiv`` overlay before each click; while it's
       present the page swallows the click and the menu never opens.
    2. Retry the Actions click and the Itemize click independently — Dynamics often
       re-renders the action bar mid-fill and the first click becomes non-actionable.
    3. Use the stable ``control-name`` attribute (``ItemizeExpenseButton``) as the primary
       selector and fall back to the accessible name only if that locator never resolves.
    4. Verbose timing + reason logs so a hang is diagnosable instead of opaque.
    5. Final ``force=True`` fallback so an overlapping tooltip / icon can't burn the
       full timeout budget.
    """
    overall_start = time.monotonic()
    logger.info("[itemize] click_itemize_button: start")

    # 1. Open the Actions flyout.
    # IMPORTANT: prefer the **per-expense-line** Actions button (CardBottomMenuFormMenuButtonControl
    # at the bottom of the expense detail card) over the generic accessible-name match,
    # which on the report detail page ALSO matches the page-level "Actions" toolbar button
    # (named MoreActions). Opening the page-level one shows menu items like "Edit expense
    # report" / "Export to Microsoft Excel" — none of which is "Itemize" — and the subsequent
    # Itemize lookup correctly times out. The fix is selector order.
    actions_start = time.monotonic()
    actions_opened = False
    last_actions_err: Exception | None = None
    actions_candidates = [
        (
            'button[name="CardBottomMenuFormMenuButtonControl"]',
            page.locator('button[name="CardBottomMenuFormMenuButtonControl"]'),
        ),
        (
            "#ExpenseReportDetails_5_CardBottomMenuFormMenuButtonControl_button",
            page.locator(
                "#ExpenseReportDetails_5_CardBottomMenuFormMenuButtonControl_button"
            ),
        ),
        ("role=button name=Actions", page.get_by_role("button", name="Actions")),
    ]
    for attempt in range(3):
        for label, loc in actions_candidates:
            try:
                await _wait_for_shell_unblocked(page)
                await loc.first.scroll_into_view_if_needed(timeout=3_000)
                await loc.first.click(timeout=8_000)
                logger.info(
                    "[itemize] Actions clicked via %s on attempt %d (%.2fs)",
                    label,
                    attempt + 1,
                    time.monotonic() - actions_start,
                )
                actions_opened = True
                break
            except Exception as exc:  # noqa: BLE001
                last_actions_err = exc
                logger.debug(
                    "[itemize] Actions click via %s attempt %d failed: %s",
                    label,
                    attempt + 1,
                    exc,
                )
        if actions_opened:
            break
        # Brief settle before retrying the whole candidate list.
        await page.wait_for_timeout(400)

    if not actions_opened:
        # Last resort: force-click the most stable selector. Logs why each variant failed.
        logger.warning(
            "[itemize] Actions menu refused normal clicks (last error: %s); "
            "forcing click on control-name selector.",
            last_actions_err,
        )
        await _wait_for_shell_unblocked(page)
        await page.locator(
            'button[name="CardBottomMenuFormMenuButtonControl"]'
        ).first.click(force=True, timeout=8_000)

    # 2. Click the Itemize menu item in the now-open flyout.
    itemize_start = time.monotonic()
    itemize_candidates = [
        ("button[name='ItemizeExpenseButton']", page.locator("button[name='ItemizeExpenseButton']")),
        (
            "role=menuitem name=Itemize",
            page.get_by_role("menuitem", name="Itemize", exact=True),
        ),
        ("role=button name=Itemize", page.get_by_role("button", name="Itemize", exact=True)),
    ]
    chosen_label = None
    chosen_locator = None
    for label, loc in itemize_candidates:
        try:
            await loc.first.wait_for(state="visible", timeout=15_000)
            chosen_label = label
            chosen_locator = loc.first
            logger.info(
                "[itemize] Itemize menuitem found via %s after %.2fs",
                label,
                time.monotonic() - itemize_start,
            )
            break
        except PlaywrightTimeoutError:
            logger.debug(
                "[itemize] Itemize selector %s not visible within 15s; trying next",
                label,
            )

    if chosen_locator is None:
        # Capture diagnostic state — what menu items *are* visible? — and re-raise so the
        # caller's exception handler still records a failure.
        try:
            visible_items = await page.evaluate(
                """() => Array.from(document.querySelectorAll('[role="menuitem"], button'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => ({
                        text: (el.innerText || el.textContent || '').trim().slice(0, 60),
                        name: el.getAttribute('name') || '',
                        role: el.getAttribute('role') || el.tagName.toLowerCase()
                    }))
                    .filter(x => x.text || x.name)
                    .slice(0, 25)"""
            )
        except Exception:
            visible_items = []
        logger.error(
            "[itemize] Could not find Itemize menu item after Actions opened. "
            "Visible buttons/menuitems (top 25): %s",
            visible_items,
        )
        raise RuntimeError(
            "Itemize menu item not visible after opening Actions. "
            "See ez-expense.log for the menu state captured at failure."
        )

    # Real click first, force-click fallback if Dynamics says it's not actionable yet.
    try:
        await chosen_locator.click(timeout=8_000)
    except PlaywrightTimeoutError:
        logger.warning(
            "[itemize] Itemize click via %s not actionable in 8s; forcing click", chosen_label
        )
        await chosen_locator.click(force=True, timeout=5_000)

    # 3. Wait for the dialog popup. The popup-pane selector is more specific than the
    # generic dialog-popup container, so prefer it — but log if it never appears.
    dialog_start = time.monotonic()
    try:
        await page.locator("div.dialog-popup.conductorContent").wait_for(
            state="visible", timeout=15_000
        )
    except PlaywrightTimeoutError:
        logger.warning(
            "[itemize] dialog-popup.conductorContent never visible in 15s; "
            "falling back to popup-pane selector"
        )
        await page.locator(_POPUP_PANE_SELECTOR).wait_for(state="visible", timeout=10_000)
    logger.info(
        "[itemize] dialog opened in %.2fs (total %.2fs)",
        time.monotonic() - dialog_start,
        time.monotonic() - overall_start,
    )


def get_itemization_data():
    return pd.DataFrame(
        {"Subcategory": ["Hotel"], "Start date": ["1/10/2025"], "Amount": [500], "Quantity": [1]}
    )
