from time import sleep

from playwright.sync_api import sync_playwright

from main import setup_browser_session

NUM_ENTRIES = 30

browser_process = setup_browser_session()

sleep(2)
with sync_playwright() as playwright:
    browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
    # Replace with your actual expense app URL
    EXPENSE_APP_URL = "myexpense.operations.dynamics.com"

    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    # Wait a moment for the page to be fully created
    page.wait_for_load_state("domcontentloaded")
    page.goto(f"https://{EXPENSE_APP_URL}")

    print(1)

    data = [
        {
            "Subcategory": "Hotel Deposit",
            "Start date": f"10/{i + 1}/2025",
            "Daily rate": "500",
            "Quantity": f"{i + 1}",
        }
        for i in range(NUM_ENTRIES)
    ]

    # Open the itemization dialog
    actions_button = page.locator("button[name='CardBottomMenuFormMenuButtonControl']")
    actions_button.wait_for(state="visible")
    actions_button.click()

    itemize_button = page.locator("button[name='ItemizeExpenseButton']")
    itemize_button.wait_for(state="visible")
    itemize_button.click()

    popup_pane = page.locator(
        "div.rootLayout.rootLayout-dialog.fill-width.fill-height.layout-container.layout-vertical"
    )
    popup_pane.wait_for(state="visible")

    # Delete the pre-populated first row as it's annoying to handle
    popup_pane.locator("button[name='DeleteButtonItemizationGroup']").click()
    page.wait_for_load_state("domcontentloaded")

    new_item_button = popup_pane.locator("button[name='NewButtonItemizationGroup']")

    # Populate itemization entries for each expense line in the hotel invoice
    for record in data:
        new_item_button.click()
        page.wait_for_load_state("domcontentloaded")

        # Get the second entry (Skipping the header)
        current_row = (
            popup_pane.locator("div.fixedDataTableLayout_rowsContainer")
            .locator("div.fixedDataTableRowLayout_body")
            .nth(1)
        )

        for field in ["Subcategory", "Start date", "Daily rate", "Quantity"]:
            current_cell = current_row.locator(f'input[aria-label="{field}"]')
            current_cell.click()
            current_cell.fill(record[field], timeout=1000)

    print(1)

    # Close the dialog
    popup_pane.locator("button[name='CloseButton']").click()
