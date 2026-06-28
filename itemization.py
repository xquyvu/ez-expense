import asyncio
import logging
import sys
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



async def _wait_for_commit_settled(page: Page, timeout: float = 90_000) -> None:
    """Wait for a post-action ShellBlockingDiv commit overlay to appear, then fully clear.

    Closing the Itemize dialog kicks off a server-side commit of the itemization rows, and
    Dynamics shows the ShellBlockingDiv while it runs — for a hotel with many rows this can
    far exceed the usual 10s budget (observed ~40s). Anything clicked before it clears —
    notably "Save and continue" — is swallowed by the overlay and burns its whole timeout.

    So we first let the overlay *appear* (best-effort, short budget; it may already be up or
    may never show for an instant commit), then wait for it to *disappear* with a generous
    budget, so the next action lands on a settled page.
    """
    try:
        await page.wait_for_selector(
            '[class*="ShellBlockingDiv"]', state="visible", timeout=2_000
        )
    except Exception:
        # Overlay may already be gone or never appear (instant commit); proceed to the
        # hidden-wait regardless.
        pass
    await _wait_for_shell_unblocked(page, timeout=timeout)


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


def _select_all_modifier() -> str:
    """Return the Playwright modifier key for Dynamics' "select all rows" shortcut.

    Dynamics F&O binds the grid "select all" command to Cmd+Shift+M on macOS and
    Ctrl+Shift+M on Windows/Linux. The Edge browser runs on the same host as this
    process, so the process platform is the right one to key off.
    """
    return "Meta" if sys.platform == "darwin" else "Control"


async def _select_all_itemization_rows(page: Page, popup_pane) -> None:
    """Mark every row in the itemization grid in one shot via the keyboard shortcut.

    We click the first data row first so the itemization grid is the active control, then
    fire Dynamics' "select all rows" shortcut (Cmd+Shift+M / Ctrl+Shift+M). This engages
    Dynamics' real row-selection state — unlike clicking a cell's ``<input>``, which only
    moves focus and leaves the Delete button with nothing marked.
    """
    rows = popup_pane.locator(
        "div.fixedDataTableLayout_rowsContainer div.fixedDataTableRowLayout_body"
    )
    # Focus the grid. nth(0) is the header, so nth(1) is the first data row. Clicking the
    # row body (not a specific input) selects the row without dropping into cell-edit mode.
    try:
        await rows.nth(1).click(timeout=15_000)
    except Exception:
        # Fall back to the row's first input if the body itself isn't clickable yet.
        await rows.nth(1).locator("input").first.click(timeout=15_000)
    await page.keyboard.press(f"{_select_all_modifier()}+Shift+M")


async def _clear_existing_itemization_rows(
    page: Page, popup_pane, max_iterations: int = 5
) -> int:
    """Delete every existing itemization row via grid "select all" + a single Delete.

    Returns the number of rows deleted.

    We previously deleted rows one at a time, clicking a cell's hidden ``<input>`` to
    "select" each row — but that only moves focus, it does not engage Dynamics' row-
    selection state, so the Delete button had nothing marked and the server deleted
    nothing (the row count never dropped and we'd give up reporting "deleted 0 of N").
    Instead we use Dynamics' built-in "select all rows" shortcut (Cmd+Shift+M on macOS,
    Ctrl+Shift+M on Windows) to mark the whole group, then click Delete once.

    Reliability strategy:
    1. Before acting, wait for Dynamics' ShellBlockingDiv overlay to clear — while it's up
       the click is silently swallowed and we'd "delete" 0 rows but think we deleted N.
    2. Select all rows, click the group Delete, confirm "Yes" if Dynamics asks.
    3. **Wait for the data-row count to actually drop** below the value observed before the
       click — the only reliable signal the server committed the deletion (the confirm
       dialog closes synchronously, but the grid only re-renders once the server replies).
    4. If the count never drops within ``_delete_settle_timeout``, raise — never close the
       dialog with stale rows, because the parent expense re-saves them under a fresh
       itemization batch ID and they reappear in the report grid as orphans.

    ``max_iterations`` bounds the number of select-all+Delete passes (one normally clears
    the whole group; extra passes only guard against a partial server commit).
    """
    delete_button = popup_pane.locator("button[name='DeleteButtonItemizationGroup']")
    # Per-delete timeout: Dynamics' server commit for a saved itemization group can take
    # 5–15s under load. 30s gives generous headroom without hanging the fill forever.
    _delete_settle_timeout = 30_000

    initial = await _itemization_data_row_count(popup_pane)
    if initial == 0:
        return 0
    logger.info(
        "[itemize] Found %d existing itemization row(s); clearing via select-all + Delete",
        initial,
    )

    for iteration in range(max_iterations):
        # Step 1: ensure the page isn't blocked on a prior server op.
        await _wait_for_shell_unblocked(page, timeout=_delete_settle_timeout)

        # Step 2: re-read the current row count (loop terminator).
        current = await _itemization_data_row_count(popup_pane)
        if current == 0:
            break

        # Step 3: mark every row in one shot.
        try:
            await _select_all_itemization_rows(page, popup_pane)
        except Exception as exc:
            logger.warning(
                "[itemize] Select-all failed on pass %d (rows still showing: %d): %s",
                iteration + 1,
                current,
                exc,
            )
            await page.wait_for_timeout(500)
            continue

        # Step 4: click the group Delete button. Generous timeout so Playwright's
        # auto-retry sees through any ShellBlockingDiv that briefly intercepts events.
        try:
            await delete_button.click(timeout=15_000)
        except Exception as exc:
            logger.warning(
                "[itemize] Delete button click failed on pass %d "
                "(rows still showing: %d): %s",
                iteration + 1,
                current,
                exc,
            )
            await page.wait_for_timeout(500)
            continue

        # Step 5: confirm "Yes" if Dynamics asks (deleting committed rows triggers a
        # confirmation dialog). Wait long enough that a slow confirm dialog doesn't get
        # missed — if we proceed without clicking Yes, the delete is silently cancelled.
        try:
            yes_button = page.get_by_role("button", name="Yes", exact=True)
            await yes_button.wait_for(state="visible", timeout=5_000)
            await yes_button.click()
        except Exception:
            # No confirmation dialog (e.g. only unsaved rows were selected). Continue.
            pass

        # Step 6: WAIT for the row count to actually drop. This is the only reliable
        # signal that the server committed the deletion. Closing the dialog before this
        # commit lands re-saves the parent expense with the stale rows.
        try:
            new_count = await _wait_for_itemization_row_count_below(
                popup_pane, threshold=current, timeout=_delete_settle_timeout
            )
        except PlaywrightTimeoutError as exc:
            still = await _itemization_data_row_count(popup_pane)
            overlay_up = await _overlay_visible(page)
            logger.error(
                "[itemize] Row count did not drop after select-all + Delete on pass %d "
                "(was %d, still %d, overlay=%s). Refusing to close the dialog with stale "
                "rows — caller must handle.",
                iteration + 1,
                current,
                still,
                overlay_up,
                exc_info=False,
            )
            raise RuntimeError(
                f"Itemization delete did not commit (row count stuck at {still}). "
                f"Cleared {initial - still} of {initial} rows before failure."
            ) from exc

        logger.debug(
            "[itemize] Select-all delete pass %d ok: %d → %d rows",
            iteration + 1,
            current,
            new_count,
        )
    else:
        # max_iterations exhausted without count == 0. Should never happen for a real
        # itemization, but raise loudly rather than commit a partial.
        final = await _itemization_data_row_count(popup_pane)
        if final > 0:
            raise RuntimeError(
                f"Did not reach 0 itemization rows after {max_iterations} select-all "
                f"passes ({final} still remain)"
            )

    final = await _itemization_data_row_count(popup_pane)
    deleted = initial - final
    logger.info(
        "[itemize] Cleared %d existing itemization row(s); %d remain (target: 0)",
        deleted,
        final,
    )
    return deleted


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
    # Closing kicks off a server-side commit of the rows (ShellBlockingDiv overlay), which
    # for a hotel with many rows can take far longer than the usual 10s. Wait for that
    # commit to finish before returning so the caller's "Save and continue" click isn't
    # swallowed by the overlay (the cause of the 30s click timeout).
    await _wait_for_commit_settled(page)


async def _open_actions_flyout(page: Page, strategy: str = "normal") -> str:
    """Click the per-expense-line Actions button to open its flyout.

    Returns the selector label that was clicked. ``strategy`` escalates *how* the click is
    delivered so a swallowed/intercepted click can still register:

    * ``"normal"`` – a real Playwright click (full actionability checks).
    * ``"force"``  – ``click(force=True)``: skips the "receives events" check so an
      invisible hovering element can't intercept the click.
    * ``"js"``     – ``dispatch_event("click")``: fires a synthetic click straight at the
      node, bypassing hit-testing entirely (defeats a transparent overlay).

    Always waits for the ShellBlockingDiv overlay to clear first. Raises if no Actions
    selector resolves at all.

    NOTE: a successful return does NOT guarantee the flyout opened — Dynamics frequently
    accepts the click with no effect while it is mid round-trip. The caller MUST verify by
    looking for the Itemize item (see ``_find_visible_itemize``).

    Selector order prefers the **per-expense-line** Actions button
    (``CardBottomMenuFormMenuButtonControl``) over the generic accessible name, which on the
    report detail page also matches the page-level "Actions" toolbar button (``MoreActions``)
    whose menu has no Itemize item.
    """
    await _wait_for_shell_unblocked(page)
    candidates = [
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
    last_err: Exception | None = None
    for label, loc in candidates:
        try:
            target = loc.first
            await target.scroll_into_view_if_needed(timeout=3_000)
            if strategy == "force":
                await target.click(force=True, timeout=8_000)
            elif strategy == "js":
                await target.dispatch_event("click")
            else:
                await target.click(timeout=8_000)
            return label
        except Exception as exc:  # noqa: BLE001 - fall through to the next selector
            last_err = exc
            continue
    raise last_err or RuntimeError("No Actions button selector resolved")


async def _find_visible_itemize(
    candidates, primary_timeout: float = 2_000, fallback_timeout: float = 400
):
    """Return ``(label, locator)`` for the first visible Itemize control, else ``(None, None)``.

    Uses a SHORT budget so a swallowed flyout is detected in seconds — the old code waited
    3 × 15s = 45s for an Itemize item that wasn't there. The first candidate (the stable
    ``ItemizeExpenseButton`` control name) gets ``primary_timeout``; the accessible-name
    fallbacks get the smaller ``fallback_timeout`` because if the flyout is open at all the
    primary already resolves.
    """
    for index, (label, loc) in enumerate(candidates):
        timeout = primary_timeout if index == 0 else fallback_timeout
        try:
            await loc.first.wait_for(state="visible", timeout=timeout)
            return label, loc.first
        except PlaywrightTimeoutError:
            continue
    return None, None


async def _actions_flyout_open(page: Page) -> bool:
    """True when a per-line Actions flyout/menu is currently open.

    Used to decide whether pressing Escape is safe: Escape with no flyout open lands on the
    Dynamics expense-report form and closes it, navigating back to the workspace.
    """
    try:
        return await page.evaluate(
            """() => {
                const menu = document.querySelector('[role="menu"]');
                if (menu && menu.offsetParent !== null) return true;
                const item = document.querySelector(
                    "button[name='ItemizeExpenseButton'], button[name='SplitExpenseButton']"
                );
                return !!(item && item.offsetParent !== null);
            }"""
        )
    except Exception:
        return False


async def _dismiss_flyout_if_open(page: Page) -> None:
    """Press Escape to close an Actions flyout, but ONLY if one is actually open.

    Pressing Escape blindly is what caused the "taken back to another page" failures: when
    the Actions click was swallowed there was no flyout, so Escape closed the expense-report
    form itself and Dynamics navigated back to the workspace.
    """
    if await _actions_flyout_open(page):
        try:
            await page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001 - best-effort dismissal
            pass


async def click_itemize_button(page: Page) -> None:
    """Open the Itemize dialog by clicking Actions → Itemize on the open expense line.

    Reliability model — *verify the flyout, don't trust the click*:
    1. Wait for the Dynamics ``ShellBlockingDiv`` overlay before each click; while it's
       present the page swallows the click and the menu never opens.
    2. The per-line Actions click frequently returns success (~0.2s, no exception) yet the
       flyout never opens because Dynamics is mid round-trip right after the line was
       selected. So success is measured by *Itemize becoming visible* on a short budget —
       not by the click returning. If it doesn't appear we re-open Actions with an
       escalating delivery (normal → force → JS-dispatch) after letting the page settle.
    3. Use the stable ``control-name`` attribute (``ItemizeExpenseButton``) as the primary
       selector and fall back to the accessible name only if that locator never resolves.
    4. Never press Escape unless a flyout is actually open — on the bare report form Escape
       closes the form and navigates back to the workspace.
    5. Verbose timing + reason logs so a hang is diagnosable instead of opaque.
    """
    overall_start = time.monotonic()
    logger.info("[itemize] click_itemize_button: start")

    # Phases 1+2 (merged): open the Actions flyout AND verify it opened by finding the
    # Itemize menu item on a short budget. See the docstring for why the click's return
    # value is not trusted — Itemize becoming visible is the only success signal.
    open_start = time.monotonic()
    itemize_candidates = [
        ("button[name='ItemizeExpenseButton']", page.locator("button[name='ItemizeExpenseButton']")),
        (
            "role=menuitem name=Itemize",
            page.get_by_role("menuitem", name="Itemize", exact=True),
        ),
        ("role=button name=Itemize", page.get_by_role("button", name="Itemize", exact=True)),
    ]
    # Escalate the click delivery as attempts progress: a settled normal re-click fixes the
    # common timing race; force / JS-dispatch defeat a rarer intercepting overlay.
    open_strategies = ["normal", "normal", "force", "js", "force"]
    chosen_label = None
    chosen_locator = None
    for index, strategy in enumerate(open_strategies):
        if index > 0:
            # Only dismiss a flyout that is actually open — a blind Escape on the bare form
            # closes it and navigates back to the workspace. Then let the post-round-trip
            # re-render settle before re-opening Actions.
            await _dismiss_flyout_if_open(page)
            await _wait_for_shell_unblocked(page)
            await page.wait_for_timeout(600)
        try:
            opened_via = await _open_actions_flyout(page, strategy)
        except Exception as exc:  # noqa: BLE001 - record and try the next strategy
            logger.debug(
                "[itemize] Actions open via %s strategy failed on attempt %d: %s",
                strategy,
                index + 1,
                exc,
            )
            continue
        # Brief settle, then verify the flyout truly opened.
        await page.wait_for_timeout(250)
        chosen_label, chosen_locator = await _find_visible_itemize(
            itemize_candidates, primary_timeout=2_000, fallback_timeout=400
        )
        if chosen_locator is not None:
            logger.info(
                "[itemize] Actions flyout opened via %s (%s strategy) on attempt %d; "
                "Itemize visible (%.2fs)",
                opened_via,
                strategy,
                index + 1,
                time.monotonic() - open_start,
            )
            break
        logger.warning(
            "[itemize] Actions click via %s (%s strategy) did not open the flyout "
            "(attempt %d/%d) — Itemize not visible; re-opening.",
            opened_via,
            strategy,
            index + 1,
            len(open_strategies),
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
            "[itemize] Could not open the Actions flyout with an Itemize item after %d "
            "attempts. Visible buttons/menuitems (top 25): %s",
            len(open_strategies),
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
