#!/usr/bin/env python3
"""
Simple test script to verify the fill-expense-report endpoint works correctly.
"""

import json
from datetime import datetime

import pytest
import requests

from config import FRONTEND_PORT


def test_fill_expense_report_endpoint():
    """Test the /api/expenses/fill-expense-report endpoint"""

    # Base URL for the Flask app (using correct port from config)
    base_url = f"http://localhost:{FRONTEND_PORT}"
    endpoint = f"{base_url}/api/expenses/fill-expense-report"  # Sample test data
    test_data = {
        "expenses": [
            {
                "id": "exp_001",
                "description": "Business lunch",
                "amount": 45.67,
                "date": "2025-09-20",
                "category": "Meals",
                "attachedReceipts": [
                    {"name": "lunch_receipt.jpg", "size": 1024, "type": "image/jpeg"}
                ],
            },
            {
                "id": "exp_002",
                "description": "Taxi fare",
                "amount": 23.45,
                "date": "2025-09-20",
                "category": "Transportation",
                "attachedReceipts": [],
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
    except AssertionError:
        raise
    except Exception as e:
        pytest.fail(f"Test failed with error: {e}")


if __name__ == "__main__":
    print("Run with: uv run -m pytest tests/test_fill_expense_report.py -v")
