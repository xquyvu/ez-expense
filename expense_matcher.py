from datetime import date, timedelta
from enum import Enum
from typing import Any


class MatchKind(Enum):
    """How a receipt matched an expense line.

    This is the authoritative criterion for distinguishing match types; the numeric score
    is derived from it (see ``MATCH_SCORES``). Identifying a next-day match must always be
    done via ``MatchKind.NEXT_DAY`` rather than by comparing the float score, so that an
    unrelated rule producing the same score can never be mistaken for a next-day match.
    """

    NONE = "none"
    EXACT = "exact"
    NEXT_DAY = "next_day"


# Numeric confidence associated with each match kind (surfaced to the UI as score * 100).
MATCH_SCORES: dict[MatchKind, float] = {
    MatchKind.NONE: 0.0,
    MatchKind.EXACT: 1.0,
    MatchKind.NEXT_DAY: 0.5,
}


def classify_receipt_match(receipt: dict[str, Any], expense_line: dict[str, Any]) -> MatchKind:
    """
    Classify how a receipt matches an expense line.

    Currency and amount must always match. With a matching date the result is
    ``MatchKind.EXACT``; when the expense date is exactly one day after the invoice date it
    is ``MatchKind.NEXT_DAY`` (the invoice is on the correct date but the expense can take an
    extra day to reflect on the balance). Anything else is ``MatchKind.NONE``.

    Args:
        receipt: Receipt object to be matched, optionally with extracted invoice details
        expense_line: Expense line from the expense table
    """
    invoice_details = receipt.get("invoiceDetails")

    if not invoice_details:
        # If no invoice details are present, we cannot match
        return MatchKind.NONE

    same_currency = expense_line["Currency"] == invoice_details["Currency"]
    same_amount = float(expense_line["Amount"]) == float(invoice_details["Amount"])

    if not (same_currency and same_amount):
        return MatchKind.NONE

    if expense_line["Date"] == invoice_details["Date"]:
        return MatchKind.EXACT

    # The expense may take an extra day to reflect on the balance, so an expense dated
    # exactly one day after the invoice is still considered a (partial) match.
    try:
        invoice_date = date.fromisoformat(invoice_details["Date"])
        expense_date = date.fromisoformat(expense_line["Date"])
    except (ValueError, TypeError):
        return MatchKind.NONE

    if expense_date - invoice_date == timedelta(days=1):
        return MatchKind.NEXT_DAY

    return MatchKind.NONE


def receipt_match_score(receipt: dict[str, Any], expense_line: dict[str, Any]) -> float:
    """
    Return the numeric match score between a receipt and an expense.

    This is the confidence associated with the match kind (1.0 exact, 0.5 next-day, 0.0 no
    match) and is surfaced to the UI as a percentage. Use :func:`classify_receipt_match`
    when you need to know *why* a receipt matched rather than just the score.

    Args:
        receipt: Receipt object to be matched, optionally with extracted invoice details
        expense_line: Expense line from the expense table
    """
    return MATCH_SCORES[classify_receipt_match(receipt, expense_line)]


def _attach_receipt_to_expense(
    receipt: dict[str, Any],
    expense_line: dict[str, Any],
    invoice_details: dict[str, Any],
    score: float,
) -> None:
    """Attach a matched receipt to an expense line and back-fill missing fields."""
    expense_line["receipts"].append(receipt)
    receipt["confidence"] = score * 100

    # Fill in merchant and additional information from invoice details if available.
    # Only update if the expense fields are empty or undefined.
    merchant_value = expense_line.get("Merchant") or ""
    if invoice_details.get("Merchant") and not str(merchant_value).strip():
        expense_line["Merchant"] = invoice_details["Merchant"]

    additional_info_value = expense_line.get("Additional information") or ""
    if invoice_details.get("Additional information") and not str(additional_info_value).strip():
        expense_line["Additional information"] = invoice_details["Additional information"]


def match_receipts_with_expenses(
    bulk_receipts: list[dict[str, Any]], expense_data: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Match receipts and expense data.

    Matching runs in two passes so that exact matches always take precedence over
    next-day (partial) matches: the first pass links exact matches and the second pass
    links the remaining receipts to an expense dated one day later. Each pass selects
    pairs by their :class:`MatchKind`, never by the numeric score, so the next-day pass
    can only ever pick up genuine next-day matches.

    Args:
        bulk_receipts: List of bulk receipt objects, optionally with extracted invoice details
        expense_data: List of expense data objects from the expense table
    """
    matched_expense_indices: set[int] = set()
    matched_receipt_indices: set[int] = set()

    for required_kind in (MatchKind.EXACT, MatchKind.NEXT_DAY):
        for receipt_idx, receipt in enumerate(bulk_receipts):
            if receipt_idx in matched_receipt_indices:
                continue

            invoice_details = receipt.get("invoiceDetails")
            if not invoice_details:
                # Skip if there is no invoice details parsed
                continue

            for expense_line_idx, expense_line in enumerate(expense_data):
                if expense_line_idx in matched_expense_indices:
                    continue  # Skip already matched expenses

                if classify_receipt_match(receipt, expense_line) == required_kind:
                    _attach_receipt_to_expense(
                        receipt, expense_line, invoice_details, MATCH_SCORES[required_kind]
                    )
                    matched_expense_indices.add(expense_line_idx)
                    matched_receipt_indices.add(receipt_idx)
                    break

    unmatched_receipts = [
        receipt
        for receipt_idx, receipt in enumerate(bulk_receipts)
        if receipt_idx not in matched_receipt_indices
    ]

    return (
        expense_data,
        unmatched_receipts,
    )
