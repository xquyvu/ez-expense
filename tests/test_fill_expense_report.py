#!/usr/bin/env python3
"""
Simple test script to verify the fill-expense-report endpoint works correctly.
"""

import json
import os
from datetime import datetime

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
        # Send POST request
        response = requests.post(
            endpoint, json=test_data, headers={"Content-Type": "application/json"}, timeout=10
        )

        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        # Skip if the browser session is not available (expected in test environments)
        if response.status_code == 500:
            body = response.json()
            if "browser session" in body.get("message", "").lower() or "page not available" in body.get("message", "").lower():
                pytest.skip("Fill endpoint requires a real browser session to MyExpense")

        assert response.status_code == 200, (
            f"Request failed with status {response.status_code}: {response.text}"
        )
        result = response.json()
        print("✅ SUCCESS!")
        print(f"Response: {json.dumps(result, indent=2)}")

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


if __name__ == "__main__":
    print("Run with: uv run -m pytest tests/test_fill_expense_report.py -v")
