#!/usr/bin/env python3
"""
Test script for the new bulk receipt matching endpoint.
"""

import pytest
import requests

from config import FRONTEND_PORT


def test_bulk_receipt_matching():
    """Test the new /api/receipts/match_bulk_receipts endpoint."""

    # Sample test data
    test_data = {
        "bulk_receipts": [
            {
                "name": "receipt1.pdf",
                "file_path": "/tmp/test_receipt1.pdf",
                "type": "pdf",
                "extract_ai": True,
                "invoiceDetails": {"Amount": 25.50, "Date": "2025-09-20", "Currency": "USD"},
            },
            {
                "name": "receipt2.pdf",
                "file_path": "/tmp/test_receipt2.pdf",
                "type": "pdf",
                "extract_ai": False,
                "invoiceDetails": {"Amount": 42.00, "Date": "2025-09-21", "Currency": "USD"},
            },
        ],
        "expense_data": [
            {
                "id": "exp1",
                "Amount": "25.50 USD",  # Changed to uppercase and proper format
                "Date": "2025-09-20",  # Changed to uppercase
                "Description": "Office supplies",  # Changed to uppercase
                "Category": "Business",  # Changed to uppercase
            },
            {
                "id": "exp2",
                "Amount": "42.00 USD",  # Changed to uppercase and proper format
                "Date": "2025-09-21",  # Changed to uppercase
                "Description": "Lunch meeting",  # Changed to uppercase
                "Category": "Meals",  # Changed to uppercase
            },
        ],
    }

    try:
        # Test the endpoint
        response = requests.post(
            f"http://127.0.0.1:{FRONTEND_PORT}/api/receipts/match_bulk_receipts",
            json=test_data,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200, f"Endpoint test failed: {response.status_code}"
        result = response.json()
        print("✅ Bulk receipt matching endpoint test successful!")
        print(f"   Match score: {result.get('match_score')}")
        print(
            f"   Bulk receipts processed: {result.get('summary', {}).get('bulk_receipts_processed')}"
        )
        print(f"   Expenses analyzed: {result.get('summary', {}).get('expenses_analyzed')}")
        print(
            f"   Receipts with AI extraction: {result.get('summary', {}).get('receipts_with_ai_extraction')}"
        )

    except requests.exceptions.ConnectionError:
        pytest.skip(f"Cannot connect to the application on http://127.0.0.1:{FRONTEND_PORT}")
    except AssertionError:
        raise
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


def test_endpoint_validation():
    """Test endpoint validation with invalid data."""

    print("\nTesting endpoint validation...")

    # Test missing required fields
    invalid_data = {"bulk_receipts": []}  # Missing expense_data

    try:
        response = requests.post(
            f"http://127.0.0.1:{FRONTEND_PORT}/api/receipts/match_bulk_receipts",
            json=invalid_data,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Validation test passed - correctly rejected missing fields")

    except requests.exceptions.ConnectionError:
        pytest.skip(f"Cannot connect to application on http://127.0.0.1:{FRONTEND_PORT}")
    except AssertionError:
        raise
    except Exception as e:
        pytest.fail(f"Validation test failed: {e}")


if __name__ == "__main__":
    print("Testing Bulk Receipt Matching Endpoint")
    print("=" * 45)
    print("\nRun with: uv run -m pytest tests/test_bulk_matching.py -v")
