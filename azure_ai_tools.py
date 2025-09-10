import os
from logging import getLogger

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from pydantic import BaseModel

logger = getLogger(__name__)


load_dotenv()


class TextSearchResult(BaseModel):
    text: str
    bounding_polygon: list[dict[str, int]]


IMG_ANALYSIS_CLIENT = ImageAnalysisClient(
    endpoint=os.environ["AZURE_AI_SERVICES_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["AZURE_AI_SERVICES_KEY"]),
)


def find_text_in_image(image_data: bytes, text_to_find: str) -> list[TextSearchResult]:
    analysed_image_data = IMG_ANALYSIS_CLIENT.analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.READ],
    )

    results = []

    for line in analysed_image_data.read.blocks[0].lines:
        logger.debug(f"Found line: {line.text}")
        if text_to_find in line.text:
            logger.debug(f"Found `{text_to_find}` as part of {line.text} in image")
            logger.debug(f"Bounding polygon: {line.bounding_polygon}")

            results.append(
                TextSearchResult(
                    text=line.text,
                    bounding_polygon=line.bounding_polygon,
                )
            )

    return results


def get_polygon_center(
    bounding_polygon: list[dict[str, int]],
) -> dict[str, int]:
    """
    Given a bounding polygon, return the center coordinate.

    Bounding polygon is a list of dict with 'x' and 'y' keys.

    Example: [{'x': 226, 'y': 255}, {'x': 421, 'y': 257}, {'x': 421, 'y': 278}, {'x': 225, 'y': 277}]
    """
    if not bounding_polygon or len(bounding_polygon) == 0:
        raise ValueError("Bounding polygon is empty")

    min_x = min(point["x"] for point in bounding_polygon)
    max_x = max(point["x"] for point in bounding_polygon)
    min_y = min(point["y"] for point in bounding_polygon)
    max_y = max(point["y"] for point in bounding_polygon)

    center_x = (min_x + max_x) // 2
    center_y = (min_y + max_y) // 2

    return {"x": center_x, "y": center_y}


# Adjust coordinates by device pixel ratio


def get_scaled_coordinate(x, y, page):
    device_pixel_ratio = page.evaluate("window.devicePixelRatio")
    scaled_x = int(x / device_pixel_ratio)
    scaled_y = int(y / device_pixel_ratio)
    return scaled_x, scaled_y
