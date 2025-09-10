import pytest

from azure_ai_tools import find_text_in_image, get_polygon_center


def test_find_text_in_image():
    with open("./tests/test_data/test_screenshot.png", "rb") as image_file:
        image_data = image_file.read()

        text_to_find = "Unattached expenses"

        results = find_text_in_image(image_data, text_to_find)

        assert len(results) > 0


def test_get_polygon_center_basic():
    polygon = [
        {"x": 226, "y": 255},
        {"x": 421, "y": 257},
        {"x": 421, "y": 278},
        {"x": 225, "y": 277},
    ]
    result = get_polygon_center(polygon)
    assert result == {"x": 323, "y": 266}


def test_get_polygon_center_single_point():
    polygon = [{"x": 100, "y": 200}]
    result = get_polygon_center(polygon)
    assert result == {"x": 100, "y": 200}


def test_get_polygon_center_empty():
    with pytest.raises(ValueError):
        get_polygon_center([])
