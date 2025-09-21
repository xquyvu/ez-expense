#!/usr/bin/env python3
"""
Test the match_receipts_with_expenses function directly
"""

from expense_matcher import match_receipts_with_expenses

# Sample data
bulk_receipts = [
    {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,  # Changed to float to match backend processing
            "Date": "2024-01-15",
            "Currency": "USD",
        },
    }
]

expense_data = [
    {"id": "exp1", "Amount": "25.99 USD", "Date": "2024-01-15", "Description": "Test expense"}
]

print("Testing match_receipts_with_expenses function...")
print(f"Input receipts: {len(bulk_receipts)}")
print(f"Input expenses: {len(expense_data)}")

try:
    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    print("\nResults:")
    print(f"Matched expenses: {len(matched_expense_data)}")
    print(f"Unmatched receipts: {len(unmatched_receipts)}")

    print("\nMatched expense data:")
    for expense in matched_expense_data:
        print(f"  Expense ID: {expense.get('id')}")
        print(f"  Receipts: {len(expense.get('receipts', []))}")
        if expense.get("receipts"):
            for receipt in expense["receipts"]:
                print(f"    - {receipt.get('name', 'Unknown')}")

    print("\nUnmatched receipts:")
    for receipt in unmatched_receipts:
        print(f"  - {receipt.get('name', 'Unknown')}")

    print("\n✅ Function executed successfully!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
