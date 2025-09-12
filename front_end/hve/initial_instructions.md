# Instruction

Your task is to create a web application that supports invoice and receipt management. The application should have the following functionality. Do not start the implementation yet. Follow the breadcrumb protocol in `front_end/copilot-instructions.md` to create a breadcrumb file documenting the requirements, plan, and implementation details.

## 1. Downloading expenses

- Button to import current expense from a website. The logic for this button is already implemented in the `expense_importer.py` file, in the `import_expense()` function.

## 2. Displaying and verifying expense

- Button to select a CSV file containing expense data, and import it into the web app
- Display the imported expenses in a table format on the web application.
- The table should include all columns from the CSV file.
- Allow users to verify and edit the imported expense data before finalizing it.

## 3. Matching receipts and expenses

- For each row in the table displayed on the web app in section 2:
  - Add a button to open a file dialog to select receipt files (images or PDFs).
  - Allow the user to drag and drop receipt files onto the corresponding row in the table.
- Preview the selected receipt files in the corresponding row.
- Save the paths of the selected receipt files in a new column in the table.
- Display the "confidence" of the match between the expense and the receipt files. The functionality to do so is implemented in the `receipt_matcher.py` file, in the `receipt_match_score()` function.

## 4. Exporting finalized expenses

- Button to export the finalized expenses (with matched receipts) to a new CSV file.
