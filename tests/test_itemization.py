#!/usr/bin/env python3
"""Tests for hotel itemization: subcategory config, LLM-response parsing, and route validation.

These are all non-browser unit/route tests — Playwright interactions are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(str(Path(__file__).parent.parent))

import config
import invoice_extractor as ie


# ── Subcategory config loader ───────────────────────────────────────────────


def test_hotel_subcategories_loaded_without_comments():
    """HOTEL_SUBCATEGORIES is a clean list (no comment/blank lines leak through)."""
    subs = config.HOTEL_SUBCATEGORIES
    assert isinstance(subs, list)
    assert "Daily Room Rate" in subs  # known entry from the repo file
    assert all(s and not s.startswith("#") for s in subs)


# ── Pure parsing/normalization helpers ──────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2025-10-01", "10/1/2025"),
        ("10/1/2025", "10/1/2025"),
        ("01/05/2025", "1/5/2025"),
    ],
)
def test_normalize_date_mdy(raw, expected):
    assert ie._normalize_date_mdy(raw) == expected


def test_normalize_date_mdy_passthrough_on_unparseable():
    assert ie._normalize_date_mdy("not a date") == "not a date"
    assert ie._normalize_date_mdy("") == ""


def test_coerce_subcategory_snaps_to_valid_value():
    assert ie._coerce_subcategory("daily room rate") == "Daily Room Rate"  # case-insensitive
    assert ie._coerce_subcategory("tax") == "Hotel Tax"  # substring match
    assert ie._coerce_subcategory("Spa") == "Spa"  # unknown -> unchanged


def test_to_number_handles_symbols_and_commas():
    assert ie._to_number("$1,234.50") == 1234.5
    assert ie._to_number(200) == 200.0
    assert ie._to_number("") == 0.0
    assert ie._to_number("abc") == 0.0


def test_parse_itemization_response_object_and_fence():
    payload = (
        "```json\n"
        '{"Lines": [{"Subcategory": "Daily Room Rate", "Start date": "2025-10-01", '
        '"Daily rate": "$200", "Quantity": 3}]}\n'
        "```"
    )
    assert ie._parse_itemization_response(payload) == [
        {
            "Subcategory": "Daily Room Rate",
            "Start date": "10/1/2025",
            "Daily rate": 200.0,
            "Quantity": 3.0,
        }
    ]


def test_parse_itemization_response_bare_list_and_alias_keys():
    payload = (
        '[{"subcategory": "Laundry", "start_date": "2025-10-02", '
        '"daily_rate": 15, "quantity": 1}]'
    )
    lines = ie._parse_itemization_response(payload)
    assert len(lines) == 1
    assert lines[0] == {
        "Subcategory": "Laundry",
        "Start date": "10/2/2025",
        "Daily rate": 15.0,
        "Quantity": 1.0,
    }


def test_parse_itemization_response_tolerates_surrounding_prose():
    # Models sometimes wrap the JSON in commentary (esp. with extra instructions); the parser
    # must still recover the embedded object. Regression for the expected_total extraction path.
    payload = (
        "Sure, here is the reconciled itemization:\n"
        '{"Lines": [{"Subcategory": "Daily Room Rate", "Start date": "9/15/2024", '
        '"Daily rate": 264, "Quantity": 5}]}\n'
        "These lines sum to 1320. Let me know if you need anything else!"
    )
    lines = ie._parse_itemization_response(payload)
    assert lines == [
        {
            "Subcategory": "Daily Room Rate",
            "Start date": "9/15/2024",
            "Daily rate": 264.0,
            "Quantity": 5.0,
        }
    ]


def test_parse_itemization_response_empty_on_garbage():
    assert ie._parse_itemization_response("no json here at all") == []
    assert ie._parse_itemization_response("") == []


# ── Balance validation helpers ──────────────────────────────────────────────


def test_itemized_total_sums_rate_times_quantity():
    lines = [
        {"Daily rate": 264.0, "Quantity": 5.0},  # 1320
        {"Daily rate": 39.0, "Quantity": 5.0},  # 195
        {"Daily rate": 34.0, "Quantity": 5.0},  # 170
    ]
    assert ie.itemized_total(lines) == 1685.0


def test_itemized_total_handles_alias_keys_and_strings():
    lines = [{"daily_rate": "$100.50", "quantity": 2}, {"Daily rate": -50.25, "Quantity": 1}]
    assert ie.itemized_total(lines) == 150.75


def test_is_balanced_true_within_tolerance():
    lines = [{"Daily rate": 100.0, "Quantity": 3.0}]  # 300
    assert ie.is_balanced(lines, 300.0) is True
    assert ie.is_balanced(lines, "300.00") is True
    assert ie.is_balanced(lines, 300.005) is True  # within 0.01 tolerance


def test_is_balanced_false_when_mismatch_or_missing_amount():
    lines = [{"Daily rate": 100.0, "Quantity": 3.0}]  # 300
    assert ie.is_balanced(lines, 350.0) is False
    assert ie.is_balanced(lines, None) is False
    assert ie.is_balanced(lines, "") is False


def test_is_balanced_with_negative_adjustment_line():
    # Mirrors a real folio: nightly + tax + a negative adjustment that reconciles to the total.
    lines = [
        {"Daily rate": 1095.0, "Quantity": 6.0},  # 6570
        {"Daily rate": 155.0, "Quantity": 6.0},  # 930
        {"Daily rate": 350.0, "Quantity": 1.0},  # 350
        {"Daily rate": 290.0, "Quantity": 1.0},  # 290
        {"Daily rate": -427.02, "Quantity": 1.0},  # -427.02
    ]
    assert ie.itemized_total(lines) == 7712.98
    assert ie.is_balanced(lines, 7712.98) is True


# ── Route validation / wiring ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hotel_subcategories_endpoint(app):
    client = app.test_client()
    response = await client.get("/api/expenses/hotel-subcategories")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    assert "Daily Room Rate" in data["subcategories"]


@pytest.mark.asyncio
async def test_itemize_extract_rejects_when_no_hotel_expenses(app):
    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/extract",
        json={
            "expenses": [
                {
                    "id": 1,
                    "Expense category": "Meals | Employee Travel",
                    "Receipts": [{"filePath": "/tmp/x.jpg"}],
                }
            ]
        },
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert data["success"] is False
    assert "hotel" in data["message"].lower()


@pytest.mark.asyncio
async def test_itemize_extract_runs_extraction_for_hotel(app, monkeypatch):
    """Only Hotel expenses with a receipt are extracted; results echo identity + lines + balance."""

    async def fake_extract(path, provider=None, expected_total=None):
        assert path == "/tmp/hotel.pdf"
        assert expected_total == 600  # the expense Amount is passed through for reconciliation
        return [
            {
                "Subcategory": "Daily Room Rate",
                "Start date": "10/1/2025",
                "Daily rate": 200.0,
                "Quantity": 3.0,
            }
        ]

    # The route imports this lazily from invoice_extractor, so patch it there.
    monkeypatch.setattr(ie, "extract_hotel_itemization", fake_extract)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/extract",
        json={
            "expenses": [
                {
                    "id": 7,
                    "Created ID": "EXP-7",
                    "Merchant": "Grand Hotel",
                    "Expense category": "Hotel",
                    "Amount": 600,
                    "Receipts": [{"filePath": "/tmp/hotel.pdf"}],
                },
                # Non-hotel and hotel-without-receipt are ignored.
                {"id": 8, "Expense category": "Airfare", "Receipts": [{"filePath": "/tmp/a.jpg"}]},
                {"id": 9, "Expense category": "Hotel", "Receipts": []},
            ]
        },
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["created_id"] == "EXP-7"
    assert result["lines"][0]["Subcategory"] == "Daily Room Rate"
    # Balance validation fields: 200 × 3 == 600, so it reconciles.
    assert result["itemized_total"] == 600.0
    assert result["difference"] == 0.0
    assert result["balanced"] is True


@pytest.mark.asyncio
async def test_itemize_extract_flags_unbalanced(app, monkeypatch):
    """When the lines don't sum to the expense amount, balanced=False with the difference."""

    async def fake_extract(path, provider=None, expected_total=None):
        return [{"Subcategory": "Daily Room Rate", "Daily rate": 100.0, "Quantity": 3.0}]  # 300

    monkeypatch.setattr(ie, "extract_hotel_itemization", fake_extract)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/extract",
        json={
            "expenses": [
                {
                    "id": 1,
                    "Created ID": "EXP-1",
                    "Expense category": "Hotel",
                    "Amount": "350.00",
                    "Receipts": [{"filePath": "/tmp/h.pdf"}],
                }
            ]
        },
    )
    data = await response.get_json()
    result = data["results"][0]
    assert result["itemized_total"] == 300.0
    assert result["amount"] == 350.0
    assert result["difference"] == -50.0
    assert result["balanced"] is False


@pytest.mark.asyncio
async def test_itemize_fill_rejects_empty_items(app):
    client = app.test_client()
    response = await client.post("/api/expenses/itemize/fill", json={"items": []})
    assert response.status_code == 400
    data = await response.get_json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_itemize_fill_no_session_returns_500(app, monkeypatch):
    from front_end.routes import expense_routes

    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: None)
    monkeypatch.setattr(expense_routes, "_fill_in_progress", False)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/fill",
        json={
            "items": [
                {
                    "created_id": "EXP-1",
                    "lines": [
                        {
                            "Subcategory": "Daily Room Rate",
                            "Start date": "10/1/2025",
                            "Daily rate": 200,
                            "Quantity": 3,
                        }
                    ],
                }
            ]
        },
    )
    assert response.status_code == 500
    data = await response.get_json()
    assert data["success"] is False
    assert "page not available" in data["message"].lower()


@pytest.mark.asyncio
async def test_itemize_fill_drives_playwright_for_hotel_line(app, monkeypatch):
    """A valid item locates+opens the line, opens the dialog, and fills the rows."""
    import itemization
    from front_end.routes import expense_routes

    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: MagicMock())
    monkeypatch.setattr(expense_routes, "_fill_in_progress", False)
    monkeypatch.setattr(expense_routes, "_locate_expense_line", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(expense_routes, "_open_expense_line", AsyncMock())

    click_mock = AsyncMock()
    fill_mock = AsyncMock()
    # The route imports these lazily from `itemization`, so patch them on that module.
    monkeypatch.setattr(itemization, "click_itemize_button", click_mock)
    monkeypatch.setattr(itemization, "itemize_hotel_invoice", fill_mock)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/fill",
        json={
            "items": [
                {
                    "id": 7,
                    "created_id": "EXP-7",
                    "lines": [
                        {
                            "Subcategory": "Daily Room Rate",
                            "Start date": "10/1/2025",
                            "Daily rate": 200,
                            "Quantity": 3,
                        }
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    assert data["results"][0]["success"] is True
    click_mock.assert_awaited_once()
    fill_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_itemize_fill_skips_item_without_created_id(app, monkeypatch):
    """Items lacking a Created ID can't be targeted in MyExpense and are reported as failures."""
    from front_end.routes import expense_routes

    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: MagicMock())
    monkeypatch.setattr(expense_routes, "_fill_in_progress", False)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/fill",
        json={
            "items": [
                {
                    "id": 1,
                    "created_id": None,
                    "lines": [
                        {
                            "Subcategory": "Daily Room Rate",
                            "Start date": "10/1/2025",
                            "Daily rate": 200,
                            "Quantity": 3,
                        }
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is False
    assert data["results"][0]["success"] is False
    assert "created id" in data["results"][0]["message"].lower()
