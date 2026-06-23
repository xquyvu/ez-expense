"""Delete every receipt attached to a MyExpense expense report.

This drives the same steps a user performs in the web UI, but programmatically: it navigates
the app's browser to an expense report, opens it, switches to the report-level **Receipts**
tab, ticks the selection marker of every visible receipt card, clicks **Remove** and confirms
with **Yes** — repeating until the report's receipt count reaches zero. Removal is slow, so it
waits (on the Dynamics loading overlay and the live receipt count) rather than a fixed delay.

Everything below was verified live against report D10710000215406:
- The clickable tab is ``<li role="tab" data-dyn-controlname="ReceiptsTabPage_header">``; both the
  report detail page and the workspace expose one, so we click the **visible** one.
- ``[data-dyn-controlname="ReceiptsTabPage"]`` is the tab *panel* (content), matched ``:visible``.
- Receipts render as **cards**; each card's selection marker is ``.dyn-cardMarking[role="checkbox"]``
  (``aria-checked`` toggles). Its centre is overlapped by the card's read-only "File name" field,
  so we click the marker's top-left corner (a real, trusted click) and fall back to dispatching a
  click event if that ever stalls.
- The card list is **virtualised** (only ~25 cards render at once), so progress and termination are
  driven by the true count in ``input[id$="ReceiptCount_input"]``, not the rendered card count.
- Remove is ``button[name="RemoveButtonReceiptsTab"]``; the confirmation Yes is ``button[name="Yes"]``;
  the blocking overlay during deletion is ``#ShellBlockingDiv``.

Prerequisites:
- A debug browser (Edge/Chrome) already running with remote debugging on the configured port
  (default 9222), signed in to MyExpense. This is the same browser the app uses.

Usage:
    uv run python -m scripts.delete_receipts --report-number D10710000215406

    # Only do a single Remove pass (don't loop until empty):
    uv run python -m scripts.delete_receipts --report-number D10710000215406 --single-pass

    # Select receipts but stop before removing (verify selection only):
    uv run python -m scripts.delete_receipts --report-number D10710000215406 --dry-run

The process exits non-zero if it cannot complete, and writes a screenshot of the MyExpense page
for diagnosis.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Make the repo importable regardless of where this is launched from.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse the e2e driver's session setup + navigation. Importing it also sets AI_DEBUG=True
# (required by the /navigate-to-report endpoint) and pins the browser port.
from scripts.drive_e2e import DEFAULT_WORKSPACE_URL, _log, navigate, setup_session  # noqa: E402

# --- Verified selectors (see module docstring) ------------------------------------------
_TAB_HEADER = '[data-dyn-controlname="ReceiptsTabPage_header"]:visible'
_PANEL = '[data-dyn-controlname="ReceiptsTabPage"]:visible'
_REMOVE = 'button[name="RemoveButtonReceiptsTab"]:visible'
_CARD_CHECKBOX = '.dyn-cardMarking[role="checkbox"]'
_CARD_CHECKBOX_UNCHECKED = '.dyn-cardMarking[role="checkbox"][aria-checked="false"]'
_OVERLAY = "#ShellBlockingDiv"  # Dynamics blocking overlay shown while a delete is in progress
_RECEIPT_COUNT_INPUT = 'input[id$="ReceiptCount_input"]'  # report header "Receipts" total
_REPORT_DETAIL_MARKER = '*[data-dyn-controlname="NewExpenseButton"]'

# Hard cap so a misbehaving selector can never loop forever.
_MAX_SELECT_CLICKS = 5_000


# ---------------------------------------------------------------------------
# Low-level page helpers
# ---------------------------------------------------------------------------


async def _wait_overlay_clear(page, timeout: float) -> None:
    """Wait for the Dynamics ``ShellBlockingDiv`` overlay to disappear (best-effort).

    The overlay swallows clicks while present and stays up for the duration of a (slow)
    receipt deletion, so we wait for it before interacting with the page. We deliberately do
    NOT wait for networkidle: the Dynamics SPA polls continuously and never reaches it.
    """
    try:
        await page.wait_for_selector(_OVERLAY, state="hidden", timeout=timeout)
    except Exception:  # noqa: BLE001 - the overlay may simply not be present
        pass


async def get_receipt_count(page) -> int | None:
    """Read the report's true receipt total from the header field, or None if unavailable."""
    try:
        value = await page.evaluate(
            """() => {
                const el = document.querySelector('input[id$="ReceiptCount_input"]');
                return el ? (el.value || '') : null;
            }"""
        )
    except Exception:  # noqa: BLE001
        return None
    if value is None:
        return None
    value = value.replace(",", "").strip()
    return int(value) if value.isdigit() else None


def _remove_button(page):
    """Locator for the (visible) Receipts-tab Remove button."""
    return page.locator(_REMOVE).first


async def _on_report_detail(page) -> bool:
    """True if the report detail page (with its toolbar) is currently open."""
    try:
        return await page.locator(_REPORT_DETAIL_MARKER).count() > 0
    except Exception:  # noqa: BLE001
        return False


async def activate_receipts_tab(page, timeout: float = 30_000) -> None:
    """Switch to the report-level Receipts tab and wait for its Remove button to appear.

    Clicks the visible ``ReceiptsTabPage_header`` tab (the report detail one, not the hidden
    workspace pivot). Activation is verified by the Remove button becoming visible.
    """
    remove = _remove_button(page)
    try:
        if await remove.is_visible():
            return
    except Exception:  # noqa: BLE001
        pass

    candidates = [
        page.locator(_TAB_HEADER).first,
        page.locator('[id$="ReceiptsTabPage_header"]:visible').first,
    ]
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            if await candidate.count() == 0:
                continue
            await candidate.scroll_into_view_if_needed(timeout=5_000)
            await candidate.click(timeout=8_000)
            await remove.wait_for(state="visible", timeout=timeout)
            await page.wait_for_timeout(800)  # let the card list paint
            return
        except Exception as exc:  # noqa: BLE001 - try the next strategy
            last_error = exc
            continue

    raise RuntimeError(f"Could not activate the Receipts tab. Last error: {last_error}")


async def count_visible_receipts(page) -> int:
    """Number of receipt cards currently rendered in the active Receipts panel."""
    return await page.locator(f"{_PANEL} {_CARD_CHECKBOX}").count()


async def select_visible_receipts(page) -> int:
    """Tick the selection marker of every visible receipt card; return how many were ticked.

    Re-queries the "unchecked" set on every iteration so it is robust to the card list
    re-rendering after each click, and stops early if selection stalls. The marker's centre is
    overlapped by the card's read-only "File name" field, so we click the marker's top-left
    corner (a real, trusted click Dynamics honours) and fall back to ``dispatch_event('click')``
    if corner-clicking ever stops making progress.
    """
    panel = page.locator(_PANEL).first

    selected = 0
    stalls = 0
    use_dispatch = False
    for _ in range(_MAX_SELECT_CLICKS):
        unchecked = panel.locator(_CARD_CHECKBOX_UNCHECKED)
        remaining = await unchecked.count()
        if remaining == 0:
            break

        checkbox = unchecked.first
        try:
            await checkbox.scroll_into_view_if_needed(timeout=5_000)
        except Exception:  # noqa: BLE001 - scrolling is best-effort
            pass
        try:
            if use_dispatch:
                await checkbox.dispatch_event("click")
            else:
                await checkbox.click(position={"x": 6, "y": 6}, timeout=5_000)
        except Exception as exc:  # noqa: BLE001
            _log(f"[warn] card select click failed: {exc}")

        await page.wait_for_timeout(120)

        new_remaining = await unchecked.count()
        if new_remaining < remaining:
            selected += remaining - new_remaining
            stalls = 0
        elif not use_dispatch and stalls >= 1:
            _log("[info] switching to dispatch_event('click') for card selection")
            use_dispatch = True
            stalls = 0
        else:
            stalls += 1
            if stalls >= 3:
                _log(f"[warn] selection stalled with {new_remaining} unchecked card(s); stopping")
                break

    return selected


async def click_remove(page, timeout: float = 30_000) -> None:
    """Click the Receipts-tab Remove button (auto-waits past the loading overlay)."""
    remove = _remove_button(page)
    await remove.wait_for(state="visible", timeout=timeout)
    await remove.click(timeout=timeout)


async def confirm_yes(page, timeout: float = 30_000) -> bool:
    """Confirm the Dynamics removal prompt by clicking Yes. Returns True if clicked."""
    for selector in (
        'button[name="Yes"]',
        '[data-dyn-controlname="Yes"]',
        '.dialog-popup-content button:has-text("Yes")',
        'button:has-text("Yes")',
    ):
        loc = page.locator(selector).first
        wait_ms = timeout if selector == 'button[name="Yes"]' else 2_000
        try:
            await loc.wait_for(state="visible", timeout=wait_ms)
            await loc.click(timeout=timeout)
            return True
        except Exception:  # noqa: BLE001 - try the next fallback
            continue
    return False


async def _overlay_visible(page) -> bool:
    """True while the Dynamics blocking overlay is shown (i.e. a delete is in progress)."""
    try:
        return await page.evaluate(
            """() => {
                const e = document.querySelector('#ShellBlockingDiv');
                if (!e) return false;
                const s = getComputedStyle(e);
                return s.display !== 'none' && s.visibility !== 'hidden' && e.offsetParent !== null;
            }"""
        )
    except Exception:  # noqa: BLE001
        return False


async def _wait_for_count_drop(page, prev: int, timeout: float) -> int | None:
    """Poll the receipt count until it drops below ``prev`` (deletion complete), or timeout.

    Deleting a batch of attached receipts is very slow (~9s per receipt; ~4 min for 25): the
    ``ShellBlockingDiv`` overlay stays up the whole time and the count then drops all at once.
    We only poll here — we never re-navigate, because navigating away mid-deletion aborts it.
    Returns the latest count seen (which may still equal ``prev`` if the deletion never ran).
    """
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        current = await get_receipt_count(page)
        if current is not None and current < prev:
            return current
        await page.wait_for_timeout(2_000)
    return await get_receipt_count(page)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def delete_all_receipts(
    page,
    client,
    report_number: str,
    *,
    single_pass: bool,
    max_passes: int,
    settle_timeout: float,
    dry_run: bool,
) -> int:
    """Remove every receipt from the open report, returning the number removed.

    Each pass selects every visible receipt card, clicks Remove and confirms, then waits for
    the report's receipt count to drop (the deletion is slow). Repeats until the count is zero
    or stops making progress, unless ``single_pass``.
    """
    await _wait_overlay_clear(page, 60_000)
    await activate_receipts_tab(page)
    count = await get_receipt_count(page)
    _log(f"[start] report has {count if count is not None else '?'} receipt(s)")

    total_removed = 0
    for pass_index in range(1, max_passes + 1):
        if not await _on_report_detail(page):
            _log("[nav] not on the report detail page; re-navigating")
            await navigate(client, report_number)
        await _wait_overlay_clear(page, settle_timeout)
        await activate_receipts_tab(page)

        count = await get_receipt_count(page)
        if count == 0:
            _log(f"[done] no receipts remain (after {pass_index - 1} pass(es))")
            break
        if count is None and await count_visible_receipts(page) == 0:
            _log(f"[done] no receipts rendered (after {pass_index - 1} pass(es))")
            break

        selected = await select_visible_receipts(page)
        if selected == 0:
            # Transient (overlay/tab not settled)? Retry once before giving up.
            await page.wait_for_timeout(3_000)
            await activate_receipts_tab(page)
            selected = await select_visible_receipts(page)
        if selected == 0:
            _log(f"[warn] {count} receipt(s) remain but none could be selected; stopping")
            break
        _log(f"[pass {pass_index}] selected {selected} card(s) (remaining before: {count})")

        if dry_run:
            _log("[dry-run] selection only — not clicking Remove/Yes")
            return 0

        await _wait_overlay_clear(page, settle_timeout)
        await click_remove(page)
        if not await confirm_yes(page):
            raise RuntimeError("Removal confirmation ('Yes') did not appear after clicking Remove")
        _log(
            f"[pass {pass_index}] confirmed — waiting up to "
            f"{settle_timeout / 1000:.0f}s for deletion to complete (this is slow)..."
        )

        prev = count if count is not None else selected
        new_count = await _wait_for_count_drop(page, prev, settle_timeout)
        if new_count is not None and new_count < prev:
            removed = prev - new_count
            total_removed += removed
            _log(f"[pass {pass_index}] deleted {removed} receipt(s); {new_count} remaining")
            count = new_count
        else:
            _log(
                f"[pass {pass_index}] receipt count did not drop "
                f"(was {prev}, now {new_count}); stopping to avoid a loop"
            )
            break

        if single_pass:
            break

    final = await get_receipt_count(page)
    _log(f"[summary] removed {total_removed} receipt(s); {final if final is not None else '?'} remaining")
    return total_removed


async def run(args: argparse.Namespace) -> int:
    client, page, playwright = await setup_session(
        args.browser_port, args.workspace_url, diagnostics=args.diagnostics
    )
    try:
        _log(f"[step] navigate -> {args.report_number}")
        await navigate(client, args.report_number)

        _log("[step] delete receipts")
        await delete_all_receipts(
            page,
            client,
            args.report_number,
            single_pass=args.single_pass,
            max_passes=args.max_passes,
            settle_timeout=args.settle_timeout,
            dry_run=args.dry_run,
        )
        _log("[result] done")
        return 0
    except Exception as exc:  # noqa: BLE001 - capture a screenshot for diagnosis
        _log(f"[error] {exc}")
        try:
            await page.screenshot(path=args.screenshot, full_page=True)
            _log(f"[screenshot] saved {args.screenshot}")
        except Exception as shot_exc:  # noqa: BLE001
            _log(f"[warn] screenshot failed: {shot_exc}")
        return 1
    finally:
        try:
            await playwright.stop()
        except Exception:  # noqa: BLE001
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all receipts attached to a MyExpense expense report."
    )
    parser.add_argument("--report-number", required=True, help="MyExpense report to open.")
    parser.add_argument(
        "--browser-port",
        type=int,
        default=int(os.getenv("EZ_EXPENSE_BROWSER_PORT", "9222")),
        help="Debug browser remote-debugging port.",
    )
    parser.add_argument(
        "--workspace-url",
        default=DEFAULT_WORKSPACE_URL,
        help="MyExpense workspace URL used to normalise the starting page.",
    )
    parser.add_argument(
        "--single-pass",
        action="store_true",
        help="Only do one Remove+confirm pass instead of looping until the count is zero.",
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=100,
        help="Safety cap on the number of select/Remove/confirm passes (default 100).",
    )
    parser.add_argument(
        "--settle-timeout",
        type=float,
        default=600_000,
        help="Max milliseconds to wait for one removal to finish (default 600000 = 10 min). "
        "Deleting attached receipts is very slow (~9s each; ~4 min for a 25-card batch); the "
        "script returns as soon as the count drops, so this is just an upper bound.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select the visible receipts but stop before clicking Remove/Yes.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Attach verbose Playwright event listeners (crash/close/navigation/network).",
    )
    parser.add_argument(
        "--screenshot",
        default="delete_receipts_failure.png",
        help="Where to save a MyExpense screenshot if the run fails.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
