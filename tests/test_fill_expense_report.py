#!/usr/bin/env python3
"""
Simple test script to verify the fill-expense-report endpoint works correctly.
"""

import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import requests

# Use the preferred port directly (not config.FRONTEND_PORT which calls
# find_available_port and picks a DIFFERENT port when the server is running).
FRONTEND_PORT = int(os.getenv("EZ_EXPENSE_FRONTEND_PORT", 5001))


def test_fill_expense_report_endpoint():
    """Test the /api/expenses/fill-expense-report endpoint"""

    # Base URL for the Flask app (using correct port from config)
    base_url = f"http://localhost:{FRONTEND_PORT}"
    endpoint = f"{base_url}/api/expenses/fill-expense-report"  # Sample test data
    test_data = {
        "expenses": [
            {
                "Date": "2025-09-20",
                "Amount": "45.67",
                "Currency": "USD",
                "Merchant": "Test Restaurant",
                "Expense category": "Meals | Employee Travel",
                "Additional information": "Business lunch",
                "Payment method": "Cash",
                "Receipts": [
                    {"name": "lunch_receipt.jpg", "filename": "lunch_receipt.jpg", "filePath": "/tmp/lunch_receipt.jpg"}
                ],
            },
            {
                "Date": "2025-09-20",
                "Amount": "23.45",
                "Currency": "USD",
                "Merchant": "Test Taxi",
                "Expense category": "Ground Transportation",
                "Additional information": "Taxi fare",
                "Payment method": "Cash",
                "Receipts": [],
            },
        ],
        "timestamp": datetime.now().isoformat(),
    }

    print("Testing /api/expenses/fill-expense-report endpoint...")
    print(f"Sending POST request to: {endpoint}")
    print(f"Test data: {len(test_data['expenses'])} expenses")

    try:
        # Stream the response so we can read progress events without waiting for the
        # whole (potentially long) browser automation to finish.
        response = requests.post(
            endpoint,
            json=test_data,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=10,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        # Skip if the browser session is not available (expected in test environments).
        # Validation/setup failures are still returned as a JSON error response.
        if response.status_code == 500:
            body = response.json()
            if (
                "browser session" in body.get("message", "").lower()
                or "page not available" in body.get("message", "").lower()
            ):
                pytest.skip("Fill endpoint requires a real browser session to MyExpense")

        assert response.status_code == 200, (
            f"Request failed with status {response.status_code}: {response.text}"
        )

        # The success path streams server-sent progress events.
        content_type = response.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type, (
            f"Expected an event stream, got Content-Type: {content_type}"
        )

        # Read the first SSE event (the deterministic "starting" event) to confirm the
        # streaming progress contract, then stop without waiting for the automation.
        first_event = None
        for raw_line in response.iter_lines():
            if raw_line and raw_line.startswith(b"data: "):
                first_event = json.loads(raw_line[len(b"data: ") :])
                break
        response.close()

        assert first_event is not None, "Expected at least one SSE progress event"
        assert "status" in first_event, f"SSE event missing 'status': {first_event}"
        assert first_event["status"] == "starting", (
            f"First SSE event should be 'starting', got: {first_event}"
        )
        assert "total" in first_event, f"'starting' event should include 'total': {first_event}"
        print("✅ SUCCESS!")
        print(f"First progress event: {json.dumps(first_event, indent=2)}")

    except requests.exceptions.ConnectionError:
        pytest.skip(
            f"Could not connect to the Flask app on localhost:{FRONTEND_PORT}. Run: uv run -m front_end.app"
        )
    except requests.exceptions.ReadTimeout:
        pytest.skip(
            "Fill endpoint timed out — likely waiting for a browser session to MyExpense"
        )
    except AssertionError:
        raise
    except Exception as e:
        pytest.fail(f"Test failed with error: {e}")


def test_fill_expense_report_rejects_empty_expenses():
    """The endpoint should reject an empty expenses array with a 400 JSON error."""
    base_url = f"http://localhost:{FRONTEND_PORT}"
    endpoint = f"{base_url}/api/expenses/fill-expense-report"

    try:
        response = requests.post(
            endpoint,
            json={"expenses": [], "timestamp": datetime.now().isoformat()},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        assert response.status_code == 400, (
            f"Expected 400 for empty expenses, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body.get("success") is False
        assert "expenses" in body.get("message", "").lower()

    except requests.exceptions.ConnectionError:
        pytest.skip(
            f"Could not connect to the Flask app on localhost:{FRONTEND_PORT}. Run: uv run -m front_end.app"
        )
    except AssertionError:
        raise
    except Exception as e:
        pytest.fail(f"Test failed with error: {e}")


def _make_fake_expense_page(created_id: str) -> MagicMock:
    """Build a fake Playwright page that satisfies the existing-expense update path."""
    row = MagicMock()
    row.click = AsyncMock()
    row.scroll_into_view_if_needed = AsyncMock()
    # Report the row as selected immediately so _wait_for_row_selected returns fast.
    row.get_attribute = AsyncMock(return_value="true")

    # The Created ID locator used by _locate_expense_line: count()=1 (rendered), and its
    # ancestor row + scrollIntoView used by _open_expense_line.
    created_locator = MagicMock()
    created_locator.count = AsyncMock(return_value=1)
    created_locator.evaluate = AsyncMock()
    created_locator.locator = MagicMock(return_value=row)
    created_locator.first = created_locator

    text_box = MagicMock()
    text_box.click = AsyncMock()
    text_box.wait_for_element_state = AsyncMock()
    text_box.fill = AsyncMock()

    # "Save and continue" force-save button used after filling/attaching each line.
    save_button = MagicMock()
    save_button.click = AsyncMock()

    page = MagicMock()
    page.locator = MagicMock(return_value=created_locator)

    # _open_expense_line verifies the open card via document.activeElement's row Created ID;
    # return the target for that probe so selection confirms (MagicMock for other evaluates).
    async def _fake_evaluate(js, *args):
        if "activeElement" in js:
            return created_id
        return MagicMock()

    page.evaluate = AsyncMock(side_effect=_fake_evaluate)
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock(return_value=None)
    page.query_selector = AsyncMock(return_value=text_box)
    page.get_by_role = MagicMock(return_value=save_button)
    return page


@pytest.mark.asyncio
async def test_fill_expense_report_streams_progress(app, monkeypatch):
    """The endpoint streams starting -> progress -> complete events (per filled line)."""
    from front_end.routes import expense_routes

    created_id = "EXP-1"
    fake_page = _make_fake_expense_page(created_id)
    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: fake_page)

    payload = {
        "expenses": [
            {
                "Created ID": created_id,
                "Merchant": "Test Restaurant",
                "Additional information": "Business lunch",
                "Receipts": [],
            }
        ],
        "timestamp": datetime.now().isoformat(),
    }

    client = app.test_client()
    response = await client.post("/api/expenses/fill-expense-report", json=payload)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("Content-Type", "")

    body = (await response.get_data()).decode()
    events = [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    statuses = [event["status"] for event in events]

    assert statuses[0] == "starting"
    assert events[0]["total"] == 1

    progress_events = [event for event in events if event["status"] == "progress"]
    assert len(progress_events) == 1
    assert progress_events[0]["current"] == 1
    assert progress_events[0]["total"] == 1

    assert statuses[-1] == "complete"
    assert events[-1]["data"]["total_expenses"] == 1

    # The line is force-saved even though it has no receipt (a text-box-only edit is not
    # auto-saved by MyExpense), via the "Save and continue" button.
    save_role_calls = [
        call.kwargs.get("name") for call in fake_page.get_by_role.call_args_list
    ]
    assert "Save and continue" in save_role_calls
    fake_page.get_by_role.return_value.click.assert_awaited()


@pytest.mark.asyncio
async def test_fill_expense_report_no_session_returns_json_error(app, monkeypatch):
    """When no browser session exists, a 500 JSON error is returned (not a stream)."""
    from front_end.routes import expense_routes

    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: None)

    payload = {
        "expenses": [{"Created ID": "EXP-1", "Additional information": "x", "Receipts": []}],
        "timestamp": datetime.now().isoformat(),
    }

    client = app.test_client()
    response = await client.post("/api/expenses/fill-expense-report", json=payload)

    assert response.status_code == 500
    data = await response.get_json()
    assert data["success"] is False
    assert "page not available" in data["message"].lower()


@pytest.mark.asyncio
async def test_fill_expense_report_rejects_concurrent_fill(app, monkeypatch):
    """A second fill while one is in progress is rejected with 409 (shared page guard)."""
    from front_end.routes import expense_routes

    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: MagicMock())
    # Simulate a fill already running.
    monkeypatch.setattr(expense_routes, "_fill_in_progress", True)

    payload = {
        "expenses": [{"Created ID": "EXP-1", "Additional information": "x", "Receipts": []}],
        "timestamp": datetime.now().isoformat(),
    }

    client = app.test_client()
    response = await client.post("/api/expenses/fill-expense-report", json=payload)

    assert response.status_code == 409
    data = await response.get_json()
    assert data["success"] is False
    assert "already running" in data["message"].lower()


class _FakeFileChooserCtx:
    """Async-context-manager stand-in for page.expect_file_chooser().

    If ``raise_timeout`` is set, ``__aexit__`` raises a Playwright TimeoutError to simulate
    the file chooser never appearing.
    """

    def __init__(self, file_chooser, raise_timeout=False):
        self._file_chooser = file_chooser
        self._raise_timeout = raise_timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        if self._raise_timeout:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError

            raise PlaywrightTimeoutError("file chooser did not appear")
        return False

    @property
    def value(self):
        file_chooser = self._file_chooser

        async def _resolve():
            return file_chooser

        return _resolve()


def _fake_upload_page():
    """Fake page for _attach_receipt_file covering the file-chooser flow."""
    page = MagicMock()
    page.click = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    async def _wait_for_selector(selector, **kwargs):
        if "ShellBlockingDiv" in selector:
            return None  # overlay already gone
        if selector == 'button[name="UploadControlBrowseButton"]':
            browse = MagicMock()
            browse.click = AsyncMock()
            return browse
        return MagicMock()

    page.wait_for_selector = AsyncMock(side_effect=_wait_for_selector)
    return page


@pytest.mark.asyncio
async def test_attach_receipt_uses_file_chooser_flow():
    """The receipt is attached via the Browse + file-chooser flow, then Upload is clicked."""
    from front_end.routes import expense_routes

    file_chooser = MagicMock()
    file_chooser.set_files = AsyncMock()

    page = _fake_upload_page()
    page.expect_file_chooser = MagicMock(
        side_effect=lambda *a, **k: _FakeFileChooserCtx(file_chooser)
    )

    await expense_routes._attach_receipt_file(page, "/tmp/receipt.jpg")

    file_chooser.set_files.assert_awaited_once_with("/tmp/receipt.jpg")
    # The upload is confirmed by clicking the Upload button.
    clicked = [call.args[0] for call in page.click.call_args_list if call.args]
    assert 'button[name="UploadControlUploadButton"]' in clicked


@pytest.mark.asyncio
async def test_attach_receipt_raises_when_chooser_never_appears():
    """If the file chooser never appears after retries, a clear error is raised."""
    from front_end.routes import expense_routes

    page = _fake_upload_page()
    # Every attempt times out (chooser never appears).
    page.expect_file_chooser = MagicMock(
        side_effect=lambda *a, **k: _FakeFileChooserCtx(MagicMock(), raise_timeout=True)
    )

    with pytest.raises(RuntimeError, match="File chooser did not appear"):
        await expense_routes._attach_receipt_file(page, "/tmp/receipt.jpg")


@pytest.mark.asyncio
async def test_open_expense_line_real_clicks_row_and_waits_for_selection():
    """The line is opened with a REAL click on its grid row, then waits for selection.

    The hidden 'Created ID' input must not be clicked directly (it stalls on actionability),
    and a synthetic JS click is not used for selection (Dynamics ignores untrusted events) —
    instead the enclosing [role=row] ancestor is really clicked.
    """
    from front_end.routes import expense_routes

    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=None)
    page.wait_for_timeout = AsyncMock()

    row = MagicMock()
    row.click = AsyncMock()
    row.scroll_into_view_if_needed = AsyncMock()
    row.get_attribute = AsyncMock(return_value="true")  # selected immediately

    line = MagicMock()
    line.evaluate = AsyncMock()  # JS scrollIntoView only
    line.click = AsyncMock()
    line.locator = MagicMock(return_value=row)

    await expense_routes._open_expense_line(page, line)

    # The hidden Created ID input itself is never clicked.
    line.click.assert_not_called()
    # The enclosing row is located by xpath ancestor and really clicked.
    assert "role='row'" in line.locator.call_args.args[0]
    row.click.assert_awaited_once()
    # JS is used only to scroll the row into view (not to click it).
    js = line.evaluate.call_args.args[0]
    assert "scrollIntoView" in js and "click()" not in js


@pytest.mark.asyncio
async def test_open_expense_line_confirms_selection_by_created_id():
    """With a created_id, selection is confirmed via the open card's Created ID."""
    from front_end.routes import expense_routes

    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=None)
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value="EXP-9")  # open card matches target
    row = MagicMock()
    row.click = AsyncMock()
    row.scroll_into_view_if_needed = AsyncMock()
    line = MagicMock()
    line.evaluate = AsyncMock()
    line.locator = MagicMock(return_value=row)

    assert await expense_routes._open_expense_line(page, line, created_id="EXP-9") is True


@pytest.mark.asyncio
async def test_open_expense_line_returns_false_when_wrong_card_opens():
    """If the open card is a different line, selection is reported as failed (callers raise)."""
    from front_end.routes import expense_routes

    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=None)
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value="OTHER")  # never matches the target
    row = MagicMock()
    row.click = AsyncMock()
    row.scroll_into_view_if_needed = AsyncMock()
    line = MagicMock()
    line.evaluate = AsyncMock()
    line.locator = MagicMock(return_value=row)

    assert await expense_routes._open_expense_line(page, line, created_id="EXP-HOTEL") is False


@pytest.mark.asyncio
async def test_locate_expense_line_scrolls_until_row_renders():
    """_locate_expense_line scrolls the virtualized grid until the target row renders."""
    from front_end.routes import expense_routes

    target = MagicMock()
    # Not rendered on the first 2 checks, then appears after scrolling.
    target.count = AsyncMock(side_effect=[0, 0, 1])
    target.first = "TARGET_LOCATOR"

    page = MagicMock()
    page.locator = MagicMock(return_value=target)
    # Each wheel-scroll iteration issues 2 evaluates: the grid_state probe (returns dict
    # with rect + renderedIds) and the verify probe (returns the new renderedIds list).
    # renderedIds change between iterations so the stale counter resets.
    page.evaluate = AsyncMock(
        side_effect=[
            {"rect": {"x": 0, "y": 0, "width": 1000, "height": 400}, "renderedIds": ["1000"]},
            ["1001"],  # verify after wheel
            {"rect": {"x": 0, "y": 0, "width": 1000, "height": 400}, "renderedIds": ["1001"]},
            ["1002"],
        ]
    )
    page.wait_for_timeout = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()

    result = await expense_routes._locate_expense_line(page, "5889114209", max_scrolls=5)

    assert result == "TARGET_LOCATOR"
    assert page.mouse.wheel.await_count >= 1


@pytest.mark.asyncio
async def test_locate_expense_line_raises_when_never_found():
    """_locate_expense_line raises a clear error if the row never renders.

    Exercises the full fallback chain: wheel scrolling stalls, keyboard nav setup fails
    (no rows to click), scroll-to-top still doesn't render the target, and the diagnostic
    dump runs before the RuntimeError.
    """
    from front_end.routes import expense_routes

    target = MagicMock()
    target.count = AsyncMock(return_value=0)  # never rendered

    # The .last locator used by keyboard nav setup raises when we try to click it (no rows),
    # which causes the keyboard nav fallback to return False and the search to keep going
    # to scroll-to-top + diagnostic dump.
    last_locator = MagicMock()
    last_locator.evaluate = AsyncMock(side_effect=Exception("no last row"))

    page = MagicMock()
    # Different page.locator() calls return different mocks; the .last accessor on the
    # "input[aria-label=...Created ID...]" locator is what keyboard nav uses.
    def locator_side_effect(selector):
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        loc.first = "FIRST_TARGET"
        loc.last = last_locator
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)
    # Grid state stays the same on every probe → renderedIds stay identical → after 2
    # consecutive no-progress wheel iterations, switch to keyboard nav (which fails),
    # then scroll-to-top + final diagnostic dump (last evaluate).
    page.evaluate = AsyncMock(
        return_value={
            "rect": {"x": 0, "y": 0, "width": 1000, "height": 400},
            "renderedIds": ["9999"],
        }
    )
    page.wait_for_timeout = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.press = AsyncMock()

    with pytest.raises(RuntimeError, match="Could not locate expense line"):
        # Re-fetch target by overriding the FIRST locator call (the one that creates the
        # target locator at the top of the function).
        page.locator.side_effect = None
        page.locator.return_value = target
        await expense_routes._locate_expense_line(page, "999", max_scrolls=3)


if __name__ == "__main__":
    print("Run with: uv run -m pytest tests/test_fill_expense_report.py -v")
