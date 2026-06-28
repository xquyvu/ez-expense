"""End-to-end driver for the hotel ITEMIZATION flow against real MyExpense.

For each receipt in a folder this:
  1. uploads it + extracts invoice details (Copilot/Azure/local),
  2. creates a new expense line in MyExpense (via the front-end fill endpoint),
  3. extracts the hotel itemization (line items grouped by subcategory) from the receipt, and
  4. fills the MyExpense "Itemize" dialog for that just-created (open) line.

It connects to the already-running debug browser the app uses (same one a user drives),
so it exercises the real MyExpense page. Screenshots are written between steps for review.

Prerequisites:
- Debug browser (Edge/Chrome) running with remote debugging on port 9222, signed in to MyExpense.

Usage:
    uv run -m scripts.drive_itemization_e2e \\
        --report-number D10710000200380 \\
        --receipts-dir "/Users/quyvu/Desktop/receipts/Hotels for Peter" \\
        --provider copilot --max 1
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# navigate-to-report is gated behind AI_DEBUG; it also pins the browser port to 9222.
os.environ.setdefault("AI_DEBUG", "True")

DEFAULT_WORKSPACE_URL = "https://myexpense.operations.dynamics.com/?cmp=1071&mi=ExpenseWorkspace"


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


async def setup_session(browser_port: int, workspace_url: str | None):
    """Connect to the debug browser, register its page with the app, return (client, page, pw)."""
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

    if workspace_url and "dynamics.com" not in (page.url or ""):
        try:
            await page.goto(workspace_url, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001
            _log(f"[warn] could not navigate to workspace URL: {exc}")

    playwright_manager.set_current_page(page)

    from front_end.app import create_app

    # The repo .env sets IMPORT_EXPENSE_MOCK=True; force real imports so /import reads the
    # actual report grid (we need real Created IDs to target itemization).
    import config as _config
    from front_end.routes import expense_routes as _expense_routes

    _config.IMPORT_EXPENSE_MOCK = False
    _expense_routes.IMPORT_EXPENSE_MOCK = False

    app = create_app()
    return app.test_client(), page, playwright


async def navigate(client, report_number: str) -> None:
    resp = await client.post(
        "/api/expenses/navigate-to-report", json={"report_number": report_number}
    )
    data = await resp.get_json()
    if resp.status_code != 200 or not (data or {}).get("success"):
        raise RuntimeError(f"navigate-to-report failed [{resp.status_code}]: {data}")


async def navigate_direct(client, page, report_number: str, workspace_url: str) -> None:
    """Open a report reliably: land on a clean workspace list first, then use the app's navigate.

    The app's navigate-to-report is unreliable from the dashboard or a stuck page, but works
    consistently once we force a fresh ExpenseWorkspace list via page.goto.
    """
    await page.goto(workspace_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await navigate(client, report_number)


async def upload_and_extract(client, file: Path, provider: str) -> dict:
    """Upload a receipt and extract its invoice details. Returns {receipt, invoiceDetails}."""
    from werkzeug.datastructures import FileStorage

    with open(file, "rb") as handle:
        up = await client.post(
            "/api/receipts/upload", files={"file": FileStorage(stream=handle, filename=file.name)}
        )
    up_data = await up.get_json()
    if up.status_code != 200 or not (up_data or {}).get("success"):
        raise RuntimeError(f"upload failed for {file.name}: {up_data}")
    info = up_data["file_info"]
    receipt = {
        "name": info["original_filename"],
        "filePath": info["file_path"],
        "filename": info["saved_filename"],
    }

    with open(file, "rb") as handle:
        ex = await client.post(
            "/api/receipts/extract_invoice_details",
            files={"file": FileStorage(stream=handle, filename=file.name)},
            form={"provider": provider} if provider else {},
        )
    ex_data = await ex.get_json()
    if ex.status_code != 200 or not (ex_data or {}).get("success"):
        raise RuntimeError(f"extract failed for {file.name}: {ex_data}")
    return {"receipt": receipt, "invoiceDetails": ex_data["invoice_details"]}


async def create_expense(client, invoice: dict, receipt: dict) -> dict | None:
    """Create a single new expense line in MyExpense via the fill endpoint (SSE)."""
    expense = {
        "Date": invoice.get("Date", ""),
        "Amount": str(invoice.get("Amount", "")),
        "Currency": invoice.get("Currency", ""),
        "Merchant": invoice.get("Merchant", ""),
        "Expense category": invoice.get("Expense category", ""),
        "Additional information": invoice.get("Additional information", "") or "",
        "Receipts": [{"filePath": receipt["filePath"], "name": receipt.get("name")}],
    }
    payload = {"expenses": [expense], "timestamp": datetime.datetime.now().isoformat()}
    resp = await client.post("/api/expenses/fill-expense-report", json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"fill rejected [{resp.status_code}]: {await resp.get_json()}")

    last_event, buffer = None, ""
    async for chunk in resp.response:
        buffer += chunk.decode(errors="replace")
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            if line.startswith("data: "):
                last_event = json.loads(line[len("data: ") :])
                if last_event.get("status") in ("progress", "complete", "error"):
                    _log(f"[create] {last_event.get('status')}: {last_event.get('message', '')}")
    return last_event


async def save_screenshot(client, out_path: str) -> None:
    try:
        resp = await client.get("/api/expenses/screenshot")
        if resp.status_code == 200:
            Path(out_path).write_bytes(await resp.get_data())
            _log(f"[screenshot] saved {out_path}")
        else:
            _log(f"[warn] screenshot returned {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        _log(f"[warn] screenshot failed: {exc}")


def gather_receipts(receipts_dir: str) -> list[Path]:
    base = Path(receipts_dir).expanduser()
    if not base.is_dir():
        raise FileNotFoundError(f"receipts directory not found: {base}")
    return [f for f in sorted(base.iterdir()) if f.is_file() and f.name != ".DS_Store"]


async def _open_line_created_id(page) -> str | None:
    """Return the newest line's Created ID (highest value) from the rendered grid DOM.

    Robust against the import endpoint's virtualization limits: the line we just created is
    open/rendered and has the highest (newest) Created ID in the report.
    """
    return await page.evaluate(
        """() => {
            const ids = [...document.querySelectorAll('input[aria-label="Created ID"]')]
                .map(i => (i.value || '').trim()).filter(v => /^\\d+$/.test(v));
            if (!ids.length) return null;
            return ids.reduce((a, b) => (BigInt(b) > BigInt(a) ? b : a));
        }"""
    )


async def _wait_for_idle(page, timeout_ms: int = 40000) -> None:
    """Wait for MyExpense's shell blocking overlay (server 'processing') to clear."""
    try:
        await page.wait_for_function(
            """() => {
                const d = document.querySelector('#ShellBlockingDiv');
                return !d || getComputedStyle(d).display === 'none' || d.offsetParent === null;
            }""",
            timeout=timeout_ms,
        )
    except Exception:  # noqa: BLE001
        pass
    await page.wait_for_timeout(1500)


async def run(args: argparse.Namespace) -> int:
    from invoice_extractor import extract_hotel_itemization

    client, page, playwright = await setup_session(args.browser_port, args.workspace_url)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []
    try:
        # Let any in-flight MyExpense operation settle, then close an itemization dialog left
        # open from a previous run (it would otherwise intercept clicks during navigation).
        await page.wait_for_timeout(3000)
        close_btn = page.locator("button[name='CloseButton']")
        for _ in range(5):
            try:
                await page.keyboard.press("Escape")
            except Exception:  # noqa: BLE001
                pass
            try:
                if await close_btn.count() > 0 and await close_btn.first.is_visible():
                    await close_btn.first.click()
                    await page.wait_for_timeout(1200)
                    continue
            except Exception:  # noqa: BLE001
                pass
            break

        _log(f"[step] navigate -> {args.report_number}")
        await navigate_direct(client, page, args.report_number, args.workspace_url)

        files = gather_receipts(args.receipts_dir)
        if args.max and args.max > 0:
            files = files[: args.max]
        _log(f"[receipts] processing {len(files)} file(s)")
        last_created_id = None

        for idx, file in enumerate(files, start=1):
            _log(f"\n===== [{idx}/{len(files)}] {file.name} =====")
            record: dict = {"file": file.name}
            try:
                extracted = await upload_and_extract(client, file, args.provider)
                inv = extracted["invoiceDetails"]
                record["invoice"] = inv
                _log(
                    f"[extract] {inv.get('Merchant', '?')} | {inv.get('Date')} | "
                    f"{inv.get('Amount')} {inv.get('Currency')} | cat={inv.get('Expense category')}"
                )
                if not inv:
                    record["status"] = "extract_empty"
                    summary.append(record)
                    continue

                # Wait for any prior itemization's server commit ('processing' overlay) to clear
                # so the New-expense click isn't blocked.
                await _wait_for_idle(page)
                await create_expense(client, inv, extracted["receipt"])
                await save_screenshot(client, str(out_dir / f"{idx:02d}_{file.stem}_created.png"))

                # The just-created line is open/rendered with the highest Created ID; read it
                # directly from the DOM (the import endpoint only sees the virtualized top rows),
                # then itemize via the real route (which locates+opens the line by Created ID).
                created_id = await _open_line_created_id(page)
                record["created_id"] = created_id

                if created_id and created_id == last_created_id:
                    # No new line appeared (create was blocked) — don't itemize the previous line.
                    record["status"] = "create_failed_no_new_line"
                    _log("[create] no new line detected (Created ID unchanged); skipping itemize")
                    await save_screenshot(
                        client, str(out_dir / f"{idx:02d}_{file.stem}_ERROR.png")
                    )
                    summary.append(record)
                    continue
                last_created_id = created_id

                lines = await extract_hotel_itemization(
                    extracted["receipt"]["filePath"], provider=args.provider
                )
                record["itemization_lines"] = lines
                _log(f"[itemize] {created_id}: {len(lines)} line(s): {json.dumps(lines)}")

                if created_id and lines:
                    fr = await client.post(
                        "/api/expenses/itemize/fill",
                        json={"items": [{"created_id": created_id, "lines": lines}]},
                    )
                    fr_data = await fr.get_json()
                    record["fill_result"] = fr_data
                    line_ok = bool(
                        fr_data.get("success")
                        and fr_data.get("results")
                        and fr_data["results"][0].get("success")
                    )
                    record["status"] = "ok" if line_ok else "itemize_failed"
                    _log(f"[itemize] result: {fr_data.get('message')}")
                else:
                    record["status"] = "created_no_itemization"

                await save_screenshot(client, str(out_dir / f"{idx:02d}_{file.stem}_itemized.png"))
            except Exception as exc:  # noqa: BLE001 - keep going so one bad receipt isn't fatal
                _log(f"[error] {file.name}: {exc}")
                record["status"] = f"error: {exc}"
                await save_screenshot(client, str(out_dir / f"{idx:02d}_{file.stem}_ERROR.png"))
            summary.append(record)

        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
        _log(f"\n[done] summary written to {out_dir / 'summary.json'}")
        ok = sum(1 for r in summary if r.get("status") == "ok")
        _log(f"[result] {ok}/{len(summary)} receipts created + itemized")
        return 0 if ok > 0 else 1
    finally:
        try:
            await playwright.stop()
        except Exception:  # noqa: BLE001
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive create + itemize for hotel receipts.")
    parser.add_argument("--report-number", required=True)
    parser.add_argument("--receipts-dir", required=True)
    parser.add_argument("--provider", default="copilot", help="copilot|azure|local")
    parser.add_argument("--max", type=int, default=0, help="Limit receipts processed (0 = all).")
    parser.add_argument(
        "--browser-port", type=int, default=int(os.getenv("EZ_EXPENSE_BROWSER_PORT", "9222"))
    )
    parser.add_argument("--workspace-url", default=DEFAULT_WORKSPACE_URL)
    parser.add_argument("--out-dir", default="scripts/_itemization_e2e_out")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
