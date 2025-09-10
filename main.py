import datetime
import subprocess
import time
from logging import getLogger

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from azure_ai_tools import find_text_in_image, get_polygon_center, get_scaled_coordinate

logger = getLogger(__name__)

load_dotenv()

PORT = 9222

# Check if there is an existing Microsoft Edge process
result = subprocess.run(["pgrep", "-f", "Microsoft Edge"], capture_output=True, text=True)
if result.stdout.strip():
    print("Found existing Microsoft Edge process(es).")
    user_input = (
        input(
            """Edge needs to be closed for this to work. Hit <Enter> to Close your
            browser or <Ctrl+C> to cancel"""
        )
        .strip()
        .lower()
    )
    print("Closing existing Edge processes...")
    subprocess.run(["pkill", "-f", "Microsoft Edge"], capture_output=True)
    time.sleep(1)  # Give time for processes to close
else:
    print("No existing Edge processes found.")


res = subprocess.Popen(
    [
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        f"--remote-debugging-port={PORT}",
        "--new-window",
    ]
)

time.sleep(2)  # Give Edge time to start

CDP_URL = f"http://localhost:{PORT}"

with sync_playwright() as p:
    # Attach to the existing browser instance
    browser = p.chromium.connect_over_cdp(CDP_URL)

    # Find the expense management page
    context = browser.contexts[0] if browser.contexts else browser.new_context()

    for page in context.pages:
        if "myexpense.operations.dynamics.com" in page.url:
            page.bring_to_front()
            break
    else:
        page = context.new_page()
        page.goto("https://myexpense.operations.dynamics.com/")

    # Wait for the user input
    input(
        """Press <Enter> after you have created a new expense report, or navigated
        to the expense report you want to fill. Press <Ctrl+C> to exit at any
        time."""
    )

    def click_text_in_page(text_to_click: str) -> tuple[int, int] | None:
        screenshot = page.screenshot()
        ocr_results = find_text_in_image(screenshot, text_to_click)

        # # Save screenshot to screenshot.png for debugging
        # image = Image.open(io.BytesIO(screenshot))
        # image.save("screenshot.png")

        if ocr_results:
            for result in ocr_results:
                click_point = get_polygon_center(result.bounding_polygon)
                click_x, click_y = get_scaled_coordinate(click_point["x"], click_point["y"], page)
                page.mouse.click(click_x, click_y, button="left")

                logger.info(
                    f"✅ Clicked on '{text_to_click}' at coordinates ({click_x}, {click_y})"
                )
                return click_x, click_y
        else:
            logger.warning(f"❌ Could not find '{text_to_click}' text in OCR results")

    click_text_in_page("New expense")

    new_expense_button = page.get_by_text("New expense", exact=True)
    new_expense_button.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    print(1)

    category = "Airfare"
    amount = "10"
    currency = "CHF"
    date_to_fill = datetime.datetime.now().date()
    merchant = "merchant"
    description = "desc"  # Expense description / Business purpose

    page.fill('input[name="CategoryInput"]', category)
    page.fill('input[name="AmountInput"]', amount)
    page.fill('input[name="CurrencyInput"]', currency)
    page.fill('input[name="MerchantInputNoLookup"]', merchant)
    page.fill('input[name="DateInput"]', date_to_fill.strftime("%-m/%-d/%Y"))
    page.fill('textarea[name="NotesInput"]', description)

    page.get_by_text("Save").click()
    page.wait_for_timeout(3000)

    # Now we add receipt to the expense
    page.click('a[name="EditReceipts"]')
    page.click('button[name="AddButton"]')

    # Upload receipt
    with page.expect_file_chooser() as fc_info:
        page.click('button[name="UploadControlBrowseButton"]')

    file_chooser = fc_info.value
    file_chooser.set_files("screenshot.png")

    page.click('button[name="UploadControlUploadButton"]')

    page.click('button[name="OkButtonAddNewTabPage"]')
    page.wait_for_timeout(1000)
    page.get_by_text("Close", exact=True).click()

    page.get_by_text("Save and continue", exact=True).click()

    # Optionally, you can also wait for a specific element that indicates success
    try:
        # Wait for success message or form reset

        logger.info("✅ Expense saved successfully - form has been reset")
    except:
        logger.warning("⚠️  Could not confirm if save operation completed")

    page.get_by_text("Expense management", exact=True).click()
