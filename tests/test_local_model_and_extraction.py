"""
Tests for local model manager and local invoice extraction pipeline.

These tests exercise real code paths wherever possible.
Only the LLM model inference boundary is mocked (since the 400MB model
file won't be present in CI). OCR, parsing, prompt building, and
filesystem operations all run for real.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import EXPENSE_CATEGORIES
from invoice_extractor import (
    _build_extraction_prompt,
    _extract_with_local,
    _is_azure_configured,
    _ocr_image,
    _parse_local_llm_response,
    extract_invoice_details,
)
from local_model_manager import (
    MODEL_FILENAME,
    _get_model_path,
    delete_model,
    generate,
    get_model_dir,
    get_model_status,
    is_model_downloaded,
    load_model,
)


def _make_receipt_image(text_lines: list[str], width: int = 400, line_height: int = 30) -> Image.Image:
    """Create a test image with clearly drawn text lines for OCR.

    Uses a large font size and high-contrast black-on-white to ensure
    RapidOCR can reliably read the text.
    """
    height = line_height * (len(text_lines) + 2)
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    # Use a large default font for OCR readability
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except (OSError, IOError):
        font = ImageFont.load_default(size=24)
    y = line_height
    for line in text_lines:
        draw.text((20, y), line, fill="black", font=font)
        y += line_height
    return img


# ===== local_model_manager tests =====


class TestLocalModelManager:
    def test_get_model_dir_creates_directory(self, tmp_path):
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(tmp_path / "models")):
            result = get_model_dir()
            assert result.exists()
            assert result.is_dir()

    def test_get_model_path(self):
        path = _get_model_path()
        assert path.name == MODEL_FILENAME

    def test_is_model_downloaded_false(self, tmp_path):
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(tmp_path / "models")):
            assert is_model_downloaded() is False

    def test_is_model_downloaded_true(self, tmp_path):
        model_dir = tmp_path / "models"
        model_dir.mkdir()
        (model_dir / MODEL_FILENAME).write_text("fake model data")
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(model_dir)):
            assert is_model_downloaded() is True

    def test_get_model_status_not_downloaded(self, tmp_path):
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(tmp_path / "models")):
            status = get_model_status()
            assert status["downloaded"] is False
            assert status["model_name"] == MODEL_FILENAME
            assert status["size_mb"] == 0

    def test_get_model_status_downloaded(self, tmp_path):
        model_dir = tmp_path / "models"
        model_dir.mkdir()
        fake_model = model_dir / MODEL_FILENAME
        # Write ~1MB of data
        fake_model.write_bytes(b"x" * (1024 * 1024))
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(model_dir)):
            status = get_model_status()
            assert status["downloaded"] is True
            assert status["size_mb"] == 1

    def test_delete_model(self, tmp_path):
        model_dir = tmp_path / "models"
        model_dir.mkdir()
        fake_model = model_dir / MODEL_FILENAME
        fake_model.write_text("fake model data")
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(model_dir)):
            delete_model()
            assert not fake_model.exists()

    def test_delete_model_clears_cached_instance(self, tmp_path):
        import local_model_manager

        model_dir = tmp_path / "models"
        model_dir.mkdir()
        (model_dir / MODEL_FILENAME).write_text("fake")
        local_model_manager._llm_instance = "fake_instance"
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(model_dir)):
            delete_model()
            assert local_model_manager._llm_instance is None

    def test_load_model_raises_when_not_downloaded(self, tmp_path):
        with patch("local_model_manager.LOCAL_MODEL_DIR", str(tmp_path / "models")):
            with pytest.raises(FileNotFoundError, match="Model not found"):
                load_model()

    def test_generate_calls_model_with_correct_messages(self):
        """Verify generate() constructs the right chat completion call.

        We mock load_model because the 400MB model file isn't present,
        but we let the real generate() function run and verify it passes
        the expected system/user messages and parameters.
        """
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = {
            "choices": [{"message": {"content": '{"Amount": 42.0}'}}]
        }
        with patch("local_model_manager.load_model", return_value=mock_llm):
            result = generate("test prompt")
            assert result == '{"Amount": 42.0}'
            mock_llm.create_chat_completion.assert_called_once()

            # Verify the actual message structure
            call_kwargs = mock_llm.create_chat_completion.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][0]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert "JSON" in messages[0]["content"]
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "test prompt"
            # Verify temperature and max_tokens defaults
            assert call_kwargs.kwargs.get("max_tokens", call_kwargs[1].get("max_tokens")) == 1024
            assert call_kwargs.kwargs.get("temperature", call_kwargs[1].get("temperature")) == 0.1


# ===== invoice_extractor tests =====


class TestProviderSelection:
    def test_is_azure_configured_true(self):
        with (
            patch("invoice_extractor.AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com"),
            patch("invoice_extractor.INVOICE_DETAILS_EXTRACTOR_MODEL_NAME", "gpt-4o"),
        ):
            assert _is_azure_configured() is True

    def test_is_azure_configured_false_empty(self):
        with (
            patch("invoice_extractor.AZURE_OPENAI_ENDPOINT", ""),
            patch("invoice_extractor.INVOICE_DETAILS_EXTRACTOR_MODEL_NAME", ""),
        ):
            assert _is_azure_configured() is False

    def test_is_azure_configured_false_partial(self):
        with (
            patch("invoice_extractor.AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com"),
            patch("invoice_extractor.INVOICE_DETAILS_EXTRACTOR_MODEL_NAME", ""),
        ):
            assert _is_azure_configured() is False


class TestBuildExtractionPrompt:
    def test_prompt_contains_schema_fields(self):
        prompt = _build_extraction_prompt("Some OCR text here")
        assert "Amount" in prompt
        assert "Currency" in prompt
        assert "Date" in prompt
        assert "Merchant" in prompt
        assert "Some OCR text here" in prompt

    def test_prompt_contains_json_schema(self):
        prompt = _build_extraction_prompt("text")
        # Verify it includes the actual JSON schema structure
        assert '"properties"' in prompt or '"Amount"' in prompt

    def test_prompt_includes_expense_categories(self):
        prompt = _build_extraction_prompt("text")
        # At least one expense category should appear in the schema
        assert any(cat in prompt for cat in EXPENSE_CATEGORIES[:3])


class TestParseLocalLLMResponse:
    def test_parse_clean_json(self):
        raw = json.dumps(
            {
                "Amount": 42.50,
                "Currency": "USD",
                "Date": "2024-01-15",
                "Expense category": "Meals | Employee Travel",
                "Merchant": "Starbucks",
                "Additional information": "Coffee",
                "is_refund": False,
            }
        )
        result = _parse_local_llm_response(raw)
        assert result["Amount"] == 42.50
        assert result["Merchant"] == "Starbucks"

    def test_parse_json_with_code_fences(self):
        raw = '```json\n{"Amount": 10.0, "Currency": "GBP"}\n```'
        result = _parse_local_llm_response(raw)
        assert result["Amount"] == 10.0
        assert result["Currency"] == "GBP"

    def test_parse_fixes_invalid_category(self):
        raw = json.dumps(
            {
                "Amount": 5.0,
                "Expense category": "totally_invalid_category",
            }
        )
        result = _parse_local_llm_response(raw)
        # Should fall back to the first valid category
        assert result["Expense category"] == EXPENSE_CATEGORIES[0]

    def test_parse_fixes_category_case_mismatch(self):
        cat = EXPENSE_CATEGORIES[0]
        raw = json.dumps(
            {
                "Amount": 5.0,
                "Expense category": cat.upper(),
            }
        )
        result = _parse_local_llm_response(raw)
        assert result["Expense category"] == cat

    def test_parse_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_local_llm_response("not json at all")


# ===== OCR tests =====


class TestOcrImage:
    def test_ocr_image_extracts_text(self):
        """Create a PIL image with known text, call _ocr_image() directly,
        and verify some of the text is found in the output."""
        img = _make_receipt_image([
            "STARBUCKS",
            "1234 Main Street",
            "Total: $4.50",
            "Date: 2024-01-15",
        ])
        ocr_text = _ocr_image(img)
        # OCR should pick up at least some of our text
        text_upper = ocr_text.upper()
        assert "STARBUCKS" in text_upper or "STAR" in text_upper, (
            f"Expected 'STARBUCKS' in OCR output, got: {ocr_text!r}"
        )
        assert "4.50" in ocr_text or "4.5" in ocr_text, (
            f"Expected '$4.50' in OCR output, got: {ocr_text!r}"
        )


# ===== End-to-end extraction tests =====


class TestExtractInvoiceDetails:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_no_file(self):
        result = await extract_invoice_details(None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_missing_file(self):
        result = await extract_invoice_details("/nonexistent/file.pdf")
        assert result == {}

    @pytest.mark.asyncio
    async def test_local_path_used_when_azure_not_configured(self, tmp_path):
        """When Azure is not configured, the local pipeline should run.

        This test creates a real image with text, lets real OCR run on it,
        mocks only the LLM boundary (local_model_manager.generate) to return
        valid JSON, and lets the real _parse_local_llm_response run.
        """
        # Create a test image with receipt-like text
        img = _make_receipt_image([
            "STARBUCKS COFFEE",
            "1234 Main Street",
            "Latte          $4.50",
            "Date: 2024-01-15",
            "Total: $4.50",
        ])
        img_path = tmp_path / "test_receipt.png"
        img.save(str(img_path))

        # This is what the LLM would return after seeing the OCR text
        fake_llm_response = json.dumps({
            "Amount": 4.50,
            "Currency": "USD",
            "Date": "2024-01-15",
            "Expense category": "Meals | Employee Travel",
            "Merchant": "Starbucks",
            "Additional information": "Latte",
            "is_refund": False,
        })

        with (
            patch("invoice_extractor._is_azure_configured", return_value=False),
            patch("local_model_manager.generate", return_value=fake_llm_response),
        ):
            result = await extract_invoice_details(str(img_path))

        assert result["Amount"] == 4.50
        assert result["Currency"] == "USD"
        assert result["Merchant"] == "Starbucks"
        assert result["Date"] == "2024-01-15"
        assert result["Expense category"] == "Meals | Employee Travel"

    @pytest.mark.asyncio
    async def test_azure_path_used_when_configured(self, tmp_path):
        """When Azure IS configured, the Azure extraction path should be used.

        We mock _extract_with_azure since we can't call Azure in tests,
        but we verify the routing logic correctly selects the Azure path.
        """
        img = Image.new("RGB", (100, 50), color="white")
        img_path = tmp_path / "test_receipt.png"
        img.save(str(img_path))

        mock_azure_result = {
            "Amount": 50.0,
            "Currency": "GBP",
            "Date": "2024-07-01",
            "Expense category": EXPENSE_CATEGORIES[1],
            "Merchant": "Azure Store",
            "Additional information": "Azure purchase",
        }

        with (
            patch("invoice_extractor._is_azure_configured", return_value=True),
            patch(
                "invoice_extractor._extract_with_azure",
                return_value=mock_azure_result,
            ) as mock_azure,
        ):
            result = await extract_invoice_details(str(img_path))
            mock_azure.assert_called_once()
            assert result["Amount"] == 50.0
            assert result["Currency"] == "GBP"


class TestExtractWithLocalEndToEnd:
    @pytest.mark.asyncio
    async def test_extract_with_local_end_to_end(self, tmp_path):
        """Full end-to-end test of the local extraction pipeline.

        Creates a receipt image with known text, mocks only the LLM
        generate() boundary, and verifies _extract_with_local() produces
        a result dict with all expected keys and correct values.
        """
        # Create a receipt-like image
        img = _make_receipt_image([
            "STARBUCKS COFFEE",
            "123 Pike Place",
            "Seattle WA 98101",
            "",
            "Grande Latte        $4.50",
            "Tax                 $0.40",
            "Total               $4.90",
            "",
            "Date: 2024-01-15",
            "Thank you!",
        ])
        img_path = tmp_path / "receipt.png"
        img.save(str(img_path))

        fake_llm_response = json.dumps({
            "Amount": 4.90,
            "Currency": "USD",
            "Date": "2024-01-15",
            "Expense category": "Meals | Employee Travel",
            "Merchant": "Starbucks Coffee",
            "Additional information": "Grande Latte",
            "is_refund": False,
        })

        with patch("local_model_manager.generate", return_value=fake_llm_response):
            result = await _extract_with_local(str(img_path))

        # Verify all expected keys are present
        expected_keys = {"Amount", "Currency", "Date", "Expense category", "Merchant", "Additional information"}
        assert expected_keys.issubset(result.keys()), f"Missing keys: {expected_keys - result.keys()}"

        # Verify values
        assert result["Amount"] == 4.90
        assert result["Currency"] == "USD"
        assert result["Date"] == "2024-01-15"
        assert result["Expense category"] == "Meals | Employee Travel"
        assert result["Merchant"] == "Starbucks Coffee"
        assert result["Additional information"] == "Grande Latte"

    @pytest.mark.asyncio
    async def test_extract_with_local_handles_refund(self, tmp_path):
        """Verify that the refund flag correctly negates the amount."""
        img = _make_receipt_image([
            "REFUND",
            "Starbucks Coffee",
            "Amount: $4.90",
        ])
        img_path = tmp_path / "refund_receipt.png"
        img.save(str(img_path))

        fake_llm_response = json.dumps({
            "Amount": 4.90,
            "Currency": "USD",
            "Date": "2024-01-15",
            "Expense category": "Meals | Employee Travel",
            "Merchant": "Starbucks",
            "Additional information": "Refund",
            "is_refund": True,
        })

        with patch("local_model_manager.generate", return_value=fake_llm_response):
            result = await _extract_with_local(str(img_path))

        assert result["Amount"] == -4.90

    @pytest.mark.asyncio
    async def test_extract_with_local_raises_on_blank_image(self, tmp_path):
        """A blank white image should produce no OCR text, causing an error."""
        img = Image.new("RGB", (100, 50), color="white")
        img_path = tmp_path / "blank.png"
        img.save(str(img_path))

        with pytest.raises(Exception, match="OCR extracted no text"):
            await _extract_with_local(str(img_path))
