import pandas as pd


def import_expense() -> pd.DataFrame:
    """
    Import expenses from a website and return them as a pandas DataFrame.
    """
    # Logic to interact with the website and fetch expenses
    # This is a placeholder for the actual implementation
    expenses = [
        {"Created ID": 4, "Amount": 100.0, "Description": "Office Supplies"},
        {"Created ID": 2, "Amount": 250.0, "Description": "Travel Expenses"},
    ]

    expense_df = pd.DataFrame(expenses)

    # No need to save to file since we return the DataFrame
    # The calling code can decide what to do with the data
    return expense_df
