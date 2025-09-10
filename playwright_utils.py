from logging import getLogger

from playwright.sync_api import Page

from azure_ai_tools import find_text_in_image, get_polygon_center, get_scaled_coordinate

logger = getLogger(__name__)


def click_text_in_page(page: Page, text_to_click: str) -> tuple[int, int] | None:
    screenshot = page.screenshot()
    ocr_results = find_text_in_image(screenshot, text_to_click)

    if ocr_results:
        for result in ocr_results:
            click_point = get_polygon_center(result.bounding_polygon)
            click_x, click_y = get_scaled_coordinate(click_point["x"], click_point["y"], page)
            page.mouse.click(click_x, click_y, button="left")

            logger.info(f"✅ Clicked on '{text_to_click}' at coordinates ({click_x}, {click_y})")
            return click_x, click_y
    else:
        logger.warning(f"❌ Could not find '{text_to_click}' text in OCR results")
