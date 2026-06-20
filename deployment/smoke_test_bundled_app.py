#!/usr/bin/env python3
"""End-to-end smoke test for EZ-Expense, driven with Playwright (no MCP).

Launches the app (the bundled executable by default, or the dev entrypoint with
--dev). The app brings up a *dedicated-profile* debug Edge in the background — it
never touches your own browser — and the Quart frontend. The test then connects
to that Edge over CDP (same pattern as the CEQE onboarding scripts), opens the
frontend, and asserts the Copilot provider resolved and is signed in.

Usage:
    uv run python deployment/smoke_test_bundled_app.py             # tests dist/ez-expense
    uv run python deployment/smoke_test_bundled_app.py --dev       # tests `uv run python main.py`
    uv run python deployment/smoke_test_bundled_app.py --exe path/to/exe
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# Allow importing the app's own modules (browser.py, etc.) regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"


def _edge_cdp_up() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as r:
            return "Edg/" in json.loads(r.read()).get("Browser", "")
    except Exception:
        return False


def connect_or_launch_edge() -> None:
    """Reuse a debug Edge on :9222, else launch a dedicated-profile one.

    Delegates to the app's own (cross-platform) BrowserProcess launcher, so this test
    runs on macOS and Windows alike and never touches the user's own browser.
    """
    if _edge_cdp_up():
        print(f"[edge] reusing existing debug Edge on {CDP_URL}")
        return
    print("[edge] launching a dedicated debug Edge via the app's BrowserProcess")
    from browser import BrowserProcess

    bp = BrowserProcess("edge", CDP_PORT)
    bp.start_browser_debug_mode()
    if not bp.wait_for_debug_port(timeout=60):
        raise RuntimeError("Edge CDP endpoint did not come up within 60s")
    print("[edge] CDP endpoint is up")


def launch_app(cmd: list[str], env: dict) -> tuple[subprocess.Popen, int]:
    """Launch the app, streaming its output, and return (process, frontend_port)."""
    print(f"[app] launching: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    port = None
    deadline = time.time() + 240
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"app exited early (code {proc.returncode})")
            continue
        sys.stdout.write("    [app] " + line)
        m = re.search(r"web interface at http://127\.0\.0\.1:(\d+)", line)
        if m:
            port = int(m.group(1))
        if "Starting hypercorn server" in line and port:
            return proc, port
    raise RuntimeError("could not detect the frontend port from app output")


def wait_for_status(port: int, timeout: float = 90) -> dict:
    url = f"http://127.0.0.1:{port}/api/model/status"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return json.loads(r.read())
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("frontend /api/model/status did not respond in time")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="run `uv run python main.py` instead of the exe")
    ap.add_argument("--exe", default="dist/ez-expense", help="path to the bundled executable")
    args = ap.parse_args()

    env = {**os.environ, "AI_DEBUG": "True", "EXTRACTION_PROVIDER": "copilot"}
    cmd = ["uv", "run", "python", "main.py"] if args.dev else [str(Path(args.exe).resolve())]

    connect_or_launch_edge()
    proc, port = launch_app(cmd, env)
    failures: list[str] = []
    try:
        status = wait_for_status(port)
        print(
            f"\n[status] copilot_available={status.get('copilot_available')} "
            f"copilot_login={status.get('copilot_login')!r} "
            f"provider={status.get('extraction_provider')}"
        )
        if status.get("copilot_available") is not True:
            failures.append("copilot_available is not True (bundled binary did not resolve / not signed in)")
        if not status.get("copilot_login"):
            failures.append("copilot_login is empty")

        # Drive the frontend over CDP and confirm the Copilot radio rendered.
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded")
            try:
                # The AI options live in a section that's display:none until an expense
                # report is imported, so assert on the DOM (attached), not visibility.
                page.wait_for_selector("#copilot-ai-checkbox", state="attached", timeout=20000)
                info = page.evaluate(
                    """() => {
                        const cb = document.getElementById('copilot-ai-checkbox');
                        const label = cb ? cb.closest('label') : null;
                        return {
                            present: !!cb,
                            disabled: cb ? cb.disabled : null,
                            text: label ? label.innerText.trim() : '',
                        };
                    }"""
                )
                print(f"[ui] copilot radio: {info}")
                if not info.get("present"):
                    failures.append("copilot radio not found in the UI")
                elif "Available" not in info.get("text", ""):
                    failures.append(f"copilot radio does not show 'Available' (text={info.get('text')!r})")
            except Exception as e:
                failures.append(f"UI check failed: {e}")
            page.close()
    finally:
        print("[teardown] stopping app")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    if failures:
        print("\n❌ FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("\n✅ PASS: app launched non-disruptively, frontend served, Copilot binary resolved + signed in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
