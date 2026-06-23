"""Reusable end-to-end driver for the MyExpense fill flow.

This drives the same flow a user performs in the web UI, but programmatically: it
navigates the app's browser to an expense report, imports the expense lines, uploads
receipts, attaches them to expenses, and runs "Fill Expense Report" — all through the
front-end API against the real MyExpense page. It is intended for manual/e2e testing and
for iterating on the fill automation.

Prerequisites:
- A debug browser (Edge/Chrome) already running with remote debugging on the configured
  port (default 9222), signed in to MyExpense. This is the same browser the app uses.
- ``IMPORT_EXPENSE_MOCK=False`` so imports come from the real page.

Usage:
    uv run python -m scripts.drive_e2e \\
        --report-number D10710000215406 \\
        --receipts-dir /path/to/receipts

    # Faithful mode (real Copilot extraction + matching):
    uv run python -m scripts.drive_e2e \\
        --report-number D10710000215406 \\
        --receipts-dir /path/to/receipts \\
        --mode faithful --provider copilot

Modes:
- ``fast`` (default): skip extraction/matching; upload receipts and assign them to
  expenses round-robin so every line has a receipt. Best for iterating on the fill step.
- ``faithful``: run real invoice extraction (``--provider``) and receipt matching, then
  fill any unmatched expenses round-robin.

The process exits non-zero if the fill does not complete, and writes a screenshot of the
MyExpense page for diagnosis.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

# Make the repo importable regardless of where this is launched from.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Enable AI_DEBUG before importing config: it gates the /navigate-to-report endpoint and
# pins the browser port (so we reuse the already-running debug browser).
os.environ.setdefault("AI_DEBUG", "True")

DEFAULT_WORKSPACE_URL = "https://myexpense.operations.dynamics.com/?cmp=1071&mi=ExpenseWorkspace"

# File types MyExpense accepts as receipt attachments. HEIC is converted to JPG on upload;
# other types (notably HTML) cannot be attached and are excluded from assignment.
MYEXPENSE_ATTACHABLE_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Session setup
# ---------------------------------------------------------------------------


def _attach_diagnostics(page, context) -> None:
    """Attach verbose Playwright event listeners to diagnose mid-fill page teardown.

    Logs renderer crashes, page/context closes, frame navigations, popups, console
    errors, and failed network requests so we can see exactly what kills the target.
    """

    def _ts() -> str:
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    page.on("crash", lambda _p: _log(f"[event {_ts()}] *** PAGE CRASHED (renderer) ***"))
    page.on("close", lambda _p: _log(f"[event {_ts()}] *** PAGE CLOSED ***"))
    page.on(
        "framenavigated",
        lambda frame: (
            _log(f"[event {_ts()}] framenavigated (main) -> {frame.url}")
            if frame is page.main_frame
            else None
        ),
    )
    page.on("popup", lambda p: _log(f"[event {_ts()}] popup opened -> {p.url}"))
    page.on(
        "console",
        lambda msg: (
            _log(f"[console {_ts()}] {msg.type}: {msg.text[:200]}")
            if msg.type in ("error", "warning")
            else None
        ),
    )
    page.on("pageerror", lambda exc: _log(f"[pageerror {_ts()}] {str(exc)[:200]}"))
    page.on(
        "requestfailed",
        lambda req: _log(
            f"[netfail {_ts()}] {req.method} {req.url[:120]} :: "
            f"{(req.failure or '')[:80]}"
        ),
    )

    def _on_response(resp):
        try:
            if resp.status >= 500 or resp.status == 0:
                _log(f"[net {_ts()}] {resp.status} {resp.url[:120]}")
        except Exception:  # noqa: BLE001
            pass

    page.on("response", _on_response)
    context.on("page", lambda p: _log(f"[event {_ts()}] NEW PAGE/tab -> {p.url}"))
    context.on("close", lambda _c: _log(f"[event {_ts()}] *** CONTEXT CLOSED ***"))


async def setup_session(browser_port: int, workspace_url: str | None, diagnostics: bool = False):
    """Connect to the debug browser, register its page with the app, and build a client.

    Returns ``(client, page, playwright)``. The playwright instance is returned so the
    caller can stop it; the browser itself is left open (it's the user's debug browser).
    """
    import playwright_manager
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{browser_port}")

    context = browser.contexts[0] if browser.contexts else await browser.new_context()

    page = None
    for candidate in context.pages:
        if "dynamics.com" in (candidate.url or ""):
            page = candidate
            break
    if page is None:
        page = context.pages[0] if context.pages else await context.new_page()

    if diagnostics:
        _attach_diagnostics(page, context)

    if workspace_url:
        try:
            await page.goto(workspace_url, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001 - best-effort normalisation of start state
            _log(f"[warn] could not navigate to workspace URL: {exc}")

    playwright_manager.set_current_page(page)

    from front_end.app import create_app

    app = create_app()
    return app.test_client(), page, playwright


# ---------------------------------------------------------------------------
# Flow steps (each maps to a front-end API call)
# ---------------------------------------------------------------------------


async def navigate(client, report_number: str) -> None:
    """Open the target expense report via the app's browser page."""
    resp = await client.post(
        "/api/expenses/navigate-to-report", json={"report_number": report_number}
    )
    data = await resp.get_json()
    if resp.status_code != 200 or not (data or {}).get("success"):
        raise RuntimeError(f"navigate-to-report failed [{resp.status_code}]: {data}")


async def import_expenses(client) -> list[dict]:
    """Import the expense lines from the open report."""
    resp = await client.post("/api/expenses/import")
    data = await resp.get_json()
    if resp.status_code != 200 or not (data or {}).get("success"):
        raise RuntimeError(f"import failed [{resp.status_code}]: {data}")
    return data["data"]


def gather_receipt_files(receipts_dir: str, include_subdirs: bool) -> list[Path]:
    """Return receipt files to upload (top-level by default; ``.DS_Store`` skipped)."""
    base = Path(receipts_dir).expanduser()
    if not base.is_dir():
        raise FileNotFoundError(f"receipts directory not found: {base}")
    walker = base.rglob("*") if include_subdirs else base.iterdir()
    return [f for f in sorted(walker) if f.is_file() and f.name != ".DS_Store"]


async def upload_receipts(client, files: list[Path]) -> list[dict]:
    """Upload each receipt; return ``[{name, filePath, filename}]`` (HEIC arrives as JPG)."""
    from werkzeug.datastructures import FileStorage

    receipts: list[dict] = []
    for f in files:
        with open(f, "rb") as handle:
            storage = FileStorage(stream=handle, filename=f.name)
            resp = await client.post("/api/receipts/upload", files={"file": storage})
        data = await resp.get_json()
        if resp.status_code != 200 or not (data or {}).get("success"):
            _log(f"[warn] upload failed for {f.name} [{resp.status_code}]: {data}")
            continue
        info = data["file_info"]
        receipts.append(
            {
                "name": info["original_filename"],
                "filePath": info["file_path"],
                "filename": info["saved_filename"],
            }
        )
        _log(f"[upload] {f.name} -> {info['saved_filename']}")
    return receipts


async def extract_details(client, files: list[Path], provider: str) -> list[dict]:
    """Faithful mode: upload + extract invoice details for each receipt."""
    from werkzeug.datastructures import FileStorage

    bulk: list[dict] = []
    for f in files:
        with open(f, "rb") as handle:
            storage = FileStorage(stream=handle, filename=f.name)
            up = await client.post("/api/receipts/upload", files={"file": storage})
        up_data = await up.get_json()
        if up.status_code != 200 or not (up_data or {}).get("success"):
            _log(f"[warn] upload failed for {f.name}: {up_data}")
            continue
        info = up_data["file_info"]
        receipt = {
            "name": info["original_filename"],
            "filePath": info["file_path"],
            "filename": info["saved_filename"],
            "type": "pdf" if f.suffix.lower() == ".pdf" else "image",
        }
        with open(f, "rb") as handle:
            storage = FileStorage(stream=handle, filename=f.name)
            ex = await client.post(
                "/api/receipts/extract_invoice_details",
                files={"file": storage},
                form={"provider": provider},
            )
        ex_data = await ex.get_json()
        if ex.status_code == 200 and (ex_data or {}).get("success"):
            receipt["invoiceDetails"] = ex_data["invoice_details"]
            _log(f"[extract] {f.name} -> {ex_data['invoice_details'].get('Merchant', '?')}")
        else:
            _log(f"[warn] extraction failed for {f.name}: {ex_data}")
        bulk.append(receipt)
    return bulk


async def match(client, bulk_receipts: list[dict], expenses: list[dict]) -> tuple[list[dict], list[dict]]:
    """Faithful mode: match receipts to expenses via the API."""
    resp = await client.post(
        "/api/receipts/match_bulk_receipts",
        json={"bulk_receipts": bulk_receipts, "expense_data": expenses},
    )
    data = await resp.get_json()
    if resp.status_code != 200 or not (data or {}).get("success"):
        raise RuntimeError(f"match failed [{resp.status_code}]: {data}")
    return data["matched_expense_data"], data.get("unmatched_receipts", [])


def _receipt_payload(receipt: dict) -> dict:
    """Reduce a receipt to the fields the fill endpoint needs."""
    return {"filePath": receipt["filePath"], "name": receipt.get("name")}


def normalize_expense(expense: dict) -> dict:
    """Make an imported expense safe for the fill endpoint.

    The fill matches grid rows by the string ``value`` of the hidden "Created ID" field, so
    the posted ``Created ID`` must be a string (the web UI stringifies cell values; the raw
    import returns it as an int). Also guarantees an ``Additional information`` key.
    """
    if expense.get("Created ID") is not None:
        expense["Created ID"] = str(expense["Created ID"])
    expense["Additional information"] = expense.get("Additional information") or ""
    return expense


def assign_fast(expenses: list[dict], receipts: list[dict], per_expense: int) -> list[dict]:
    """Round-robin attach receipts so every expense has ``per_expense`` of them."""
    if not receipts:
        raise RuntimeError("no receipts uploaded to assign")
    index = 0
    for expense in expenses:
        normalize_expense(expense)
        attached = []
        for _ in range(per_expense):
            attached.append(_receipt_payload(receipts[index % len(receipts)]))
            index += 1
        expense["Receipts"] = attached
    return expenses


def assign_faithful(matched: list[dict], unmatched: list[dict], per_expense: int) -> list[dict]:
    """Use matched receipts; fill expenses that have none from the unmatched pool."""
    pool = list(unmatched)
    pool_index = 0
    for expense in matched:
        normalize_expense(expense)
        attached = [_receipt_payload(r) for r in expense.get("receipts", [])]
        while len(attached) < per_expense and pool:
            attached.append(_receipt_payload(pool[pool_index % len(pool)]))
            pool_index += 1
        expense["Receipts"] = attached
    return matched


def filter_attachable(receipts: list[dict]) -> list[dict]:
    """Keep only receipts MyExpense can attach (by the stored file's extension)."""
    keep, drop = [], []
    for receipt in receipts:
        ext = Path(receipt.get("filePath", "")).suffix.lower()
        (keep if ext in MYEXPENSE_ATTACHABLE_EXTS else drop).append(receipt)
    for receipt in drop:
        _log(f"[skip] not attachable to MyExpense: {receipt.get('name')}")
    return keep


async def zoom_out(page, level: str) -> None:
    """Best-effort: shrink the page so more grid rows render (user does this manually)."""
    try:
        await page.evaluate(f"document.body.style.zoom = '{level}'")
        _log(f"[zoom] body zoom set to {level}")
    except Exception as exc:  # noqa: BLE001 - zoom is a nicety, never fail the run over it
        _log(f"[warn] zoom failed: {exc}")


async def fill(client, expenses: list[dict]) -> dict | None:
    """Run the fill and stream its SSE progress; return the last event seen."""
    payload = {"expenses": expenses, "timestamp": datetime.datetime.now().isoformat()}
    resp = await client.post("/api/expenses/fill-expense-report", json=payload)
    if resp.status_code != 200:
        data = await resp.get_json()
        raise RuntimeError(f"fill rejected [{resp.status_code}]: {data}")

    last_event: dict | None = None
    buffer = ""
    async for chunk in resp.response:
        buffer += chunk.decode(errors="replace")
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: ") :])
            last_event = event
            status = event.get("status")
            if status == "starting":
                _log(f"[fill] starting (total={event.get('total')})")
            elif status == "progress":
                _log(f"[fill] {event.get('current')}/{event.get('total')} {event.get('label', '')}")
            elif status == "complete":
                _log(f"[fill] COMPLETE: {event.get('message')}")
            elif status == "error":
                _log(f"[fill] ERROR: {event.get('message')}")
    return last_event


async def save_screenshot(client, out_path: str) -> None:
    """Grab a screenshot of the MyExpense page for diagnosis."""
    try:
        resp = await client.get("/api/expenses/screenshot")
        if resp.status_code == 200:
            Path(out_path).write_bytes(await resp.get_data())
            _log(f"[screenshot] saved {out_path}")
        else:
            _log(f"[warn] screenshot request returned {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        _log(f"[warn] screenshot failed: {exc}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> int:
    client, page, playwright = await setup_session(
        args.browser_port, args.workspace_url, diagnostics=args.diagnostics
    )
    try:
        _log(f"[step] navigate -> {args.report_number}")
        await navigate(client, args.report_number)

        _log("[step] import expenses")
        expenses = await import_expenses(client)
        _log(f"[import] {len(expenses)} expense line(s)")
        if not expenses:
            _log("[error] no expenses imported; nothing to fill")
            return 1
        if args.max_expenses and args.max_expenses > 0:
            expenses = expenses[: args.max_expenses]
            _log(f"[import] limited to first {len(expenses)} expense(s)")

        files = gather_receipt_files(args.receipts_dir, args.include_subdirs)
        _log(f"[receipts] {len(files)} file(s) from {args.receipts_dir}")
        if not files:
            _log("[error] no receipt files found")
            return 1

        if args.mode == "faithful":
            _log(f"[step] extract ({args.provider}) + match")
            bulk = await extract_details(client, files, args.provider)
            matched, unmatched = await match(client, bulk, expenses)
            expenses = assign_faithful(matched, unmatched, args.receipts_per_expense)
        else:
            _log("[step] upload receipts + assign (fast mode)")
            receipts = await upload_receipts(client, files)
            if not args.allow_all_types:
                receipts = filter_attachable(receipts)
            if not receipts:
                _log("[error] no MyExpense-attachable receipts after filtering")
                return 1
            expenses = assign_fast(expenses, receipts, args.receipts_per_expense)

        attached_total = sum(len(e.get("Receipts", [])) for e in expenses)
        _log(f"[assign] {attached_total} receipt(s) across {len(expenses)} expense(s)")

        if not args.no_zoom:
            await zoom_out(page, args.zoom_level)

        _log("[step] fill expense report")
        last = await fill(client, expenses)
        ok = bool(last and last.get("status") == "complete")
        if not ok:
            _log("[result] fill did NOT complete")
            await save_screenshot(client, args.screenshot)
            return 1

        _log("[result] fill completed successfully")
        return 0
    finally:
        try:
            await playwright.stop()
        except Exception:  # noqa: BLE001
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drive the MyExpense end-to-end fill flow through the front-end API."
    )
    parser.add_argument("--report-number", required=True, help="MyExpense report to open.")
    parser.add_argument("--receipts-dir", required=True, help="Folder of receipts to upload.")
    parser.add_argument(
        "--mode",
        choices=["fast", "faithful"],
        default="fast",
        help="fast: skip extraction/matching, assign receipts round-robin (default). "
        "faithful: real extraction + matching.",
    )
    parser.add_argument(
        "--provider",
        default="copilot",
        help="Extraction provider for faithful mode (copilot|azure|local).",
    )
    parser.add_argument(
        "--receipts-per-expense", type=int, default=1, help="Receipts to attach per expense."
    )
    parser.add_argument(
        "--max-expenses",
        type=int,
        default=0,
        help="Limit the number of expense lines filled (0 = all). Useful for quick runs.",
    )
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
        "--include-subdirs", action="store_true", help="Recurse into receipt subfolders."
    )
    parser.add_argument(
        "--allow-all-types",
        action="store_true",
        help="Do not filter out non-attachable receipt types (e.g. HTML); upload everything.",
    )
    parser.add_argument("--no-zoom", action="store_true", help="Do not zoom the page out.")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Attach verbose Playwright event listeners (crash/close/navigation/network) "
        "to diagnose mid-fill page teardown.",
    )
    parser.add_argument("--zoom-level", default="0.5", help="Body zoom level when zooming out.")
    parser.add_argument(
        "--screenshot",
        default="e2e_fill_failure.png",
        help="Where to save a MyExpense screenshot if the fill fails.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
