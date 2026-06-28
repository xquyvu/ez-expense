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
    # Each itemized hotel ends with a real "Save and continue".
    save_mock = AsyncMock()
    monkeypatch.setattr(expense_routes, "_save_and_continue", save_mock)

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
    save_mock.assert_awaited_once()  # ends with Save and continue


@pytest.mark.asyncio
async def test_itemize_fill_retries_open_when_itemize_menu_missing(app, monkeypatch):
    """If the wrong card opens (no "Itemize"), the route re-selects the line and retries.

    Regression test for the hotel-on-first-row bug: a sticky message bar overlapped the top
    grid row, the selecting click missed, and ``click_itemize_button`` raised because the
    open card's Actions menu had no "Itemize" item. The route should dismiss the stray
    flyout, re-locate + re-open the line (centered), and retry until the dialog opens.
    """
    import itemization
    from front_end.routes import expense_routes

    # The retry path awaits page.wait_for_timeout(...) and the guarded flyout dismissal, so
    # those must be awaitable on the mocked page / module.
    page = MagicMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: page)
    monkeypatch.setattr(expense_routes, "_fill_in_progress", False)

    # The route dismisses a stray flyout via the guarded helper (which only presses Escape
    # when a flyout is actually open — a blind Escape would close the report form).
    dismiss_mock = AsyncMock()
    monkeypatch.setattr(itemization, "_dismiss_flyout_if_open", dismiss_mock)

    locate_mock = AsyncMock(return_value=MagicMock())
    # _open_expense_line reports selection unconfirmed first, then confirmed on the retry.
    open_mock = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(expense_routes, "_locate_expense_line", locate_mock)
    monkeypatch.setattr(expense_routes, "_open_expense_line", open_mock)

    # First Itemize attempt fails (wrong card → no "Itemize"), second attempt succeeds.
    click_mock = AsyncMock(
        side_effect=[RuntimeError("Itemize menu item not visible after opening Actions"), None]
    )
    fill_mock = AsyncMock()
    monkeypatch.setattr(itemization, "click_itemize_button", click_mock)
    monkeypatch.setattr(itemization, "itemize_hotel_invoice", fill_mock)
    # The successful retry ends with a real "Save and continue".
    save_mock = AsyncMock()
    monkeypatch.setattr(expense_routes, "_save_and_continue", save_mock)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/fill",
        json={
            "items": [
                {
                    "id": 1,
                    "created_id": "EXP-HOTEL",
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
    # The line was re-located and re-opened once after the first failure.
    assert locate_mock.await_count == 2
    assert open_mock.await_count == 2
    # Every open used a centered scroll so a top-row hotel isn't hidden under the banner.
    assert all(call.kwargs.get("block") == "center" for call in open_mock.await_args_list)
    # Itemize was attempted twice (fail, then success) and the dialog filled exactly once.
    assert click_mock.await_count == 2
    fill_mock.assert_awaited_once()
    # The stray Actions flyout was dismissed (via the guarded helper) before retrying.
    dismiss_mock.assert_awaited()
    # And the saved-and-continued line persisted the itemization.
    save_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_itemize_fill_gives_up_after_max_open_attempts(app, monkeypatch):
    """If "Itemize" never appears, the route stops retrying and reports the line as failed."""
    import itemization
    from front_end.routes import expense_routes

    page = MagicMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    monkeypatch.setattr(expense_routes, "get_expense_page", lambda: page)
    monkeypatch.setattr(expense_routes, "_fill_in_progress", False)
    monkeypatch.setattr(expense_routes, "_locate_expense_line", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(expense_routes, "_open_expense_line", AsyncMock(return_value=False))

    # Itemize never becomes available.
    click_mock = AsyncMock(side_effect=RuntimeError("Itemize menu item not visible"))
    fill_mock = AsyncMock()
    monkeypatch.setattr(itemization, "click_itemize_button", click_mock)
    monkeypatch.setattr(itemization, "itemize_hotel_invoice", fill_mock)

    client = app.test_client()
    response = await client.post(
        "/api/expenses/itemize/fill",
        json={
            "items": [
                {
                    "id": 1,
                    "created_id": "EXP-HOTEL",
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
    # The whole request reports failure because the only line failed.
    assert data["success"] is False
    assert data["results"][0]["success"] is False
    # It retried the configured number of times, then gave up without filling the dialog.
    assert click_mock.await_count == 4
    fill_mock.assert_not_awaited()
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


# ── Itemization-row clearing (select-all + Delete) ──────────────────────────


def _make_clear_locator() -> MagicMock:
    """A Playwright-locator mock whose nth()/first/locator() chain stays awaitable."""
    loc = MagicMock()
    loc.click = AsyncMock()
    loc.wait_for = AsyncMock()
    loc.nth = MagicMock(return_value=loc)
    loc.first = loc
    loc.locator = MagicMock(return_value=loc)
    return loc


def test_select_all_modifier_is_platform_specific(monkeypatch):
    """Cmd (Meta) on macOS, Ctrl (Control) on Windows/Linux."""
    import itemization

    monkeypatch.setattr(itemization.sys, "platform", "darwin")
    assert itemization._select_all_modifier() == "Meta"
    monkeypatch.setattr(itemization.sys, "platform", "win32")
    assert itemization._select_all_modifier() == "Control"
    monkeypatch.setattr(itemization.sys, "platform", "linux")
    assert itemization._select_all_modifier() == "Control"


@pytest.mark.asyncio
async def test_clear_itemization_uses_select_all_then_single_delete(monkeypatch):
    """All rows are cleared with one select-all shortcut + one Delete (not row-by-row)."""
    import itemization

    delete_loc = _make_clear_locator()
    rows_loc = _make_clear_locator()

    def locator_side_effect(selector):
        if "DeleteButtonItemizationGroup" in selector:
            return delete_loc
        return rows_loc

    popup_pane = MagicMock()
    popup_pane.locator = MagicMock(side_effect=locator_side_effect)

    yes_button = MagicMock()
    yes_button.wait_for = AsyncMock()
    yes_button.click = AsyncMock()
    page = MagicMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.get_by_role = MagicMock(return_value=yes_button)

    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", AsyncMock())
    monkeypatch.setattr(itemization, "_overlay_visible", AsyncMock(return_value=False))
    # initial=3, pass-0 current=3, pass-1 current=0 (break), final=0.
    monkeypatch.setattr(
        itemization, "_itemization_data_row_count", AsyncMock(side_effect=[3, 3, 0, 0])
    )
    monkeypatch.setattr(
        itemization, "_wait_for_itemization_row_count_below", AsyncMock(return_value=0)
    )

    deleted = await itemization._clear_existing_itemization_rows(page, popup_pane)

    assert deleted == 3
    # Exactly one select-all shortcut press (not N per-row clicks), with the OS modifier.
    expected_key = f"{itemization._select_all_modifier()}+Shift+M"
    page.keyboard.press.assert_awaited_once_with(expected_key)
    # The grid was focused and the group Delete was clicked exactly once.
    rows_loc.click.assert_awaited()
    delete_loc.click.assert_awaited_once()
    # The confirmation dialog was accepted.
    yes_button.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_itemization_raises_when_count_does_not_drop(monkeypatch):
    """If the row count never drops after delete, we raise instead of closing with stale rows."""
    import itemization

    popup_pane = MagicMock()
    popup_pane.locator = MagicMock(return_value=_make_clear_locator())

    yes_button = MagicMock()
    yes_button.wait_for = AsyncMock()
    yes_button.click = AsyncMock()
    page = MagicMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.get_by_role = MagicMock(return_value=yes_button)

    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", AsyncMock())
    monkeypatch.setattr(itemization, "_overlay_visible", AsyncMock(return_value=False))
    # initial=3, current=3, then (in except) still=3.
    monkeypatch.setattr(
        itemization, "_itemization_data_row_count", AsyncMock(side_effect=[3, 3, 3])
    )
    monkeypatch.setattr(
        itemization,
        "_wait_for_itemization_row_count_below",
        AsyncMock(side_effect=itemization.PlaywrightTimeoutError("did not drop")),
    )

    with pytest.raises(RuntimeError, match="row count stuck at 3"):
        await itemization._clear_existing_itemization_rows(page, popup_pane)


@pytest.mark.asyncio
async def test_clear_itemization_noop_when_grid_empty(monkeypatch):
    """An already-empty grid returns 0 without pressing any shortcut or clicking Delete."""
    import itemization

    delete_loc = _make_clear_locator()
    popup_pane = MagicMock()
    popup_pane.locator = MagicMock(return_value=delete_loc)
    page = MagicMock()
    page.keyboard.press = AsyncMock()

    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", AsyncMock())
    monkeypatch.setattr(
        itemization, "_itemization_data_row_count", AsyncMock(return_value=0)
    )

    deleted = await itemization._clear_existing_itemization_rows(page, popup_pane)

    assert deleted == 0
    page.keyboard.press.assert_not_awaited()
    delete_loc.click.assert_not_awaited()


# ── click_itemize_button: verify-and-retry the swallowed Actions click ───────


@pytest.mark.asyncio
async def test_find_visible_itemize_returns_first_visible():
    """The first candidate whose locator becomes visible is returned; later ones aren't probed."""
    import itemization

    primary = _make_clear_locator()  # wait_for resolves immediately
    fallback = _make_clear_locator()
    label, found = await itemization._find_visible_itemize(
        [("primary", primary), ("fallback", fallback)],
        primary_timeout=10,
        fallback_timeout=5,
    )

    assert label == "primary"
    assert found is primary  # _make_clear_locator sets .first = itself
    primary.wait_for.assert_awaited_once()
    fallback.wait_for.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_visible_itemize_returns_none_when_all_time_out():
    """When no candidate is visible within budget we return (None, None) — fast, not 45s."""
    import itemization

    def timing_out():
        loc = _make_clear_locator()
        loc.wait_for = AsyncMock(
            side_effect=itemization.PlaywrightTimeoutError("not visible")
        )
        return loc

    label, found = await itemization._find_visible_itemize(
        [("a", timing_out()), ("b", timing_out()), ("c", timing_out())],
        primary_timeout=5,
        fallback_timeout=1,
    )

    assert label is None
    assert found is None


@pytest.mark.asyncio
async def test_dismiss_flyout_if_open_escapes_only_when_open():
    """Escape is pressed only when a flyout is open — never on the bare form (which would
    close it and navigate back to the workspace)."""
    import itemization

    page_open = MagicMock()
    page_open.evaluate = AsyncMock(return_value=True)
    page_open.keyboard.press = AsyncMock()
    await itemization._dismiss_flyout_if_open(page_open)
    page_open.keyboard.press.assert_awaited_once_with("Escape")

    page_closed = MagicMock()
    page_closed.evaluate = AsyncMock(return_value=False)
    page_closed.keyboard.press = AsyncMock()
    await itemization._dismiss_flyout_if_open(page_closed)
    page_closed.keyboard.press.assert_not_awaited()


@pytest.mark.asyncio
async def test_click_itemize_button_reopens_when_flyout_swallowed(monkeypatch):
    """A swallowed Actions click (flyout never opens) triggers a re-open instead of the old
    45s hang; once Itemize is visible we click it and wait for the dialog."""
    import itemization

    itemize_loc = MagicMock()
    itemize_loc.click = AsyncMock()
    dialog_loc = MagicMock()
    dialog_loc.wait_for = AsyncMock()

    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.locator = MagicMock(return_value=dialog_loc)
    page.get_by_role = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", AsyncMock())
    dismiss = AsyncMock()
    monkeypatch.setattr(itemization, "_dismiss_flyout_if_open", dismiss)
    open_flyout = AsyncMock(return_value='button[name="CardBottomMenuFormMenuButtonControl"]')
    monkeypatch.setattr(itemization, "_open_actions_flyout", open_flyout)
    # First open is swallowed (no Itemize); second open succeeds.
    find = AsyncMock(
        side_effect=[(None, None), ("button[name='ItemizeExpenseButton']", itemize_loc)]
    )
    monkeypatch.setattr(itemization, "_find_visible_itemize", find)

    await itemization.click_itemize_button(page)

    assert open_flyout.await_count == 2  # re-opened after the swallow
    assert find.await_count == 2
    dismiss.assert_awaited()  # guarded dismissal between attempts, not a blind Escape
    itemize_loc.click.assert_awaited()  # phase 3 clicked Itemize
    dialog_loc.wait_for.assert_awaited()  # phase 4 waited for the dialog


@pytest.mark.asyncio
async def test_click_itemize_button_raises_after_exhausting_open_attempts(monkeypatch):
    """If the flyout never opens with Itemize, we dump the menu state and raise — without
    burning the old 3 × 15s budget per attempt."""
    import itemization

    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value=[])
    page.locator = MagicMock(return_value=MagicMock())
    page.get_by_role = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", AsyncMock())
    monkeypatch.setattr(itemization, "_dismiss_flyout_if_open", AsyncMock())
    open_flyout = AsyncMock(return_value='button[name="CardBottomMenuFormMenuButtonControl"]')
    monkeypatch.setattr(itemization, "_open_actions_flyout", open_flyout)
    find = AsyncMock(return_value=(None, None))
    monkeypatch.setattr(itemization, "_find_visible_itemize", find)

    with pytest.raises(RuntimeError, match="Itemize menu item not visible"):
        await itemization.click_itemize_button(page)

    assert open_flyout.await_count == 5  # one attempt per escalation strategy
    assert find.await_count == 5
    page.evaluate.assert_awaited_once()  # captured the menu state for diagnosis


@pytest.mark.asyncio
async def test_wait_for_commit_settled_waits_overlay_appear_then_hidden(monkeypatch):
    """After the dialog closes, we let the commit overlay appear (best-effort) then wait for
    it to clear with the generous budget — so the next Save-and-continue click isn't
    swallowed by the ShellBlockingDiv."""
    import itemization

    page = MagicMock()
    # Overlay never visibly appears (instant/already-cleared) → the appear-wait times out and
    # must be swallowed, then we still delegate to the hidden-wait.
    page.wait_for_selector = AsyncMock(
        side_effect=itemization.PlaywrightTimeoutError("no overlay")
    )
    unblocked = AsyncMock()
    monkeypatch.setattr(itemization, "_wait_for_shell_unblocked", unblocked)

    await itemization._wait_for_commit_settled(page, timeout=55_000)

    # The appear-wait used state="visible" with a short budget, and its timeout was swallowed.
    page.wait_for_selector.assert_awaited_once()
    assert page.wait_for_selector.await_args.kwargs.get("state") == "visible"
    # The hidden-wait was delegated with the generous timeout.
    unblocked.assert_awaited_once_with(page, timeout=55_000)
