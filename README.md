# Easy expense

## Installation

`uvx playwright install chromium --with-deps --no-shell`

## Bugs to fix

### High priority

- [x] Deduplicate receipts across the whole app
- FIX THE MATCH RECEIPT ROUTE: When uploading receipt directly to the expense table, only check if the info is correct. Currently this route is being shared by the bulk upload as well.
- WHEN IMPORTING EXPENSE DATA FROM MY EXPENSE, SPLIT AMOUNT AND CURRENCY INTO 2 COLUMNS

### Low priority

- When receipts are dragged inside the bulk upload area, they are grey out
