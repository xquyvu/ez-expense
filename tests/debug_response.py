#!/usr/bin/env python3
"""
Debug the match_bulk_receipts endpoint response
"""

import json

import requests

from config import FRONTEND_PORT


def test_response_format():
    """Test what the backend actually returns."""

    # Sample test data that should match
    test_data = {
        "bulk_receipts": [
            {
                "name": "receipt1.pdf",
                "file_path": "/tmp/test_receipt1.pdf",
                "type": "pdf",
                "invoiceDetails": {"Amount": 25.50, "Date": "2025-09-20", "Currency": "USD"},
            }
        ],
        "expense_data": [
            {
                "id": "exp1",
                "Amount": "25.50 USD",
                "Date": "2025-09-20",
                "Description": "Office supplies",
                "Category": "Business",
            }
        ],
    }

    try:
        # Test the endpoint
        response = requests.post(
            f"http://127.0.0.1:{FRONTEND_PORT}/api/receipts/match_bulk_receipts",
            json=test_data,
            timeout=10,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print("\n✅ Success! Response:")
            print(json.dumps(result, indent=2))

            # Check specifically what's in matched_expense_data
            if "matched_expense_data" in result:
                print("\n📊 Matched Expense Data Analysis:")
                for i, expense in enumerate(result["matched_expense_data"]):
                    print(f"  Expense {i + 1}:")
                    print(f"    ID: {expense.get('id', 'No ID')}")
                    print(f"    Amount: {expense.get('Amount', 'No Amount')}")
                    print(f"    Date: {expense.get('Date', 'No Date')}")
                    print(f"    Receipts field exists: {'receipts' in expense}")
                    if "receipts" in expense:
                        print(f"    Number of receipts: {len(expense['receipts'])}")
                        for j, receipt in enumerate(expense["receipts"]):
                            print(f"      Receipt {j + 1}: {receipt.get('name', 'No name')}")

            # Check unmatched receipts
            if "unmatched_receipts" in result:
                print(f"\n📋 Unmatched Receipts: {len(result['unmatched_receipts'])}")
                for i, receipt in enumerate(result["unmatched_receipts"]):
                    print(f"  Receipt {i + 1}: {receipt.get('name', 'No name')}")

        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Raw response: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    print("Testing match_bulk_receipts response format...")
    print("=" * 50)
    test_response_format()
