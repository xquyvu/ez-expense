#!/usr/bin/env python3
"""
Create a simple test case to manually test the frontend
"""

import requests


def create_test_scenario():
    """Create a test scenario that can be manually tested in the browser."""

    print("🧪 Creating test scenario for manual browser testing...")
    print("=" * 60)

    # Test data that should work
    test_data = {
        "bulk_receipts": [
            {
                "name": "test_receipt.pdf",
                "file_path": "/tmp/test_receipt.pdf",
                "type": "pdf",
                "invoiceDetails": {"Amount": 100.00, "Date": "2025-09-21", "Currency": "USD"},
            }
        ],
        "expense_data": [
            {
                "id": "test_exp_001",
                "Amount": "100.00 USD",
                "Date": "2025-09-21",
                "Description": "Test Expense for Manual Testing",
                "Category": "Testing",
            }
        ],
    }

    print("📋 Test Data:")
    print(f"  Receipt: {test_data['bulk_receipts'][0]['name']}")
    print(f"  Amount: {test_data['bulk_receipts'][0]['invoiceDetails']['Amount']}")
    print(f"  Date: {test_data['bulk_receipts'][0]['invoiceDetails']['Date']}")
    print()
    print(f"  Expense ID: {test_data['expense_data'][0]['id']}")
    print(f"  Amount: {test_data['expense_data'][0]['Amount']}")
    print(f"  Date: {test_data['expense_data'][0]['Date']}")
    print()

    try:
        print("🚀 Sending request to backend...")
        response = requests.post(
            "http://127.0.0.1:5001/api/receipts/match_bulk_receipts", json=test_data, timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Backend response received successfully!")

            # Check if receipts were matched
            matched_data = result.get("matched_expense_data", [])
            if matched_data and len(matched_data) > 0:
                expense = matched_data[0]
                if "receipts" in expense and len(expense["receipts"]) > 0:
                    print(f"✅ Receipt successfully matched to expense {expense['id']}")
                    print(f"   Receipt name: {expense['receipts'][0]['name']}")
                    print()
                    print("🔍 Manual Testing Instructions:")
                    print("1. Open browser to http://127.0.0.1:5001")
                    print("2. Import the following expense data (CSV format):")
                    print("   Amount,Date,Description,Category")
                    print("   100.00 USD,2025-09-21,Test Expense for Manual Testing,Testing")
                    print("3. Add bulk receipt with invoice details:")
                    print("   - Name: test_receipt.pdf")
                    print("   - Amount: 100.00")
                    print("   - Date: 2025-09-21")
                    print("   - Currency: USD")
                    print("4. Click 'Match receipts with expenses' button")
                    print("5. Check browser console for debugging logs")
                    print("6. Verify receipt appears in expense table 'Receipts' column")
                else:
                    print("❌ No receipts found in matched expense data")
            else:
                print("❌ No matched expense data returned")
        else:
            print(f"❌ Backend error: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("   Make sure Flask app is running on http://127.0.0.1:5001")


if __name__ == "__main__":
    create_test_scenario()
