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
    line = MagicMock()
    line.get_attribute = AsyncMock(return_value=created_id)
    line.scroll_into_view_if_needed = AsyncMock()
    line.click = AsyncMock()

    locator = MagicMock()
    locator.all = AsyncMock(return_value=[line])

    text_box = MagicMock()
    text_box.click = AsyncMock()
    text_box.wait_for_element_state = AsyncMock()
    text_box.fill = AsyncMock()

    page = MagicMock()
    page.get_by_role = MagicMock(return_value=locator)
    page.wait_for_timeout = AsyncMock()
    page.query_selector = AsyncMock(return_value=text_box)
    return page


@pytest.mark.asyncio
async def test_fill_expense_report_streams_progress(app, monkeypatch):
    """The endpoint streams starting -> progress -> complete events (per filled line)."""
    from front_end.routes import expense_routes

    created_id = "EXP-1"
    monkeypatch.setattr(
        expense_routes, "get_expense_page", lambda: _make_fake_expense_page(created_id)
    )

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


if __name__ == "__main__":
    print("Run with: uv run -m pytest tests/test_fill_expense_report.py -v")
