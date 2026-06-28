"""
Expense-related API routes for the Flask application.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

from playwright.async_api import TimeoutError as playwright_TimeoutError
from quart import Blueprint, current_app, jsonify, make_response, request
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import AI_DEBUG, DATE_FORMAT, IMPORT_EXPENSE_MOCK, RECEIPT_EXTENSIONS

# Add the parent directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from expense_importer import get_expense_page, import_expense_wrapper
from expense_matcher import receipt_match_score

# Create blueprint
expense_bp = Blueprint("expenses", __name__)
logger = logging.getLogger(__name__)

# Per-step fill timing diagnostics. Off by default to keep production fill logs clean; set
# EZ_EXPENSE_TIMING=1 (or true/yes) to emit "[timing] ..." lines at INFO level when profiling
# the fill flow (e.g. via scripts/drive_e2e.py). Measured dominant cost is the MyExpense
# receipt-upload dialog round-trips (~6s/receipt), not this app's code.
_TIMING_ENABLED = os.getenv("EZ_EXPENSE_TIMING", "").strip().lower() in ("1", "true", "yes", "on")


def _log_timing(message: str) -> None:
    """Emit a fill step-timing line when EZ_EXPENSE_TIMING is enabled."""
    if _TIMING_ENABLED:
        logger.info(message)


# Guards against concurrent fills. All fills drive the single shared Playwright page, so
# two running at once corrupt each other (the symptom: "File chooser did not appear").
_fill_in_progress = False


async def _wait_for_shell_unblocked(page, timeout: float = 10_000) -> None:
    """Best-effort wait for the Dynamics ShellBlockingDiv loading overlay to clear.

    While that overlay is present it swallows clicks (e.g. on the Browse button), so we
    wait for it to disappear before interacting. If the overlay isn't present this resolves
    immediately.
    """
    try:
        await page.wait_for_selector('[class*="ShellBlockingDiv"]', state="hidden", timeout=timeout)
    except Exception:
        # The overlay may simply not exist on this page/state; proceed regardless.
        pass


async def _locate_expense_line(
    page, created_id: str, max_scrolls: int = 30, known_ids: set | None = None
):
    """Locate an expense line's "Created ID" cell, scrolling the virtualized grid as needed.

    The MyExpense expense grid is a React FixedDataTable: virtualized, windowed at ~25 rows,
    and **owns its own scroll state** (setting ``scrollTop`` on the surrounding DOM has no
    effect — the component restores its own scroll offset on the next render). Worse, its
    ``scrollHeight`` only reflects rendered rows, not the *total* row count, so probes that
    check "are we at the bottom?" by comparing ``scrollTop + clientHeight`` to ``scrollHeight``
    give false positives.

    Strategy: wheel-scroll first (fast and works for moderately-sized grids), then fall back
    to keyboard navigation (clicking the last visible row and pressing ``ArrowDown``, which
    drives Dynamics' own row-selection state and is the only signal the grid reliably
    listens to). Keyboard nav is slower per row but is the only path that works when the
    grid has more rows than its rendered window can hold (e.g. 26 real expenses + a leftover
    itemization batch group from a previous fill).
    """
    created_id = str(created_id)
    target = page.locator(f'input[aria-label="Created ID"][value="{created_id}"]')

    # Returns the rendered Created IDs (so we can detect "no progress" reliably) along
    # with the grid's bounding box so we know where to direct the mouse wheel.
    grid_state_js = """() => {
        const inputs = document.querySelectorAll('input[aria-label="Created ID"]');
        if (!inputs.length) return null;
        // The grid container is the first scrolling ancestor that contains our inputs.
        let el = inputs[0];
        let container = null;
        for (let i = 0; i < 30 && el; i++, el = el.parentElement) {
            if (el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 50) {
                container = el;
                break;
            }
        }
        // Fall back to the closest parent of inputs that actually has size.
        if (!container) {
            container = inputs[0].closest('[role="grid"]') || inputs[0].closest('.fixedDataTableLayout_main');
        }
        const rect = container ? container.getBoundingClientRect() : null;
        const values = [];
        for (const inp of inputs) {
            values.push(inp.getAttribute('value') || inp.value || '');
        }
        return {
            rect: rect ? {
                x: rect.x, y: rect.y, width: rect.width, height: rect.height
            } : null,
            renderedIds: values,
        };
    }"""

    scroll_to_top_js = """() => {
        const inputs = document.querySelectorAll('input[aria-label="Created ID"]');
        if (!inputs.length) return;
        let el = inputs[0];
        for (let i = 0; i < 30 && el; i++, el = el.parentElement) {
            if (el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 50) {
                el.scrollTop = 0;
                return;
            }
        }
    }"""

    start = time.monotonic()

    # Phase 1: wheel scrolling. Fast when it works; bails after a couple of no-progress
    # iterations so we can fall back to keyboard nav.
    previous_ids: tuple = ()
    stale_iters = 0
    for scrolls in range(max_scrolls):
        if await target.count() > 0:
            _log_timing(
                f"[timing] locate {created_id}: {time.monotonic() - start:.2f}s "
                f"({scrolls} wheel scroll(s))"
            )
            return target.first

        state = await page.evaluate(grid_state_js)
        if state is None or state.get("rect") is None:
            logger.warning(
                "[fill-debug] locate %s: grid container not found; skipping wheel phase",
                created_id,
            )
            break

        rect = state["rect"]

        # Dispatch a real mouse-wheel scroll over the grid centre. FixedDataTable handles
        # wheel deltaY in its own scroll state and re-renders the window when it agrees.
        cx = rect["x"] + rect["width"] / 2
        cy = rect["y"] + rect["height"] / 2
        try:
            await page.mouse.move(cx, cy)
            wheel_dy = max(200, int(rect["height"] * 0.8))
            await page.mouse.wheel(0, wheel_dy)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[fill-debug] locate %s: mouse.wheel failed: %s; ending wheel phase",
                created_id,
                exc,
            )
            break
        await page.wait_for_timeout(500)

        # Detect "no progress" by comparing the rendered ID sets between iterations.
        new_state = await page.evaluate(
            "() => Array.from(document.querySelectorAll('input[aria-label=\"Created ID\"]'))"
            ".map(i => i.getAttribute('value') || i.value || '')"
        )
        new_ids = tuple(new_state or ())
        if new_ids == previous_ids:
            stale_iters += 1
            if stale_iters >= 2:
                logger.info(
                    "[fill-debug] locate %s: wheel scrolling stalled after %d attempts "
                    "(lastRendered=%s) — switching to keyboard navigation",
                    created_id,
                    scrolls + 1,
                    new_ids[-1] if new_ids else None,
                )
                break
        else:
            stale_iters = 0
        previous_ids = new_ids

    # Phase 2: keyboard nav fallback. The Dynamics grid responds to keyboard navigation:
    # clicking a row puts the grid in row-selection mode, and ArrowDown moves selection
    # down by one — which auto-scrolls the grid to keep the selected row visible. This is
    # the ONLY signal that reliably renders rows beyond the FixedDataTable's "I'm at the
    # bottom" lie, because the component's scrollTo() is driven by its own selection state.
    keyboard_start = time.monotonic()
    kb_ok = await _keyboard_scroll_until_visible(
        page, target, created_id, known_ids=known_ids
    )
    if kb_ok:
        _log_timing(
            f"[timing] locate {created_id}: {time.monotonic() - start:.2f}s "
            f"(keyboard nav: {time.monotonic() - keyboard_start:.2f}s)"
        )
        return target.first

    # Last resort: scroll to top in case the target sits above the current window.
    await page.evaluate(scroll_to_top_js)
    await page.wait_for_timeout(500)
    if await target.count() > 0:
        _log_timing(
            f"[timing] locate {created_id}: {time.monotonic() - start:.2f}s "
            f"(via scroll-to-top)"
        )
        return target.first

    # Final diagnostic: dump every rendered Created ID so we can see what the grid does
    # contain, in case the target ID is subtly different (whitespace, type coercion, …).
    rendered = await page.evaluate(
        """() => Array.from(document.querySelectorAll('input[aria-label="Created ID"]'))
            .map(i => i.getAttribute('value') || i.value || '')"""
    )
    logger.error(
        "[fill-debug] locate %s: not found after %.1fs. Grid currently shows %d "
        "row(s) with Created IDs: %s",
        created_id,
        time.monotonic() - start,
        len(rendered),
        rendered,
    )

    raise RuntimeError(
        f"Could not locate expense line with Created ID {created_id} after scrolling the grid."
    )


async def _keyboard_scroll_until_visible(
    page, target, created_id: str, max_presses: int = 80, known_ids: set | None = None
) -> bool:
    """Drive Dynamics' grid via keyboard ArrowDown until the target row renders.

    Picks an anchor input from the rendered Created ID cells and clicks it to focus the
    cell, then presses ArrowDown. **Key heuristic**: when the rendered window contains
    hotel-itemization sub-rows (Created IDs that aren't in ``known_ids`` — i.e. weren't
    imported as top-level expenses), clicking the *last* rendered input lands focus inside
    the itemization child table, and subsequent ArrowDown presses navigate within those
    children rather than scrolling the parent grid. We pick the last *known* (non-orphan)
    Created ID instead, so ArrowDown moves down through the parent rows and Dynamics
    auto-scrolls to render the still-virtualised top-level rows below.

    Returns True if the target appears, False if we exhaust the cap.
    """
    # Pick the anchor input. Prefer the last "known" rendered Created ID (a top-level
    # expense from our import) over the literal last rendered input — see docstring.
    anchor_input = None
    try:
        rendered = await page.evaluate(
            "() => Array.from(document.querySelectorAll('input[aria-label=\"Created ID\"]'))"
            ".map(i => i.getAttribute('value') || i.value || '')"
        )
    except Exception:
        rendered = []

    if known_ids and rendered:
        # Walk the rendered list from the back, find the last entry that's a known
        # top-level expense. That's the safest place to focus before pressing ArrowDown.
        for value in reversed(rendered):
            if value in known_ids:
                anchor_input = page.locator(
                    f'input[aria-label="Created ID"][value="{value}"]'
                ).first
                logger.info(
                    "[fill-debug] locate %s: keyboard nav anchored on last known parent row "
                    "Created ID %s (skipped %d trailing orphan row(s))",
                    created_id,
                    value,
                    len(rendered) - 1 - rendered[::-1].index(value),
                )
                break

    if anchor_input is None:
        # No known anchor — fall back to the literal last rendered input.
        anchor_input = page.locator('input[aria-label="Created ID"]').last

    try:
        await anchor_input.evaluate("el => el.scrollIntoView({ block: 'center' })")
        # Click the INPUT itself (not the row container). When the input is focused,
        # ArrowDown navigates to the corresponding column in the next row.
        await anchor_input.click(timeout=5_000)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[fill-debug] locate %s: keyboard nav setup failed (couldn't click anchor input): %s",
            created_id,
            exc,
        )
        return False

    await page.wait_for_timeout(250)

    # Track the last-rendered ID so we can spot when keyboard nav has reached the true
    # grid bottom (the rendered set stops changing).
    previous_last = None
    no_progress = 0
    for press in range(max_presses):
        if await target.count() > 0:
            logger.info(
                "[fill-debug] locate %s: keyboard nav found target after %d ArrowDown press(es)",
                created_id,
                press,
            )
            return True
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(180)

        # Check the last rendered ID; if it hasn't changed across several presses, we've
        # genuinely walked off the bottom of the grid.
        try:
            cur_last = await page.locator(
                'input[aria-label="Created ID"]'
            ).last.get_attribute("value")
        except Exception:
            cur_last = None
        if cur_last == previous_last:
            no_progress += 1
            if no_progress >= 5:
                logger.warning(
                    "[fill-debug] locate %s: keyboard nav stalled at lastRendered=%s after "
                    "%d press(es); giving up",
                    created_id,
                    cur_last,
                    press + 1,
                )
                return False
        else:
            no_progress = 0
        previous_last = cur_last
    return False


async def _open_expense_line(page, expense_line_locator, *, block: str = "nearest") -> bool:
    """Open/select an existing expense line from its "Created ID" grid cell.

    The "Created ID" field itself is a hidden ``<input>``, so a real Playwright click on it
    stalls on actionability. But a *synthetic* JS ``click()`` on the row does not trigger
    Dynamics' row-selection handler (it ignores untrusted events), so the line never gets
    selected and every receipt ends up on whichever line was already open. The fix is to
    issue a **real** mouse click on the enclosing visible grid row: scroll the row into view
    via JS (handles virtualization), then click the ``[role="row"]`` ancestor so Dynamics
    receives genuine pointer events and selects the line.

    Selecting a line makes Dynamics re-render the detail pane, so we then wait for the row
    to actually become selected before returning — a fixed delay races that re-render and
    causes receipts to land on the previously-selected line.

    ``block`` controls the vertical alignment used to scroll the row into view. The default
    ``"nearest"`` keeps the fill loop from re-centering (and visually jumping) on every line.
    Pass ``"center"`` when selecting an arbitrary line *cold* — e.g. a hotel that is the
    FIRST grid row, where a sticky "receipt required" message bar overlaps the top of the
    grid: a ``"nearest"`` scroll leaves that row under the bar so the selecting click misses.

    Returns ``True`` if the row was observed to become selected, ``False`` if it fell through
    to the settle fallback (selection could not be confirmed) so callers can verify/retry.
    """
    open_start = time.monotonic()
    await _wait_for_shell_unblocked(page)
    # Bring the row into view if needed. 'nearest' (the default) scrolls the minimum amount so
    # a line Dynamics just auto-scrolled to after "Save and continue" is not yanked to the
    # middle of the viewport on every expense (that re-centering made the screen jump during a
    # fill). 'center' is used when selecting a line cold, so a sticky top message bar cannot
    # overlap — and swallow the selecting click on — the first grid row.
    await expense_line_locator.evaluate("(el, b) => el.scrollIntoView({ block: b })", block)
    row = expense_line_locator.locator("xpath=ancestor::*[@role='row'][1]")

    # Click the row to select it. The click can transiently fail actionability while the
    # grid/detail pane re-renders, so retry (re-centering + waiting for the overlay) and
    # fall back to a forced click rather than letting one stuck click burn the full timeout.
    click_start = time.monotonic()
    clicked = False
    for attempt in range(3):
        try:
            await row.scroll_into_view_if_needed(timeout=4_000)
        except Exception:  # noqa: BLE001 - scrolling is best-effort
            await expense_line_locator.evaluate("el => el.scrollIntoView({ block: 'center' })")
        try:
            await row.click(timeout=8_000)
            clicked = True
            break
        except playwright_TimeoutError:
            logger.info(f"Row click not actionable (attempt {attempt + 1}), retrying...")
            await _wait_for_shell_unblocked(page)
    if not clicked:
        # Last resort: force a click near the row's top-left, which stays visible even when
        # the row sits at the very bottom edge of the grid (its centre may be clipped).
        await row.click(force=True, position={"x": 20, "y": 6})
    _log_timing(f"[timing] row click: {time.monotonic() - click_start:.2f}s")

    # Wait for Dynamics to finish loading/selecting the line (overlay clears + row marked
    # selected) instead of a fixed delay.
    await _wait_for_shell_unblocked(page)
    selected = await _wait_for_row_selected(page, row)
    _log_timing(f"[timing] open_expense_line total: {time.monotonic() - open_start:.2f}s")
    return selected


async def _wait_for_row_selected(page, row, timeout: float = 10_000) -> bool:
    """Poll until the grid row reports it is selected (best-effort, with a settle fallback).

    Logs whether a selection marker was detected (and how long it took) or whether it fell
    through to the settle fallback. On fallback it dumps the row's attributes/outerHTML so we
    can identify the *real* selection indicator Dynamics uses and replace this timeout-based
    wait with a precise signal -- this poll, when no marker is found, is the dominant
    per-expense latency in the fill flow (it runs once per expense line).

    Returns ``True`` when a selection marker was observed and ``False`` when it timed out and
    fell through to the settle fallback. Callers that select a line cold (e.g. itemization)
    can use the ``False`` result to verify the right card opened and retry rather than
    trusting that the click landed.
    """
    start = time.monotonic()
    deadline = start + (timeout / 1000)
    selected, classes = None, ""
    while time.monotonic() < deadline:
        try:
            selected = await row.get_attribute("aria-selected")
            classes = (await row.get_attribute("class")) or ""
        except Exception:
            selected, classes = None, ""
        if selected == "true" or "selected" in classes.lower():
            await page.wait_for_timeout(300)
            _log_timing(
                f"[timing] wait_for_row_selected: detected in "
                f"{time.monotonic() - start:.2f}s (aria-selected={selected!r})"
            )
            return True
        await page.wait_for_timeout(250)
    # No explicit selection marker observed; give the detail pane a moment to settle.
    try:
        row_html = await row.evaluate("el => el.outerHTML")
    except Exception:
        row_html = "<unavailable>"
    logger.warning(
        f"[timing] wait_for_row_selected: NO selection marker after "
        f"{time.monotonic() - start:.1f}s; settling 0.8s. "
        f"last aria-selected={selected!r}, class={classes!r}, "
        f"row.outerHTML[:400]={(row_html or '')[:400]!r}"
    )
    await page.wait_for_timeout(800)
    return False


async def _attach_receipt_file(page, receipt_file_path: str) -> None:
    """Attach a single receipt file to the currently selected expense line.

    Uses the Dynamics file-chooser flow: clicking "Browse" opens the native file chooser,
    which we answer with the receipt path. Setting the file on ``<input type="file">``
    directly does NOT work here — the Dynamics upload control keeps its "Upload" button
    disabled unless the file arrives through its own Browse/file-chooser flow. The Browse
    click can be swallowed by the ShellBlockingDiv loading overlay, so we wait for that
    overlay to clear and retry the click if the chooser doesn't open.
    """
    attach_start = time.monotonic()
    await page.click('a[name="EditReceipts"]')
    t_edit = time.monotonic()
    await page.click('button[name="AddButton"]')
    await page.wait_for_load_state("domcontentloaded")
    await _wait_for_shell_unblocked(page)
    t_open = time.monotonic()

    file_chooser = None
    for _ in range(5):
        try:
            async with page.expect_file_chooser(timeout=2_000) as file_chooser_info:
                browse_button = await page.wait_for_selector(
                    'button[name="UploadControlBrowseButton"]'
                )
                await browse_button.click()  # type: ignore[reportOptionalMemberAccess]
            file_chooser = await file_chooser_info.value
            break
        except playwright_TimeoutError:
            logger.info("File chooser did not appear, retrying...")
            await _wait_for_shell_unblocked(page)
            await page.wait_for_timeout(1_000)
    if file_chooser is None:
        raise RuntimeError("File chooser did not appear after multiple attempts.")
    await file_chooser.set_files(receipt_file_path)
    t_browse = time.monotonic()

    # The Upload button stays disabled until the control registers the selected file;
    # Playwright's click auto-waits for it to become enabled.
    await page.click('button[name="UploadControlUploadButton"]')
    t_upload = time.monotonic()
    await page.click('button[name="OkButtonAddNewTabPage"]')
    await page.click('button[name="CloseButton"]')
    t_close = time.monotonic()
    _log_timing(
        f"[timing] attach receipt: {t_close - attach_start:.2f}s "
        f"(editReceipts={t_edit - attach_start:.2f} "
        f"open[add+dom+shell]={t_open - t_edit:.2f} "
        f"browse+chooser+setfiles={t_browse - t_open:.2f} "
        f"upload={t_upload - t_browse:.2f} "
        f"ok+close={t_close - t_upload:.2f})"
    )
    # NOTE: do not click CommandButtonNext here. That button reloads/navigates the report
    # (the importer uses it precisely to force a reload), and clicking it after each receipt
    # intermittently navigates away from the report, closing the page mid-fill.


async def _snapshot_page_state(page, label: str) -> None:
    """Log a snapshot of the page state to diagnose grid/dialog leakage between expenses.

    Logged values (best-effort; never raises):
    - `url` / `title`
    - whether the Dynamics ShellBlockingDiv overlay is currently visible
    - whether any *modal* dialog popup is currently visible (a leftover modal will block
      grid interaction even though the overlay is gone)
    - whether the expense report grid is visible AND how many Created ID cells it currently
      has rendered (virtualized, so a low count when 26 lines exist suggests we're scrolled
      to the wrong part of the grid or stuck on a detail view)
    - whether the expense-line detail pane is currently expanded (Additional Information
      textarea visible) — when true after `Save and continue` we're stuck on detail view
    """
    try:
        state = await page.evaluate(
            """() => {
                const overlay = document.querySelector('[class*="ShellBlockingDiv"]');
                const overlayVisible = overlay
                    ? (overlay.offsetParent !== null && getComputedStyle(overlay).display !== 'none')
                    : false;
                const dialog = document.querySelector('div.dialog-popup.conductorContent');
                const dialogVisible = dialog
                    ? (dialog.offsetParent !== null && getComputedStyle(dialog).display !== 'none')
                    : false;
                const detail = document.querySelector('textarea[name="TrvExpTrans_AdditionalInformation"]');
                const detailVisible = detail
                    ? (detail.offsetParent !== null && !detail.disabled)
                    : false;
                const createdIds = document.querySelectorAll('input[aria-label="Created ID"]');
                // Sample a few visible values so we can see what part of the grid is rendered.
                const sampleValues = [];
                for (const inp of createdIds) {
                    const v = inp.getAttribute('value') || inp.value || '';
                    if (v) sampleValues.push(v);
                    if (sampleValues.length >= 6) break;
                }
                return {
                    href: location.href,
                    title: document.title,
                    overlayVisible,
                    dialogVisible,
                    detailVisible,
                    createdIdCount: createdIds.length,
                    firstCreatedIds: sampleValues,
                };
            }"""
        )
        logger.info(
            "[fill-debug] %s: title=%r overlay=%s dialog=%s detail=%s "
            "grid_created_id_count=%d first_grid_ids=%s",
            label,
            state.get("title"),
            state.get("overlayVisible"),
            state.get("dialogVisible"),
            state.get("detailVisible"),
            state.get("createdIdCount", 0),
            state.get("firstCreatedIds"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[fill-debug] %s: snapshot failed: %s", label, exc)


async def _save_and_continue(page) -> None:
    """Force-save the currently open expense line via the "Save and continue" button.

    MyExpense does not auto-save edits to the "Additional information" text box; only
    attaching a receipt persists the line. So when an expense line has no receipt to attach,
    the only change we make is filling that text box, which would be silently discarded
    unless we explicitly save. Clicking "Save and continue" persists the line while keeping
    us on the report so the fill loop can proceed to the next expense.
    """
    await _wait_for_shell_unblocked(page)
    await page.get_by_role("button", name="Save and continue").click()
    await _wait_for_shell_unblocked(page)


@expense_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Get the list of expense categories from category_list.txt for autocomplete functionality.
    """
    try:
        from config import EXPENSE_CATEGORIES

        logger.info(f"Loaded {len(EXPENSE_CATEGORIES)} categories from config")
        return jsonify({"categories": EXPENSE_CATEGORIES})

    except Exception as e:
        logger.error(f"Error loading categories: {e}")
        return jsonify({"error": "Failed to load categories"}), 500


@expense_bp.route("/import", methods=["POST"])
async def import_expenses():
    """
    Primary import endpoint that automatically chooses between mock and real import based on environment.
    This is the main endpoint used by the frontend in production.
    """
    try:
        logger.info(f"Import requested - Mocking expense import: {IMPORT_EXPENSE_MOCK}")
        if IMPORT_EXPENSE_MOCK:
            logger.info("Using mock import due to IMPORT_EXPENSE_MOCK=True")
            result = get_mock_expenses_internal()
            logger.info("Import completed successfully using mock source")
            return result
        else:
            logger.info("Using real browser import due to IMPORT_EXPENSE_MOCK=False")
            result = await _import_real_data()
            logger.info("Import completed successfully using browser source")
            return result

    except Exception as e:
        logger.error(f"Error during expense import: {e}")
        return jsonify({"error": "Import failed", "message": str(e)}), 500


@expense_bp.route("/import/mock", methods=["POST"])
def import_expenses_mock():
    """
    Explicit mock import endpoint for testing and development.
    Always returns mock data regardless of IMPORT_EXPENSE_MOCK setting.
    """
    logger.info("Explicit mock import requested")
    return get_mock_expenses_internal()


@expense_bp.route("/import/real", methods=["POST"])
async def import_expenses_real():
    """
    Explicit real import endpoint for testing and debugging.
    Always attempts real browser import regardless of DEBUG setting.
    """
    logger.info("Explicit real import requested")
    return await _import_real_data()


async def _import_real_data():
    """Import real expense data from browser"""
    try:
        # Use the import_expense_wrapper function to get real browser data
        expense_df = await import_expense_wrapper()
        expense_df["id"] = range(1, len(expense_df) + 1)

        # Preserve column names for the frontend (even if DataFrame is empty)
        columns = [col for col in expense_df.columns if col != "id"]

        # Convert DataFrame to list of dictionaries for JSON response
        expenses = expense_df.to_dict("records")

        logger.info(f"Successfully imported {len(expenses)} expenses from browser")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully imported {len(expenses)} expenses from My Expense",
                "data": expenses,
                "columns": columns,
                "count": len(expenses),
                "source": "browser",
            }
        )

    except RuntimeError as e:
        # Handle browser connection errors specifically
        error_msg = str(e)
        if "Expense page not available" in error_msg:
            return jsonify(
                {
                    "error": "Browser session required",
                    "message": "No active browser session found. Please run main.py first to start the browser session, or set DEBUG=True in .env for mock data.",
                }
            ), 400
        else:
            return jsonify(
                {
                    "error": "Browser automation failed",
                    "message": error_msg,
                }
            ), 500

    except Exception as e:
        logger.error(f"Error in real data import: {e}")
        return jsonify(
            {
                "error": "Import failed",
                "message": str(e),
            }
        ), 500


def get_mock_expenses_internal():
    """Internal function to handle mock data import."""
    try:
        # Import mock function specifically for this endpoint
        from expense_importer import import_expense_mock

        mock_expenses_df = import_expense_mock()
        mock_expenses_df["id"] = range(1, len(mock_expenses_df) + 1)

        # Preserve column names for the frontend (even if DataFrame is empty)
        columns = [col for col in mock_expenses_df.columns if col != "id"]

        # Convert DataFrame to list of dictionaries for JSON response
        expenses = mock_expenses_df.to_dict("records")

        logger.info(f"Successfully loaded {len(expenses)} mock expenses")

        return jsonify(
            {
                "success": True,
                "message": f"Mock data loaded with {len(expenses)} expenses",
                "data": expenses,
                "columns": columns,
                "count": len(expenses),
                "source": "mock",
            }
        )
    except Exception as e:
        logger.error(f"Error loading mock expenses: {e}")
        return jsonify(
            {
                "error": "Failed to load mock data",
                "message": str(e),
            }
        ), 500


@expense_bp.route("/mock", methods=["POST"])
def get_mock_expenses():
    """
    Explicit mock endpoint for testing purposes - always returns mock data regardless of DEBUG setting.
    """
    logger.info("Explicit mock data request")
    return get_mock_expenses_internal()


@expense_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint that reports system status including browser availability.
    """
    try:
        # Check browser availability
        browser_available = get_expense_page() is not None if get_expense_page else False

        # Check if import functions are available
        import_functions_available = import_expense_wrapper is not None

        # Determine overall health
        is_healthy = True
        issues = []

        if not import_functions_available:
            is_healthy = False
            issues.append("Import functions not available")

        if not IMPORT_EXPENSE_MOCK and not browser_available:
            is_healthy = False
            issues.append("Browser session not available (required for non-DEBUG mode)")

        health_status = {
            "status": "healthy" if is_healthy else "degraded",
            "debug_mode": IMPORT_EXPENSE_MOCK,
            "browser_available": browser_available,
            "import_functions_available": import_functions_available,
            "timestamp": datetime.now().isoformat(),
        }

        if issues:
            health_status["issues"] = issues

        status_code = 200 if is_healthy else 503

        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@expense_bp.route("/upload-receipt", methods=["POST"])
async def upload_receipt():
    """
    Upload receipt file for an expense.

    Expected form data:
    - file: Receipt file (PDF, PNG, JPG, JPEG, GIF)
    - expense_id: ID of the expense this receipt belongs to (optional)

    Returns:
    - JSON response with file information and upload status
    """
    try:
        # Check if file is present in request
        files = await request.files
        if "file" not in files:
            return jsonify(
                {"error": "No file provided", "message": "Please select a receipt file"}
            ), 400

        file = files["file"]

        # Check if file was actually selected
        if file.filename == "":
            return jsonify(
                {"error": "No file selected", "message": "Please select a receipt file"}
            ), 400

        # Check file extension
        allowed_extensions = RECEIPT_EXTENSIONS
        if not allowed_file(file.filename, allowed_extensions):
            return jsonify(
                {
                    "error": "Invalid file type",
                    "message": f"Only {', '.join(allowed_extensions).upper()} files are allowed",
                }
            ), 400

        # Secure the filename
        filename = secure_filename(file.filename)

        # Add timestamp to prevent filename conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        # Save file to upload directory
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # Get expense ID if provided
        form = await request.form
        expense_id = form.get("expense_id")

        # Get file size
        file_size = os.path.getsize(file_path)

        logger.info(f"Successfully uploaded receipt: {unique_filename} ({file_size} bytes)")

        response_data = {
            "success": True,
            "message": "Receipt uploaded successfully",
            "file_info": {
                "original_filename": file.filename,
                "saved_filename": unique_filename,
                "file_path": file_path,
                "file_size": file_size,
                "file_type": ext.lower(),
            },
        }

        if expense_id:
            response_data["expense_id"] = expense_id

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error uploading receipt: {e}")
        return jsonify({"error": "Upload failed", "message": str(e)}), 500


@expense_bp.route("/test-request", methods=["POST"])
async def test_request():
    """Test endpoint to verify request context is working."""
    try:
        logger.info("test_request endpoint called")
        data = await request.get_json()
        return jsonify({"success": True, "received_data": data})
    except Exception as e:
        logger.error(f"Error in test_request: {e}")
        return jsonify({"error": str(e)}), 500


@expense_bp.route("/match-receipt", methods=["POST"])
async def match_receipt():
    """
    Calculate confidence score for expense-receipt match.

    Expected JSON data:
    - expense_data: Dictionary containing expense information
    - receipt_path: Path to the receipt file

    Returns:
    - JSON response with confidence score
    """
    try:
        logger.info("match_receipt endpoint called")
        logger.info(f"Request method: {request.method}")

        data = await request.get_json()

        if not data:
            return jsonify(
                {
                    "error": "No data provided",
                    "message": "Please provide expense and receipt information",
                }
            ), 400

        expense_data = data.get("expense_data")
        receipt_data = data.get("receipt_data")

        # Calculate confidence score using existing receipt_matcher
        try:
            confidence_score = receipt_match_score(receipt_data, expense_data)
        except Exception as e:
            logger.warning(f"Error calling receipt_match_score: {e}")
            confidence_score = None

        logger.info(
            f"Calculated match confidence: {confidence_score} for expense {expense_data.get('id', 'unknown')}"
        )

        return jsonify(
            {
                "success": True,
                "confidence_score": confidence_score,
                "expense_id": expense_data.get("id"),
                "message": f"Match confidence calculated: {confidence_score}",
            }
        )

    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return jsonify({"error": "Match calculation failed", "message": str(e)}), 500


# Additional utility endpoints


@expense_bp.route("/list", methods=["GET"])
def list_expenses():
    """
    Get a list of all available expense data.
    This could be used to retrieve previously imported/uploaded expenses.
    """
    try:
        # This is a placeholder - in a real app, you'd fetch from a database
        # For now, return empty list or check for saved CSV files

        return jsonify(
            {"success": True, "message": "No stored expenses found", "data": [], "count": 0}
        )

    except Exception as e:
        logger.error(f"Error listing expenses: {e}")
        return jsonify({"error": "List failed", "message": str(e)}), 500


@expense_bp.route("/receipts", methods=["GET"])
def list_receipts():
    """
    Get a list of all uploaded receipt files.
    """
    try:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")

        if not os.path.exists(upload_folder):
            return jsonify(
                {"success": True, "message": "No receipts found", "receipts": [], "count": 0}
            )

        receipts = []
        allowed_extensions = RECEIPT_EXTENSIONS

        for filename in os.listdir(upload_folder):
            if allowed_file(filename, allowed_extensions):
                file_path = os.path.join(upload_folder, filename)
                file_size = os.path.getsize(file_path)
                file_ext = filename.rsplit(".", 1)[1].lower()

                receipts.append(
                    {
                        "filename": filename,
                        "file_path": file_path,
                        "file_size": file_size,
                        "file_type": file_ext,
                    }
                )

        return jsonify(
            {
                "success": True,
                "message": f"Found {len(receipts)} receipt files",
                "receipts": receipts,
                "count": len(receipts),
            }
        )

    except Exception as e:
        logger.error(f"Error listing receipts: {e}")
        return jsonify({"error": "List failed", "message": str(e)}), 500


@expense_bp.route("/delete", methods=["POST"])
async def delete_expenses():
    """
    Delete specified expenses from the current working set.

    Expected JSON data:
    - expense_ids: Array of expense IDs to delete

    Returns:
    - JSON response indicating success/failure
    """
    try:
        # Get the request data
        data = await request.get_json()
        if not data:
            return jsonify({"error": "Invalid request", "message": "No JSON data provided"}), 400

        expense_ids = data.get("expense_ids", [])
        if not expense_ids:
            return jsonify({"error": "Invalid request", "message": "No expense IDs provided"}), 400

        if not isinstance(expense_ids, list):
            return jsonify(
                {"error": "Invalid request", "message": "expense_ids must be an array"}
            ), 400

        # Convert IDs to strings for consistent comparison
        expense_ids = [str(id) for id in expense_ids]

        logger.info(f"Delete request for expense IDs: {expense_ids}")

        # Note: Since this application doesn't have persistent storage,
        # the actual deletion happens on the frontend by filtering the expenses array.
        # This endpoint serves as a validation and logging point.

        return jsonify(
            {
                "success": True,
                "message": f"Successfully processed deletion of {len(expense_ids)} expense(s)",
                "deleted_ids": expense_ids,
                "count": len(expense_ids),
            }
        )

    except Exception as e:
        logger.error(f"Error deleting expenses: {e}")
        return jsonify({"error": "Delete failed", "message": str(e)}), 500


@expense_bp.route("/create-from-receipts", methods=["POST"])
async def create_expenses_from_receipts():
    """
    Create new expense entries from receipts with invoice details.
    """
    try:
        data = await request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        receipts_with_invoice_details = data.get("receipts_with_invoice_details", [])
        current_expense_data = data.get("current_expense_data", [])

        if not receipts_with_invoice_details:
            return jsonify({"error": "No receipts with invoice details provided"}), 400

        logger.info(f"Creating expenses from {len(receipts_with_invoice_details)} receipts")

        # Find the highest existing expense ID to generate new sequential IDs
        existing_ids = [expense["id"] for expense in current_expense_data if "id" in expense]
        max_id = max(existing_ids) if existing_ids else 0

        # Start new IDs from the next number
        next_id = max_id + 1

        new_expenses = []
        processed_count = 0

        for receipt in receipts_with_invoice_details:
            try:
                invoice_details = receipt.get("invoiceDetails", {})

                if not invoice_details:
                    logger.warning(
                        f"Skipping receipt {receipt.get('name', 'unknown')} - no invoice details"
                    )
                    continue

                # Create new expense object
                new_expense = {
                    "id": next_id,
                    "Date": invoice_details.get("Date", ""),
                    "Amount": invoice_details.get("Amount"),
                    "Currency": invoice_details.get("Currency"),
                    "Merchant": invoice_details.get("Merchant", ""),
                    "Additional information": invoice_details.get("Additional information", ""),
                    "Additional description": f"Expense from {receipt.get('name')}",
                    "Expense category": invoice_details.get("Expense category"),
                    "Payment method": "Cash",
                    "receipts": [receipt],  # Attach the receipt to the expense
                }

                new_expenses.append(new_expense)
                next_id += 1
                processed_count += 1

                logger.info(
                    f"Created expense {new_expense['id']} from receipt {receipt.get('name')}"
                )

            except Exception as e:
                logger.error(f"Error processing receipt {receipt.get('name', 'unknown')}: {e}")
                continue

        if not new_expenses:
            return jsonify(
                {"error": "No valid expenses could be created from the provided receipts"}
            ), 400

        logger.info(f"Successfully created {len(new_expenses)} new expenses")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully created {len(new_expenses)} expenses from receipts",
                "new_expenses": new_expenses,
                "processed_receipt_count": processed_count,
            }
        )

    except Exception as e:
        logger.error(f"Error creating expenses from receipts: {e}")
        return jsonify({"error": "Failed to create expenses", "message": str(e)}), 500


@expense_bp.route("/bring-page-to-front", methods=["POST"])
async def bring_page_to_front():
    """
    Bring the My Expense page to the front of the browser.

    Returns:
    - JSON response indicating success or failure
    """
    try:
        logger.info("Attempting to bring My Expense page to front")

        # Get the current expense page
        page = get_expense_page()
        if page is None:
            logger.error("No active browser page found")
            return jsonify(
                {
                    "success": False,
                    "error": "No active browser session found. Please ensure the browser is connected.",
                }
            ), 503

        # Bring the page to front
        await page.bring_to_front()
        logger.info("Successfully brought page to front")

        return jsonify({"success": True, "message": "Page brought to front successfully"})

    except Exception as e:
        logger.error(f"Error bringing page to front: {e}")
        return jsonify(
            {"success": False, "error": "Failed to bring page to front", "message": str(e)}
        ), 500


@expense_bp.route("/navigate-to-report", methods=["POST"])
async def navigate_to_report():
    """
    Navigate the app's browser page to a specific expense report.
    Only available when AI_DEBUG=True.

    Request body: { "report_number": "D10710000200323" }
    """
    if not AI_DEBUG:
        return jsonify({"success": False, "error": "Only available in AI_DEBUG mode"}), 403

    try:
        data = await request.get_json()
        report_number = data.get("report_number")
        if not report_number:
            return jsonify({"success": False, "error": "report_number is required"}), 400

        page = get_expense_page()
        if page is None:
            return jsonify({"success": False, "error": "No active browser session"}), 503

        logger.info(f"Navigating to expense report: {report_number}")

        # If on the dashboard, click Expense management first
        expense_mgmt_btn = page.get_by_role("button", name="Expense management")
        if await expense_mgmt_btn.is_visible():
            await expense_mgmt_btn.click()
            await page.wait_for_load_state("networkidle")

        # If on an expense report detail page, go back to the list first
        save_close_btn = page.get_by_role("button", name="Save and close")
        if await save_close_btn.is_visible():
            await save_close_btn.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_load_state("networkidle")

        # Click the target expense report to open the detail page.
        report_link = page.get_by_title(report_number, exact=False)
        await report_link.wait_for(timeout=15000)
        await report_link.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_load_state("networkidle")

        # If still on the list (single click just selected the row), retry
        new_expense_btn = page.locator('*[data-dyn-controlname="NewExpenseButton"]')
        try:
            await new_expense_btn.wait_for(timeout=5000)
        except Exception:
            # Second click
            logger.info("First click selected the row, clicking again to open")
            await report_link.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_load_state("networkidle")

            try:
                await new_expense_btn.wait_for(timeout=5000)
            except Exception:
                # Grid is stale after repeated exports — refresh and retry
                logger.info("Grid is stale, refreshing page and retrying")
                await page.reload()
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_load_state("networkidle")
                report_link = page.get_by_title(report_number, exact=False)
                await report_link.wait_for(timeout=15000)
                await report_link.click()
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_load_state("networkidle")

                # After reload, first click may still just select the row
                try:
                    await new_expense_btn.wait_for(timeout=5000)
                except Exception:
                    logger.info("Clicking again after reload")
                    await report_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_load_state("networkidle")

        # Verify we're on the expense report detail page
        await page.wait_for_selector('*[data-dyn-controlname="NewExpenseButton"]', timeout=15000)

        logger.info(f"Successfully navigated to expense report {report_number}")
        return jsonify(
            {
                "success": True,
                "message": f"Navigated to expense report {report_number}",
            }
        )

    except Exception as e:
        logger.error(f"Error navigating to report: {e}")
        return jsonify({"success": False, "error": "Navigation failed", "message": str(e)}), 500


@expense_bp.route("/fill-expense-report", methods=["POST"])
async def fill_expense_report():
    """
    Fill expense report with the provided expense data.

    Accepts JSON data containing:
    - expenses: List of expense records
    - timestamp: Timestamp of when the request was made

    Returns:
    - A server-sent events stream reporting per-line progress while filling, or a
      JSON error response if the request is invalid or no browser session exists.
    """
    logger.info("Starting fill expense report process")

    # Get the JSON data from the request
    data = await request.get_json()
    if not data:
        return jsonify(
            {
                "success": False,
                "error": "No data provided",
                "message": "Request body must contain JSON data",
            }
        ), 400

    # Extract expense data
    expenses = data.get("expenses", [])
    timestamp = data.get("timestamp")

    if not expenses:
        return jsonify(
            {
                "success": False,
                "error": "No expenses provided",
                "message": "The expenses array cannot be empty",
            }
        ), 400

    # Count expenses with receipts (now attached directly to each expense)
    total_expenses = len(expenses)
    num_expenses_with_receipts = len(
        [
            expense
            for expense in expenses
            if expense.get("Receipts") and len(expense["Receipts"]) > 0
        ]
    )

    logger.info(f"Processing {total_expenses} expenses")
    logger.info(f"Expenses with attached receipts: {num_expenses_with_receipts}")

    existing_expenses_to_update = [expense for expense in expenses if expense.get("Created ID")]
    new_expenses_to_create = [expense for expense in expenses if not expense.get("Created ID")]

    page = get_expense_page()
    if page is None:
        return jsonify(
            {
                "success": False,
                "error": "Browser session not available",
                "message": (
                    "Expense page not available. Make sure the browser session is initialized."
                ),
            }
        ), 500

    # Reject duplicate/concurrent fills: they share one Playwright page and would corrupt
    # each other's receipt uploads. This check-and-set is atomic (no await in between).
    global _fill_in_progress
    if _fill_in_progress:
        logger.warning("Ignoring fill request: another fill is already in progress")
        return jsonify(
            {
                "success": False,
                "error": "Fill already in progress",
                "message": "An expense fill is already running. Please wait for it to finish.",
            }
        ), 409
    _fill_in_progress = True

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    async def generate():
        try:
            yield _sse({"status": "starting", "total": total_expenses})

            completed = 0

            # Set of imported expense Created IDs — used by the locate helper to pick a
            # parent-row anchor for keyboard navigation when the rendered window contains
            # itemization sub-rows that would otherwise trap ArrowDown inside the children.
            known_top_level_ids = {
                str(e["Created ID"]) for e in existing_expenses_to_update
            }

            # Update existing expenses in MyExpense with receipts
            for expense in existing_expenses_to_update:
                expense_start = time.monotonic()
                expense_created_id = expense["Created ID"]

                attached_receipts = expense.get("Receipts", [])
                logger.info(
                    f"Expense {expense_created_id}: {len(attached_receipts)} receipts attached"
                )
                await _snapshot_page_state(
                    page, f"before locate expense {expense_created_id} (#{completed + 1})"
                )

                # Locate the expense line on demand, scrolling the virtualized grid so rows
                # that aren't rendered yet (e.g. the last lines after import) are found
                # without requiring the user to manually zoom out.
                expense_line_to_fill = await _locate_expense_line(
                    page, expense_created_id, known_ids=known_top_level_ids
                )
                await _open_expense_line(page, expense_line_to_fill)

                # Fill in additional information box. This can be flaky so we need to explicitely click on the box and fill it
                text_box = await page.query_selector(
                    'textarea[name="TrvExpTrans_AdditionalInformation"]'
                )
                if text_box is None:
                    raise RuntimeError("Additional information text box not found on the page.")
                await text_box.click()
                await text_box.wait_for_element_state("editable")
                await text_box.fill(expense["Additional information"])

                # Log receipt details
                for _, receipt in enumerate(attached_receipts):
                    await _attach_receipt_file(page, receipt["filePath"])

                # Force-save the line. Attaching a receipt persists the line, but a
                # text-box-only edit (no receipt) is not auto-saved, so without this the
                # "Additional information" we just filled would be lost.
                await _save_and_continue(page)
                await _snapshot_page_state(
                    page, f"after save expense {expense_created_id} (#{completed + 1})"
                )

                _log_timing(
                    f"[timing] expense {expense_created_id} TOTAL: "
                    f"{time.monotonic() - expense_start:.2f}s "
                    f"({len(attached_receipts)} receipt(s))"
                )
                completed += 1
                yield _sse(
                    {
                        "status": "progress",
                        "current": completed,
                        "total": total_expenses,
                        "label": expense.get("Merchant") or expense_created_id,
                    }
                )

            logger.info(f"Total expenses: {total_expenses}")
            logger.info(f"Expenses with receipts: {num_expenses_with_receipts}")

            # Create new expenses and attach receipts to them
            for expense in new_expenses_to_create:
                await page.click('button[name="NewExpenseButton"]')

                await page.fill('input[name="CategoryInput"]', expense["Expense category"])
                await page.fill('input[name="AmountInput"]', expense["Amount"])
                await page.fill('input[name="CurrencyInput"]', expense["Currency"])
                await page.fill('input[name="MerchantInputNoLookup"]', expense["Merchant"])

                try:
                    date_obj = datetime.strptime(expense["Date"], "%Y-%m-%d")
                    formatted_date = (
                        DATE_FORMAT.replace("DD", str(date_obj.day))
                        .replace("MM", str(date_obj.month))
                        .replace("YYYY", str(date_obj.year))
                    )
                    await page.fill('input[name="DateInput"]', formatted_date)
                except Exception as e:
                    error_msg = (
                        f"Failed to fill date field for expense date '{expense['Date']}'. "
                        f"Error: {e}. Current DATE_FORMAT: {DATE_FORMAT}. "
                        f"Please verify your DATE_FORMAT setting in the .env file matches your system's expected format."
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e

                # Fill in additional information box. This can be flaky so we need to explicitely click on the box and fill it
                text_box = await page.query_selector('textarea[name="NotesInput"]')
                if text_box is None:
                    raise RuntimeError("Notes input text box not found on the page.")
                await text_box.click()
                await text_box.wait_for_element_state("editable")
                await text_box.fill(expense["Additional information"])

                await page.click('button[name="SaveButton"]')
                await page.wait_for_timeout(3000)

                for receipt in expense["Receipts"]:
                    await _attach_receipt_file(page, receipt["filePath"])

                completed += 1
                yield _sse(
                    {
                        "status": "progress",
                        "current": completed,
                        "total": total_expenses,
                        "label": (
                            expense.get("Merchant")
                            or expense.get("Expense category")
                            or "New expense"
                        ),
                    }
                )

            result_message = f"Successfully processed {total_expenses} expenses"
            if num_expenses_with_receipts > 0:
                result_message += f" ({num_expenses_with_receipts} with receipts)"

            logger.info("Fill expense report completed successfully")

            yield _sse(
                {
                    "status": "complete",
                    "success": True,
                    "message": result_message,
                    "data": {
                        "total_expenses": total_expenses,
                        "expenses_with_receipts": num_expenses_with_receipts,
                        "timestamp": timestamp,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error filling expense report: {e}")
            yield _sse({"status": "error", "message": str(e)})

        finally:
            # Release the guard so a subsequent fill can run.
            global _fill_in_progress
            _fill_in_progress = False

    response = await make_response(generate(), 200)
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    return response


@expense_bp.route("/screenshot", methods=["GET"])
async def take_screenshot():
    """
    Capture a screenshot of the current MyExpense page.

    Saves the image to ``test_screenshots/`` and returns it as a PNG response.
    Useful for automated test verification.
    """
    try:
        page = get_expense_page()
        if page is None:
            return jsonify(
                {
                    "success": False,
                    "error": "No active browser page",
                    "message": "Browser session is not available.",
                }
            ), 503

        # Ensure output directory exists
        screenshot_dir = os.path.join(os.getcwd(), "test_screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(screenshot_dir, filename)

        await page.screenshot(path=filepath, full_page=True)
        logger.info(f"Screenshot saved to {filepath}")

        from quart import send_file as quart_send_file

        return await quart_send_file(filepath, mimetype="image/png")

    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        return jsonify({"success": False, "error": "Screenshot failed", "message": str(e)}), 500


@expense_bp.route("/hotel-subcategories", methods=["GET"])
def get_hotel_subcategories():
    """Return the configured valid hotel itemization subcategories (for the review-table dropdown)."""
    from config import HOTEL_SUBCATEGORIES

    return jsonify({"success": True, "subcategories": list(HOTEL_SUBCATEGORIES)})


def _is_hotel_expense(expense: dict) -> bool:
    """True if an expense record is in the Hotel category."""
    return str(expense.get("Expense category", "")).strip().lower() == "hotel"


def _parse_amount(value) -> float | None:
    """Parse an expense Amount that may be a number or a string (currency/commas tolerated)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    import re as _re

    cleaned = _re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _balance_info(lines: list, amount) -> dict:
    """Compute itemized total vs the expense amount for validation surfacing."""
    from invoice_extractor import is_balanced, itemized_total

    total = itemized_total(lines)
    parsed = _parse_amount(amount)
    difference = round(total - parsed, 2) if parsed is not None else None
    return {
        "amount": parsed,
        "itemized_total": total,
        "difference": difference,
        "balanced": is_balanced(lines, amount),
    }


def _primary_receipt_path(expense: dict) -> str | None:
    """Return the file path of the first attached receipt (the hotel invoice), if any."""
    receipts = expense.get("Receipts") or expense.get("receipts") or []
    for receipt in receipts:
        if isinstance(receipt, dict):
            path = receipt.get("filePath") or receipt.get("file_path")
            if path:
                return path
    return None


@expense_bp.route("/itemize/extract", methods=["POST"])
async def itemize_extract():
    """Run LLM extraction over each Hotel expense's matched receipt to produce itemization lines.

    Accepts JSON: {expenses: [...], provider?: str}. For every Hotel-category expense that has a
    matched receipt, the receipt (hotel invoice) is sent to the extractor concurrently. Returns
    one result per hotel expense with its extracted line items for the review table.
    """
    data = await request.get_json()
    if not data:
        return jsonify(
            {
                "success": False,
                "error": "No data provided",
                "message": "Request body must contain JSON data",
            }
        ), 400

    expenses = data.get("expenses", [])
    provider = data.get("provider") or None

    hotel_expenses = [e for e in expenses if _is_hotel_expense(e) and _primary_receipt_path(e)]
    if not hotel_expenses:
        return jsonify(
            {
                "success": False,
                "error": "No hotel expenses",
                "message": "No Hotel expenses with a matched receipt to itemize.",
            }
        ), 400

    logger.info(f"Extracting itemization for {len(hotel_expenses)} hotel expense(s)")

    from invoice_extractor import extract_hotel_itemization

    async def _extract_one(expense: dict) -> dict:
        receipt_path = _primary_receipt_path(expense)
        expected_total = _parse_amount(expense.get("Amount"))
        lines = await extract_hotel_itemization(
            receipt_path, provider=provider, expected_total=expected_total
        )
        return {
            "id": expense.get("id"),
            "created_id": expense.get("Created ID"),
            "merchant": expense.get("Merchant", ""),
            "expense_category": expense.get("Expense category", ""),
            "amount": expense.get("Amount"),
            "receipt_path": receipt_path,
            "lines": lines,
            **_balance_info(lines, expense.get("Amount")),
        }

    raw_results = await asyncio.gather(
        *[_extract_one(e) for e in hotel_expenses], return_exceptions=True
    )

    results = []
    for expense, result in zip(hotel_expenses, raw_results):
        if isinstance(result, Exception):
            logger.error(f"Itemization extraction failed for {expense.get('id')}: {result}")
            results.append(
                {
                    "id": expense.get("id"),
                    "created_id": expense.get("Created ID"),
                    "merchant": expense.get("Merchant", ""),
                    "expense_category": expense.get("Expense category", ""),
                    "amount": expense.get("Amount"),
                    "lines": [],
                    "error": str(result),
                    **_balance_info([], expense.get("Amount")),
                }
            )
        else:
            if not result.get("balanced"):
                logger.warning(
                    "Itemization for expense %s does not reconcile: itemized=%s vs amount=%s",
                    result.get("created_id") or result.get("id"),
                    result.get("itemized_total"),
                    result.get("amount"),
                )
            results.append(result)

    return jsonify(
        {
            "success": True,
            "results": results,
            "message": f"Extracted itemization for {len(results)} hotel expense(s)",
        }
    )


@expense_bp.route("/itemize/fill", methods=["POST"])
async def itemize_fill():
    """Fill the (reviewed) itemization lines into MyExpense for each hotel expense.

    Accepts JSON: {items: [{created_id, id?, lines: [...]}], ...}. For each item the matching
    expense line is located and opened, the Itemize dialog is launched, and the lines are filled.
    """
    data = await request.get_json()
    if not data:
        return jsonify(
            {
                "success": False,
                "error": "No data provided",
                "message": "Request body must contain JSON data",
            }
        ), 400

    items = data.get("items", [])
    if not items:
        return jsonify(
            {
                "success": False,
                "error": "No items provided",
                "message": "The items list is empty",
            }
        ), 400

    page = get_expense_page()
    if page is None:
        return jsonify(
            {
                "success": False,
                "error": "Browser session not available",
                "message": "Expense page not available. Make sure the browser session is initialized.",
            }
        ), 500

    # Itemization drives the same shared Playwright page as fill; never run them concurrently.
    global _fill_in_progress
    if _fill_in_progress:
        return jsonify(
            {
                "success": False,
                "error": "Operation already in progress",
                "message": "Another fill/itemize operation is already running.",
            }
        ), 409
    _fill_in_progress = True

    try:
        import pandas as pd

        from itemization import (
            _dismiss_flyout_if_open,
            click_itemize_button,
            itemize_hotel_invoice,
        )

        results = []
        for item in items:
            created_id = item.get("created_id") or item.get("Created ID")
            lines = item.get("lines", [])

            if not created_id:
                results.append(
                    {
                        "id": item.get("id"),
                        "created_id": None,
                        "success": False,
                        "message": "Missing Created ID; the hotel expense line must exist in MyExpense first.",
                    }
                )
                continue
            if not lines:
                results.append(
                    {
                        "id": item.get("id"),
                        "created_id": created_id,
                        "success": False,
                        "message": "No itemization lines to fill.",
                    }
                )
                continue

            try:
                balance = _balance_info(lines, item.get("amount"))
                if item.get("amount") is not None and not balance["balanced"]:
                    logger.warning(
                        "Filling unbalanced itemization for %s: itemized=%s vs amount=%s (diff=%s)",
                        created_id,
                        balance["itemized_total"],
                        balance["amount"],
                        balance["difference"],
                    )

                # Hotel lines are frequently the FIRST grid row, where a sticky "receipt
                # required" message bar overlaps the row: the selecting click misses, the
                # wrong card stays open, and its Actions menu has no "Itemize" — so
                # click_itemize_button raises. Re-select the line (centered, so the banner
                # can't hide it) and retry a few times, treating the Itemize dialog actually
                # opening as the source of truth rather than the unreliable selection marker.
                max_open_attempts = 4
                itemize_opened = False
                last_open_err: Exception | None = None
                for open_attempt in range(max_open_attempts):
                    expense_line = await _locate_expense_line(page, created_id)
                    selected = await _open_expense_line(
                        page, expense_line, block="center"
                    )
                    if not selected:
                        logger.info(
                            "[itemize] row %s selection unconfirmed (attempt %d/%d)",
                            created_id,
                            open_attempt + 1,
                            max_open_attempts,
                        )
                    try:
                        await click_itemize_button(page)
                        itemize_opened = True
                        break
                    except RuntimeError as open_err:
                        last_open_err = open_err
                        logger.warning(
                            "[itemize] Itemize unavailable for %s (attempt %d/%d): %s",
                            created_id,
                            open_attempt + 1,
                            max_open_attempts,
                            open_err,
                        )
                        # Dismiss a stray Actions flyout before re-selecting the line —
                        # but ONLY if one is actually open. A blind Escape here lands on the
                        # expense-report form and closes it, navigating back to the
                        # workspace (the "taken to another page" failure). click_itemize_button
                        # now self-heals a swallowed click, so this is just belt-and-braces.
                        await _dismiss_flyout_if_open(page)
                        await page.wait_for_timeout(800)
                if not itemize_opened:
                    raise last_open_err or RuntimeError(
                        f"Could not open the Itemize dialog for expense {created_id}."
                    )
                await itemize_hotel_invoice(page, pd.DataFrame(lines))
                # itemize_hotel_invoice commits the dialog (Close); now persist the line.
                # "Save and continue" saves the expense and advances — the final
                # confirmation step of the manual flow — so the itemization sticks before
                # we move on to the next hotel.
                await _save_and_continue(page)
                results.append(
                    {
                        "id": item.get("id"),
                        "created_id": created_id,
                        "success": True,
                        "lines": len(lines),
                        **balance,
                    }
                )
            except Exception as e:
                logger.error(f"Error itemizing expense {created_id}: {e}", exc_info=True)
                results.append(
                    {
                        "id": item.get("id"),
                        "created_id": created_id,
                        "success": False,
                        "message": str(e),
                    }
                )

        succeeded = sum(1 for r in results if r.get("success"))
        return jsonify(
            {
                "success": succeeded > 0,
                "results": results,
                "message": f"Itemized {succeeded} of {len(items)} hotel expense(s)",
            }
        )

    except Exception as e:
        logger.error(f"Error itemizing expenses: {e}", exc_info=True)
        return jsonify(
            {"success": False, "error": "Failed to itemize expenses", "message": str(e)}
        ), 500
    finally:
        _fill_in_progress = False
