# Easy expense

Help you fill expense reports with just a few clicks. Just drag your receipts into the app, and let it do the rest.

## Download and use

Go to the [Releases](https://github.com/xquyvu/ez-expense/releases) page to download the latest version for your OS. This contains the executable file and all necessary dependencies.

Refer to the [USER GUIDE](deployment/USER_GUIDE.md) for instructions on how to use the app.

**IMPORTANT:** You will need to provide your OpenAI API key to the app. Follow the instructions in the User Guide to set it up.

## Installation for development

```bash
uvx playwright install chromium --with-deps --no-shell
uv sync
```

## Bugs to fix

### High priority

- [x] Async request to OpenAI not working in Flask
- [x] Deduplicate receipts across the whole app
- [x] FIX THE MATCH RECEIPT ROUTE: When uploading receipt directly to the expense table, only check if the info is correct. Currently this route is being shared by the bulk upload as well.
- [x] WHEN IMPORTING EXPENSE DATA FROM MY EXPENSE, SPLIT AMOUNT AND CURRENCY INTO 2 COLUMNS
- [x] filePath key for files that didn't get matched doesn't exist
- [x] Refund not giving minus value
- [x] additional description for existing expense didn't get fill
- [x] Ask the user to zoom out so that all expenses are visible

### Low priority

- [x] When receipts are dragged inside the bulk upload area, they are grey out
