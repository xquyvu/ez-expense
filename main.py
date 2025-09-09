import io
import subprocess
import time

import pytesseract
from dotenv import load_dotenv
from PIL import Image
from playwright.sync_api import sync_playwright

load_dotenv()

PORT = 9222

# Check if there is an existing Microsoft Edge process
result = subprocess.run(
    ["pgrep", "-f", "Microsoft Edge"], capture_output=True, text=True
)
if result.stdout.strip():
    print("Found existing Microsoft Edge process(es).")
    user_input = (
        input(
            "Edge needs to be closed for this to work. Hit <Enter> to continue or <Ctrl+C> to cancel"
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
    # Attach to the running Edge instance via the Chrome DevTools Protocol.
    browser = p.chromium.connect_over_cdp(CDP_URL)

    # Grab the default context (your existing Edge profile session).
    context = browser.contexts[0] if browser.contexts else browser.new_context()

    # Pick an existing tab if there is one; otherwise open a new one.
    page = context.new_page()

    # Example: interact with the page (navigate, click, etc.)
    page.goto(
        "https://myexpense.operations.dynamics.com/", wait_until="domcontentloaded"
    )
    time.sleep(2)

    # Use computer vision to find a button that says "Expense Management" and click on it
    screenshot = page.screenshot()

    # Use OCR to find "Expense Management" text and its coordinates
    # Convert screenshot bytes to PIL Image
    image = Image.open(io.BytesIO(screenshot))

    # Look for "Expense Management" text and get its coordinates
    expense_mgmt_found = False
    for i, text in enumerate(ocr_data["text"]):
        if "Expense" in text and "Management" in " ".join(ocr_data["text"][i : i + 2]):
            # Found "Expense Management", get coordinates
            x = ocr_data["left"][i]
            y = ocr_data["top"][i]
            width = (
                ocr_data["width"][i] + ocr_data["width"][i + 1]
                if i + 1 < len(ocr_data["width"])
                else ocr_data["width"][i]
            )
            height = ocr_data["height"][i]

            # Click at the center of the found text
            click_x = x + width // 2
            click_y = y + height // 2

            page.mouse.click(click_x, click_y)
            print(
                f"✅ Clicked on 'Expense Management' at coordinates ({click_x}, {click_y})"
            )
            expense_mgmt_found = True
            break
    if not expense_mgmt_found:
        print("❌ Could not find 'Expense Management' text in OCR results")
    image = Image.open(io.BytesIO(screenshot))

    # Extract text from the image
    extracted_text = pytesseract.image_to_string(image)

    # Try to find and click the "Expense Management" button
    try:
        expense_mgmt_button = page.get_by_text("Expense Management").first
        expense_mgmt_button.click()
        print("✅ Clicked on 'Expense Management' button")
    except:
        print("❌ Could not find or click 'Expense Management' button")

    # Find the "New expense" button using text locator

    # # Save screenshot to workspace
    # screenshot_path = "screenshot.png"
    # with open(screenshot_path, "wb") as f:
    #     f.write(screenshot)
    # print(f"Screenshot saved to {screenshot_path}")

    # You'll need to install pytesseract and Pillow: pip install pytesseract Pillow

    # Check if "Expense Management" exists in the extracted text
    if "Expense Management" in extracted_text:
        print("✅ Found 'Expense Management' text on the page")
    else:
        print("❌ 'Expense Management' text not found on the page")
        print(
            f"Extracted text: {extracted_text[:200]}..."
        )  # Show first 200 chars for debugging
