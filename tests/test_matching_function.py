#!/usr/bin/env python3
"""Test the expense matching functions directly."""


from expense_matcher import (
    MatchKind,
    classify_receipt_match,
    match_receipts_with_expenses,
    receipt_match_score,
)


def _receipt(amount=25.99, date="2024-01-15", currency="USD"):
    return {"name": "receipt1.pdf", "invoiceDetails": {"Amount": amount, "Date": date, "Currency": currency}}


def _expense(amount="25.99", date="2024-01-15", currency="USD"):
    return {"id": "exp1", "Amount": amount, "Date": date, "Currency": currency}


def test_classify_receipt_match_exact():
    assert classify_receipt_match(_receipt(), _expense()) == MatchKind.EXACT


def test_classify_receipt_match_next_day():
    assert classify_receipt_match(_receipt(date="2024-01-15"), _expense(date="2024-01-16")) == (
        MatchKind.NEXT_DAY
    )


def test_classify_receipt_match_two_days_after_is_none():
    assert classify_receipt_match(_receipt(date="2024-01-15"), _expense(date="2024-01-17")) == (
        MatchKind.NONE
    )


def test_classify_receipt_match_day_before_is_none():
    assert classify_receipt_match(_receipt(date="2024-01-15"), _expense(date="2024-01-14")) == (
        MatchKind.NONE
    )


def test_classify_receipt_match_currency_mismatch_is_none():
    assert classify_receipt_match(_receipt(), _expense(currency="GBP")) == MatchKind.NONE


def test_classify_receipt_match_amount_mismatch_next_day_is_none():
    # Next-day date but a different amount must not classify as NEXT_DAY.
    assert classify_receipt_match(
        _receipt(amount=25.99, date="2024-01-15"),
        _expense(amount="30.00", date="2024-01-16"),
    ) == MatchKind.NONE


def test_classify_receipt_match_no_invoice_details_is_none():
    assert classify_receipt_match({"name": "r.pdf"}, _expense()) == MatchKind.NONE


def test_classify_receipt_match_invalid_date_is_none():
    assert classify_receipt_match(_receipt(date=""), _expense(date="2024-01-16")) == MatchKind.NONE


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
    """Test receipt_match_score when dates don't match (and are not one day apart)."""
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
        "Date": "2024-01-20",
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


def test_receipt_match_score_next_day_match():
    """Test receipt_match_score when the expense is dated one day after the invoice."""
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
    assert score == 0.5, "Expense dated one day after the invoice should return 0.5"


def test_receipt_match_score_next_day_across_month_boundary():
    """Test receipt_match_score next-day match across a month boundary."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-01-31",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2024-02-01",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.5, "Next-day match should work across month boundaries"


def test_receipt_match_score_next_day_across_year_boundary():
    """Test receipt_match_score next-day match across a year boundary."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "2024-12-31",
            "Currency": "USD",
        },
    }

    expense_line = {
        "id": "exp1",
        "Amount": "25.99",
        "Date": "2025-01-01",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.5, "Next-day match should work across year boundaries"


def test_receipt_match_score_two_days_after_no_match():
    """Test receipt_match_score when the expense is dated two days after the invoice."""
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
        "Date": "2024-01-17",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Expense dated two days after the invoice should return 0.0"


def test_receipt_match_score_day_before_no_match():
    """Test receipt_match_score when the expense is dated one day before the invoice."""
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
        "Date": "2024-01-14",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Expense dated one day before the invoice should return 0.0"


def test_receipt_match_score_next_day_currency_mismatch():
    """Test receipt_match_score next-day rule still requires matching currency."""
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
        "Currency": "GBP",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Next-day match with a different currency should return 0.0"


def test_receipt_match_score_next_day_amount_mismatch():
    """Test receipt_match_score next-day rule still requires matching amount."""
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
        "Date": "2024-01-16",
        "Currency": "USD",
    }

    score = receipt_match_score(receipt, expense_line)
    assert score == 0.0, "Next-day match with a different amount should return 0.0"


def test_receipt_match_score_invalid_date_no_crash():
    """Test receipt_match_score returns 0.0 (no crash) for empty/invalid dates."""
    receipt = {
        "name": "receipt1.pdf",
        "invoiceDetails": {
            "Amount": 25.99,
            "Date": "",
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
    assert score == 0.0, "Empty/invalid invoice date should return 0.0 without raising"


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


def test_match_receipts_with_expenses_next_day_partial_match():
    """A receipt should match an expense dated one day later with 50% confidence."""
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
            "Date": "2024-01-16",
            "Currency": "USD",
            "Description": "Test expense",
            "receipts": [],
        }
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    assert len(unmatched_receipts) == 0, "Next-day receipt should be matched"
    assert len(matched_expense_data[0]["receipts"]) == 1
    matched_receipt = matched_expense_data[0]["receipts"][0]
    assert matched_receipt["name"] == "receipt1.pdf"
    assert matched_receipt["confidence"] == 50, "Next-day match should have 50% confidence"


def test_match_receipts_with_expenses_exact_match_sets_full_confidence():
    """An exact match should attach the receipt with 100% confidence."""
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

    assert len(unmatched_receipts) == 0
    assert matched_expense_data[0]["receipts"][0]["confidence"] == 100


def test_match_receipts_with_expenses_exact_match_preferred_over_partial():
    """Exact matches must take precedence over next-day partial matches.

    Two receipts (Jan 15 and Jan 16) share the same amount and there is a single
    expense dated Jan 16. The Jan 16 receipt must win the exact match, leaving the
    Jan 15 receipt unmatched rather than partially grabbing the expense first.
    """
    bulk_receipts = [
        {
            "name": "day_before.pdf",
            "invoiceDetails": {
                "Amount": 25.99,
                "Date": "2024-01-15",
                "Currency": "USD",
            },
        },
        {
            "name": "exact.pdf",
            "invoiceDetails": {
                "Amount": 25.99,
                "Date": "2024-01-16",
                "Currency": "USD",
            },
        },
    ]

    expense_data = [
        {
            "id": "exp1",
            "Amount": "25.99",
            "Date": "2024-01-16",
            "Currency": "USD",
            "Description": "Test expense",
            "receipts": [],
        }
    ]

    matched_expense_data, unmatched_receipts = match_receipts_with_expenses(
        bulk_receipts, expense_data
    )

    assert len(matched_expense_data[0]["receipts"]) == 1
    matched_receipt = matched_expense_data[0]["receipts"][0]
    assert matched_receipt["name"] == "exact.pdf", "Exact match should win the expense"
    assert matched_receipt["confidence"] == 100
    assert len(unmatched_receipts) == 1
    assert unmatched_receipts[0]["name"] == "day_before.pdf"
