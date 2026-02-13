"""
Self-verifying tests against the real MyExpense automation.

These tests require:
  1. The app running with a real browser session: ``uv run python main.py``
  2. The browser navigated to a **test** expense report in MyExpense.

The tests talk to the running app via HTTP (not by importing ``create_app``).

Run:
    uv run pytest tests/test_e2e_myexpense_automation.py -v

Screenshots are saved to ``test_screenshots/`` for manual review.
"""

import os

import pytest
import requests

# Base URL of the running app — default to localhost:5001
BASE_URL = os.environ.get("EZ_EXPENSE_BASE_URL", "http://127.0.0.1:5001")

# Directory to store verification screenshots
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _save_screenshot(name: str) -> str | None:
    """Fetch a screenshot via the API and save it locally."""
    try:
        resp = requests.get(f"{BASE_URL}/api/expenses/screenshot", timeout=30)
        if resp.status_code == 200:
            path = os.path.join(SCREENSHOT_DIR, name)
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception:
        pass
    return None


# ===================================================================
# Test 1: Import from MyExpense
# ===================================================================

class TestImportFromMyExpense:
    """Import expenses from the real MyExpense portal."""

    def test_import_real(self):
        """POST /api/expenses/import/real returns expenses with correct columns."""
        resp = requests.post(f"{BASE_URL}/api/expenses/import/real", timeout=60)
        assert resp.status_code == 200, f"Import failed: {resp.text}"

        data = resp.json()
        assert data.get("success") is True, f"Import not successful: {data}"
        assert data.get("count", 0) > 0, "No expenses returned"

        # Verify column presence
        expenses = data["data"]
        assert len(expenses) > 0
        first = expenses[0]
        for col in ("Amount", "Date", "Currency"):
            assert col in first, f"Missing expected column '{col}' in expense: {list(first.keys())}"

        # Take screenshot for verification
        screenshot_path = _save_screenshot("01_after_import.png")
        if screenshot_path:
            print(f"  Screenshot saved: {screenshot_path}")

        # Store for next test
        TestImportFromMyExpense._imported = data

    @staticmethod
    def get_imported():
        return getattr(TestImportFromMyExpense, "_imported", None)


# ===================================================================
# Test 2: Fill expense report
# ===================================================================

class TestFillExpenseReport:
    """Upload a receipt, then fill the expense report in MyExpense."""

    def test_fill_report(self):
        """Upload a test receipt and fill the expense report."""
        imported = TestImportFromMyExpense.get_imported()
        if imported is None:
            pytest.skip("Import test must pass first")

        expenses = imported["data"]

        # Use existing test screenshot as a receipt file
        test_receipt = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tests",
            "test_data",
            "test_screenshot.png",
        )
        if not os.path.exists(test_receipt):
            pytest.skip(f"Test receipt not found: {test_receipt}")

        # Upload the receipt via the API
        with open(test_receipt, "rb") as f:
            upload_resp = requests.post(
                f"{BASE_URL}/api/receipts/upload",
                files={"file": ("test_receipt.png", f, "image/png")},
                timeout=30,
            )
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        upload_data = upload_resp.json()
        assert upload_data.get("success") is True

        file_info = upload_data["file_info"]

        # Attach receipt to first expense
        first_expense = expenses[0].copy()
        first_expense["Receipts"] = [
            {
                "name": file_info["original_filename"],
                "filename": file_info["saved_filename"],
                "filePath": file_info["file_path"],
            }
        ]

        # Fill expense report
        fill_resp = requests.post(
            f"{BASE_URL}/api/expenses/fill-expense-report",
            json={
                "expenses": [first_expense],
                "timestamp": "test",
            },
            timeout=120,
        )
        assert fill_resp.status_code == 200, f"Fill failed: {fill_resp.text}"
        fill_data = fill_resp.json()
        assert fill_data.get("success") is True, f"Fill not successful: {fill_data}"

        # Take screenshot for verification
        screenshot_path = _save_screenshot("02_after_fill.png")
        if screenshot_path:
            print(f"  Screenshot saved: {screenshot_path}")

    def test_fill_20_expenses(self):
        """Fill 20 existing expenses in a row, each with a receipt."""
        imported = TestImportFromMyExpense.get_imported()
        if imported is None:
            pytest.skip("Import test must pass first")

        expenses = imported["data"]
        if len(expenses) < 20:
            pytest.skip(f"Need at least 20 expenses, got {len(expenses)}")

        test_receipt = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tests",
            "test_data",
            "test_screenshot.png",
        )
        if not os.path.exists(test_receipt):
            pytest.skip(f"Test receipt not found: {test_receipt}")

        # Upload 20 receipts (one per expense)
        file_infos = []
        for i in range(20):
            with open(test_receipt, "rb") as f:
                upload_resp = requests.post(
                    f"{BASE_URL}/api/receipts/upload",
                    files={"file": (f"receipt_{i}.png", f, "image/png")},
                    timeout=30,
                )
            assert upload_resp.status_code == 200, f"Upload {i} failed: {upload_resp.text}"
            file_infos.append(upload_resp.json()["file_info"])

        # Build 20 expenses with receipts attached
        expenses_to_fill = []
        for i in range(20):
            expense = expenses[i].copy()
            fi = file_infos[i]
            expense["Receipts"] = [
                {
                    "name": fi["original_filename"],
                    "filename": fi["saved_filename"],
                    "filePath": fi["file_path"],
                }
            ]
            expenses_to_fill.append(expense)

        # Fill all 20 in one request
        fill_resp = requests.post(
            f"{BASE_URL}/api/expenses/fill-expense-report",
            json={"expenses": expenses_to_fill, "timestamp": "test-20"},
            timeout=600,
        )
        assert fill_resp.status_code == 200, f"Fill failed: {fill_resp.text}"
        fill_data = fill_resp.json()
        assert fill_data.get("success") is True, f"Fill not successful: {fill_data}"
        assert fill_data["data"]["total_expenses"] == 20
        assert fill_data["data"]["expenses_with_receipts"] == 20

        screenshot_path = _save_screenshot("03_after_fill_20.png")
        if screenshot_path:
            print(f"  Screenshot saved: {screenshot_path}")

    def test_fill_mixed_existing_and_new(self):
        """Fill a mix of existing expenses (update) and new expenses (create)."""
        imported = TestImportFromMyExpense.get_imported()
        if imported is None:
            pytest.skip("Import test must pass first")

        expenses = imported["data"]
        if len(expenses) < 2:
            pytest.skip(f"Need at least 2 existing expenses, got {len(expenses)}")

        test_receipt = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tests",
            "test_data",
            "test_screenshot.png",
        )
        if not os.path.exists(test_receipt):
            pytest.skip(f"Test receipt not found: {test_receipt}")

        # Upload receipts for each expense we'll fill
        def _upload_receipt(name: str) -> dict:
            with open(test_receipt, "rb") as f:
                resp = requests.post(
                    f"{BASE_URL}/api/receipts/upload",
                    files={"file": (name, f, "image/png")},
                    timeout=30,
                )
            assert resp.status_code == 200, f"Upload failed: {resp.text}"
            fi = resp.json()["file_info"]
            return {
                "name": fi["original_filename"],
                "filename": fi["saved_filename"],
                "filePath": fi["file_path"],
            }

        # --- Existing expenses (have Created ID — will be updated) ---
        existing_expenses = []
        for i, expense in enumerate(expenses[:2]):
            e = expense.copy()
            e["Receipts"] = [_upload_receipt(f"existing_{i}.png")]
            existing_expenses.append(e)

        # --- New expenses (no Created ID — will be created) ---
        new_expenses = [
            {
                "Date": "2025-01-15",
                "Amount": "42.50",
                "Currency": "USD",
                "Merchant": "Test Coffee Shop",
                "Expense category": "Meals | Employee Travel",
                "Additional information": "E2E test: new expense 1",
                "Payment method": "Cash",
                "Receipts": [_upload_receipt("new_expense_1.png")],
            },
            {
                "Date": "2025-01-16",
                "Amount": "15.00",
                "Currency": "GBP",
                "Merchant": "Test Taxi Service",
                "Expense category": "Ground Transportation",
                "Additional information": "E2E test: new expense 2",
                "Payment method": "Cash",
                "Receipts": [_upload_receipt("new_expense_2.png")],
            },
        ]

        all_expenses = existing_expenses + new_expenses

        fill_resp = requests.post(
            f"{BASE_URL}/api/expenses/fill-expense-report",
            json={"expenses": all_expenses, "timestamp": "test-mixed"},
            timeout=300,
        )
        assert fill_resp.status_code == 200, f"Fill failed: {fill_resp.text}"
        fill_data = fill_resp.json()
        assert fill_data.get("success") is True, f"Fill not successful: {fill_data}"
        assert fill_data["data"]["total_expenses"] == 4
        assert fill_data["data"]["expenses_with_receipts"] == 4

        screenshot_path = _save_screenshot("04_after_fill_mixed.png")
        if screenshot_path:
            print(f"  Screenshot saved: {screenshot_path}")
