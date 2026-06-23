#!/usr/bin/env python3
"""Tests for HEIC/HEIF -> JPG conversion performed when receipts are uploaded."""

import io
from pathlib import Path

import pillow_heif
import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from front_end.routes import receipt_routes
from invoice_extractor import convert_heic_to_jpg

pillow_heif.register_heif_opener()


def _make_heic(directory: Path, name: str = "receipt.heic") -> Path:
    """Create a small valid HEIC image and return its path."""
    path = directory / name
    Image.new("RGB", (48, 32), (180, 40, 40)).save(path, format="HEIF")
    return path


def test_convert_heic_to_jpg_creates_sibling_and_keeps_original(tmp_path):
    """Conversion writes a sibling .jpg (valid RGB JPEG) and keeps the source by default."""
    heic_path = _make_heic(tmp_path)

    jpg_path = convert_heic_to_jpg(str(heic_path))

    assert Path(jpg_path) == heic_path.with_suffix(".jpg")
    assert Path(jpg_path).exists()
    with Image.open(jpg_path) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"

    # Original is left in place unless explicitly removed.
    assert heic_path.exists()


def test_convert_heic_to_jpg_remove_original(tmp_path):
    """With remove_original the source HEIC is deleted after conversion."""
    heic_path = _make_heic(tmp_path)

    jpg_path = convert_heic_to_jpg(str(heic_path), remove_original=True)

    assert Path(jpg_path).exists()
    assert not heic_path.exists()


def test_normalize_uploaded_receipt_converts_heic(tmp_path):
    """_normalize_uploaded_receipt converts HEIC/HEIF on disk and removes the original."""
    for name in ("receipt.heic", "receipt.HEIF"):
        heic_path = _make_heic(tmp_path, name=name)

        result = receipt_routes._normalize_uploaded_receipt(str(heic_path))

        assert result.lower().endswith(".jpg")
        assert Path(result).exists()
        assert not heic_path.exists()
        with Image.open(result) as img:
            assert img.format == "JPEG"


def test_normalize_uploaded_receipt_passes_through_supported_files(tmp_path):
    """Non-HEIC uploads are returned unchanged."""
    for name in ("receipt.pdf", "receipt.jpg", "receipt.png"):
        original = str(tmp_path / name)
        assert receipt_routes._normalize_uploaded_receipt(original) == original


@pytest.mark.asyncio
async def test_upload_route_stores_heic_as_jpg(app):
    """POSTing a HEIC receipt stores a JPG on disk and reports it in file_info."""
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (12, 200, 90)).save(buffer, format="HEIF")
    buffer.seek(0)

    client = app.test_client()
    response = await client.post(
        "/api/receipts/upload",
        files={"file": FileStorage(stream=buffer, filename="myreceipt.heic")},
    )

    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True

    info = data["file_info"]
    assert info["original_filename"] == "myreceipt.heic"
    assert info["saved_filename"].lower().endswith(".jpg")
    assert info["file_type"] == ".jpg"

    stored = Path(info["file_path"])
    assert stored.exists()
    with Image.open(stored) as img:
        assert img.format == "JPEG"
    # The original HEIC must not linger on disk next to the JPG.
    assert not stored.with_suffix(".heic").exists()

    stored.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_preview_endpoint_serves_converted_heic_as_jpeg(app):
    """The /preview endpoint serves the converted JPG (regression: send_file must be awaited)."""
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (12, 200, 90)).save(buffer, format="HEIF")
    buffer.seek(0)

    client = app.test_client()
    upload = await client.post(
        "/api/receipts/upload",
        files={"file": FileStorage(stream=buffer, filename="My Receipt.heic")},
    )
    info = (await upload.get_json())["file_info"]
    saved_filename = info["saved_filename"]

    preview = await client.get(f"/api/receipts/preview/{saved_filename}")

    assert preview.status_code == 200
    assert preview.headers.get("Content-Type") == "image/jpeg"
    body = await preview.get_data()
    assert body[:3] == b"\xff\xd8\xff"  # JPEG magic bytes

    Path(info["file_path"]).unlink(missing_ok=True)

