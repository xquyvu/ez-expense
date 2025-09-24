#!/usr/bin/env python3
"""
Test script for the new bulk receipt matching endpoint.
"""

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

        if response.status_code == 200:
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
            return True
        else:
            print(f"❌ Endpoint test failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except Exception:
                print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the application")
        print(f"   Please make sure the Flask app is running on http://127.0.0.1:{FRONTEND_PORT}")
        return False
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False


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

        if response.status_code == 400:
            print("✅ Validation test passed - correctly rejected missing fields")
        else:
            print(f"❌ Validation test failed - expected 400, got {response.status_code}")

    except Exception as e:
        print(f"❌ Validation test failed: {e}")


def main():
    """Run all tests."""
    print("Testing Bulk Receipt Matching Endpoint")
    print("=" * 45)

    # Test the main functionality
    success = test_bulk_receipt_matching()

    if success:
        # Test validation
        test_endpoint_validation()

        print("\n" + "=" * 45)
        print("✅ All tests completed!")
        print("\nThe new endpoint is ready to:")
        print("1. Accept bulk receipt data and expense data")
        print("2. Extract invoice details from receipts (when AI is enabled)")
        print("3. Pass the data to receipt_match_score function")
        print("4. Return matching results and scores")
    else:
        print("\n❌ Basic functionality test failed")
        print("Please check if the Flask application is running and try again")


if __name__ == "__main__":
    main()
