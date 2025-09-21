from typing import Any

import pandas as pd


def receipt_match_score(receipt: dict[str, Any], expense_line: dict[str, Any]) -> float:
    """
    Calculate the match score between a receipt and an expense.

    Args:
        receipt: Receipt object to be matched, optionally with extracted invoice details
        expense_line: Expense line from the expense table
    """
    invoice_details = receipt.get("invoiceDetails")

    if not invoice_details:
        # If no invoice details are present, we cannot match
        return 0.0

    if all(
        [
            expense_line["Date"] == invoice_details["Date"],
            expense_line["Currency"] == invoice_details["Currency"],
            expense_line["Amount"] == invoice_details["Amount"],
        ]
    ):
        return 1.0

    return 0.0


def match_receipts_with_expenses(
    bulk_receipts: list[dict[str, Any]], expense_data: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Match receipts and expense data.

    Args:
        bulk_receipts: List of bulk receipt objects, optionally with extracted invoice details
        expense_data: List of expense data objects from the expense table
    """
    expense_data_df = pd.DataFrame(expense_data)

    # TODO: REMOVE THIS ONCE CURRENCY AND AMOUNT ARE SEPARATED
    expense_data_df[["Amount", "Currency"]] = expense_data_df["Amount"].str.split(" ", expand=True)
    expense_data_df["Amount"] = expense_data_df["Amount"].astype(float)

    receipt = bulk_receipts[0]

    unmatched_receipts = []
    matched_expense_indices: list[int] = []

    for receipt in bulk_receipts:
        invoice_details = receipt.get("invoiceDetails")

        if not invoice_details:
            # Skip if there is no invoice details parsed
            unmatched_receipts.append(receipt)
            continue

        # Match the receipt with the expense's date and currency
        for expense_line_idx, expense_line in expense_data_df.iterrows():
            if expense_line_idx in matched_expense_indices:
                continue  # Skip already matched expenses

            # Receipt matching
            if receipt_match_score(receipt, expense_line) == 1.0:
                expense_data_df.loc[expense_line_idx, "receipts"].append(receipt)
                matched_expense_indices.append(expense_line_idx)
                break

        else:
            # No match found for this receipt
            unmatched_receipts.append(receipt)

    return (
        expense_data_df.to_dict(orient="records"),
        unmatched_receipts,
    )
