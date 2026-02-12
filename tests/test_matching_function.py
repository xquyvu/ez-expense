#!/usr/bin/env python3
"""Test the expense matching functions directly."""


from expense_matcher import match_receipts_with_expenses, receipt_match_score


def test_receipt_match_score_perfect_match():
    """Test receipt_match_score with a perfect match."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-01-15",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2024-01-15",
        "Currency": "USD",
        "Description": "Test expense",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 1.0, "Perfect match should return score of 1.0"


def test_receipt_match_score_no_invoice_details():
    """Test receipt_match_score when receipt has no invoice details."""
    receipt = {"name": "receipt1.pdf"}

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2024-01-15",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Receipt without invoice details should return 0.0"


def test_receipt_match_score_amount_mismatch():
    """Test receipt_match_score when amounts don't match."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-01-15",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "30.00",
        "Date": "2024-01-15",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Mismatched amounts should return 0.0"


def test_receipt_match_score_date_mismatch():
    """Test receipt_match_score when dates don't match."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-01-15",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2024-01-16",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Mismatched dates should return 0.0"


def test_receipt_match_score_currency_mismatch():
    """Test receipt_match_score when currencies don't match."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-01-15",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2024-01-15",
        "Currency": "GBP",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Mismatched currencies should return 0.0"


def test_match_receipts_with_expenses_single_match():
    """Test match_receipts_with_expenses with a single matching receipt."""
    bulk_receipts = [
        {
            "name": "receipt1.pdf",
            "invoiceDetails": {
                "Amount": 25.99,
                "Date": "2024-01-15",
                "Currency": "USD",
            },
        }
    ]

    expense_data = [
        {
            "id": "exp1",
            "Amount": "25.99",
            "Date": "2024-01-15",
            "Currency": "USD",
            "Description": "Test expense",
            "receipts": [],
        }
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    assert len(matched_expense_data) == 1, "Should have 1 matched expense"
    assert len(unmatched_receipts) == 0, "Should have 0 unmatched receipts"
    assert matched_expense_data[0]["id"] == "exp1"
    assert len(matched_expense_data[0]["receipts"]) == 1
    assert matched_expense_data[0]["receipts"][0]["name"] == "receipt1.pdf"


def test_match_receipts_with_expenses_no_match():
    """Test match_receipts_with_expenses when receipt doesn't match any expense."""
    bulk_receipts = [
        {
            "name": "receipt1.pdf",
            "invoiceDetails": {
                "Amount": 25.99,
                "Date": "2024-01-15",
                "Currency": "USD",
            },
        }
    ]

    expense_data = [
        {
            "id": "exp1",
            "Amount": "30.00",
            "Date": "2024-01-16",
            "Currency": "USD",
            "Description": "Different expense",
            "receipts": [],
        }
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    # Function returns all expense data, but none should have receipts attached
    assert len(matched_expense_data) == 1, "Should return all expense data"
    assert len(matched_expense_data[0]["receipts"]) == 0, "Expense should have no receipts"
    assert len(unmatched_receipts) == 1, "Should have 1 unmatched receipt"
    assert unmatched_receipts[0]["name"] == "receipt1.pdf"


def test_match_receipts_with_expenses_multiple_receipts():
    """Test match_receipts_with_expenses with multiple receipts."""
    bulk_receipts = [
        {
            "name": "receipt1.pdf",
            "invoiceDetails": {
                "Amount": 25.99,
                "Date": "2024-01-15",
                "Currency": "USD",
            },
        },
        {
            "name": "receipt2.pdf",
            "invoiceDetails": {
                "Amount": 42.00,
                "Date": "2024-01-16",
                "Currency": "USD",
            },
        },
        {
            "name": "receipt3.pdf",
            "invoiceDetails": {
                "Amount": 100.00,
                "Date": "2024-01-17",
                "Currency": "USD",
            },
        },
    ]

    expense_data = [
        {
            "id": "exp1",
            "Amount": "25.99",
            "Date": "2024-01-15",
            "Currency": "USD",
            "Description": "First expense",
            "receipts": [],
        },
        {
            "id": "exp2",
            "Amount": "42.00",
            "Date": "2024-01-16",
            "Currency": "USD",
            "Description": "Second expense",
            "receipts": [],
        },
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    assert len(matched_expense_data) == 2, "Should have 2 matched expenses"
    assert len(unmatched_receipts) == 1, "Should have 1 unmatched receipt"
    assert unmatched_receipts[0]["name"] == "receipt3.pdf"


def test_match_receipts_with_expenses_receipt_without_invoice_details():
    """Test match_receipts_with_expenses with receipt missing invoice details."""
    bulk_receipts = [
        {"name": "receipt1.pdf"},  # No invoice details
        {
            "name": "receipt2.pdf",
            "invoiceDetails": {
                "Amount": 42.00,
                "Date": "2024-01-16",
                "Currency": "USD",
            },
        },
    ]

    expense_data = [
        {
            "id": "exp1",
            "Amount": "42.00",
            "Date": "2024-01-16",
            "Currency": "USD",
            "Description": "Test expense",
            "receipts": [],
        }
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    assert len(matched_expense_data) == 1, "Should have 1 matched expense"
    assert len(unmatched_receipts) == 1, "Should have 1 unmatched receipt"
    assert unmatched_receipts[0]["name"] == "receipt1.pdf"
    assert matched_expense_data[0]["receipts"][0]["name"] == "receipt2.pdf"


def test_match_receipts_with_expenses_empty_inputs():
    """Test match_receipts_with_expenses with empty inputs."""
    matched_expense_data, unmatched_receipts = match_receipts_with_expenses([], [])

    assert len(matched_expense_data) == 0, "Should have 0 matched expenses"
    assert len(unmatched_receipts) == 0, "Should have 0 unmatched receipts"
