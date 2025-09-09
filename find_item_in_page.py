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


client = ImageAnalysisClient(
    endpoint=os.environ["AZURE_AI_SERVICES_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["AZURE_AI_SERVICES_KEY"]),
)

with open("screenshot.png", "rb") as image_file:
    image_data = image_file.read()

    text_to_find = "Unattached expenses"


def find_text_in_image(image_data, text_to_find):
    analysed_image_data = client.analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.READ],
    )

    for line in analysed_image_data.read.blocks[0].lines:
        results = []

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
