# Easy expense

## Installation

`uvx playwright install chromium --with-deps --no-shell`

## Bugs to fix

### High priority

- [x] Async request to OpenAI not working in Flask
- [x] Deduplicate receipts across the whole app
- [x] FIX THE MATCH RECEIPT ROUTE: When uploading receipt directly to the expense table, only check if the info is correct. Currently this route is being shared by the bulk upload as well.
- [x] WHEN IMPORTING EXPENSE DATA FROM MY EXPENSE, SPLIT AMOUNT AND CURRENCY INTO 2 COLUMNS
- [x] filePath key for files that didn't get matched doesn't exist
- [ ] Refund not giving minus value
- [ ] additional description for existing expense didn't get fill
- [ ] Ask the user to zoom out so that all expenses are visible

### Low priority

- [x] When receipts are dragged inside the bulk upload area, they are grey out
