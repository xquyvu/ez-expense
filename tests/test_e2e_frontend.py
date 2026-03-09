"""
Frontend E2E tests for EZ Expense.

All tests run in mock import mode (IMPORT_EXPENSE_MOCK=True) so no MyExpense
browser session is needed.  The live server is started automatically via the
``live_server`` fixture defined in conftest.py.

Run:
    uv run pytest tests/test_e2e_frontend.py -v
    uv run pytest tests/test_e2e_frontend.py -v --headed   # visible browser
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def import_mock_expenses(page):
    """Click through the import flow and wait for the expense table to appear."""
    # Check the navigation checkbox to reveal the import button
    page.check("#navigation-checkbox")
    page.wait_for_selector("#import-from-website-btn", state="visible")

    # Click import
    page.click("#import-from-website-btn")

    # Wait for the loading overlay to disappear and the table to appear
    page.wait_for_selector("#loading-overlay", state="hidden", timeout=15_000)
    page.wait_for_selector("#expenses-table tbody tr", state="visible", timeout=10_000)


def upload_receipts_via_input(page, files):
    """Upload files by setting them on the hidden file input directly.

    The ``selectBulkReceipts()`` JS function programmatically clicks a hidden
    ``<input type="file">``; Playwright's ``expect_file_chooser`` doesn't
    reliably intercept that.  Instead, set files directly on the input element
    and dispatch a ``change`` event.
    """
    page.set_input_files("#bulk-receipt-input", files)
    page.wait_for_selector("#loading-overlay", state="hidden", timeout=15_000)


# ===================================================================
# A. App loading & navigation
# ===================================================================


class TestAppLoading:
    def test_app_loads(self, page):
        """Page title is correct and header is visible."""
        assert "Hyper Velocity Expense" in page.title()
        header = page.locator("header h1")
        assert header.is_visible()
        assert "Hyper Velocity Expense" in header.text_content()

    def test_health_endpoint(self, page, live_server):
        """The /health endpoint returns 200 with JSON."""
        response = page.request.get(f"{live_server}/health")
        assert response.status == 200
        body = response.json()
        assert body["status"] == "healthy"


# ===================================================================
# B. Import expenses (mock mode)
# ===================================================================


class TestImportExpenses:
    def test_mock_import_shows_expenses_table(self, page):
        """Clicking import shows the expense table with rows."""
        import_mock_expenses(page)
        rows = page.locator("#expenses-table tbody tr")
        assert rows.count() > 0

    def test_imported_data_has_expected_columns(self, page):
        """Table headers include core expense columns."""
        import_mock_expenses(page)
        header_text = page.locator("#table-header").text_content()
        for col in ("Amount", "Date", "Currency"):
            assert col in header_text, f"Expected column '{col}' in table header"

    def test_bulk_receipts_section_visible_after_import(self, page):
        """Bulk Receipt Upload Area is visible after importing."""
        import_mock_expenses(page)
        section = page.locator("#bulk-receipts-section")
        assert section.is_visible()


# ===================================================================
# C. AI Extraction Options panel
# ===================================================================


class TestAIOptionsPanel:
    def test_ai_options_panel_visible(self, page):
        """Panel shows AI Extraction Options text with two radio options."""
        import_mock_expenses(page)
        # The AI options are rendered inside the bulk receipt actions area
        panel = page.locator("#bulk-receipt-actions")
        assert panel.is_visible()
        assert "AI Extraction Options" in panel.text_content()
        # Two radio inputs for ai-provider
        radios = page.locator("input[name='ai-provider']")
        assert radios.count() == 2

    def test_azure_radio_state_matches_config(self, page, live_server):
        """Azure radio disabled/enabled state matches model status API."""
        import_mock_expenses(page)
        # Ask the API what the actual status is
        resp = page.request.get(f"{live_server}/api/model/status")
        body = resp.json()
        azure_configured = body.get("azure_configured", False)

        azure_radio = page.locator("#azure-ai-checkbox")
        if azure_configured:
            assert azure_radio.is_enabled(), "Azure is configured but radio is disabled"
        else:
            assert azure_radio.is_disabled(), "Azure is NOT configured but radio is enabled"
            panel = page.locator("#bulk-receipt-actions")
            assert "Not available" in panel.text_content()

    def test_azure_unavailable_state(self, page, live_server):
        """When Azure is NOT configured, radio is disabled with 'Not available' text."""
        import invoice_extractor
        from front_end.routes import model_routes

        orig_ie = invoice_extractor._is_azure_configured
        orig_mr = model_routes._is_azure_configured

        def fake():
            return False

        invoice_extractor._is_azure_configured = fake
        model_routes._is_azure_configured = fake
        try:
            # Reload so the JS re-fetches /api/model/status with patched value
            page.goto(live_server)
            page.wait_for_load_state("networkidle")
            import_mock_expenses(page)
            azure_radio = page.locator("#azure-ai-checkbox")
            assert azure_radio.is_disabled()
            panel = page.locator("#bulk-receipt-actions")
            assert "Not available" in panel.text_content()
        finally:
            invoice_extractor._is_azure_configured = orig_ie
            model_routes._is_azure_configured = orig_mr

    def test_why_popover(self, page, live_server):
        """Clicking 'Why?' shows the popover when Azure is not configured."""
        import invoice_extractor
        from front_end.routes import model_routes

        orig_ie = invoice_extractor._is_azure_configured
        orig_mr = model_routes._is_azure_configured

        def fake():
            return False

        invoice_extractor._is_azure_configured = fake
        model_routes._is_azure_configured = fake
        try:
            # Reload so the JS re-fetches /api/model/status with patched value
            page.goto(live_server)
            page.wait_for_load_state("networkidle")
            import_mock_expenses(page)

            # Click the "Why?" span — it's inside a label wrapping a disabled
            # radio, so Playwright thinks it's not enabled. Use force=True.
            why_trigger = page.locator("text=Why?")
            why_trigger.click(force=True)
            popover = page.locator("#azure-why-popover")
            assert popover.is_visible()
            assert ".env" in popover.text_content()

            # Click outside to close
            page.locator("header h1").click()
            page.wait_for_timeout(300)
            assert not popover.is_visible()
        finally:
            invoice_extractor._is_azure_configured = orig_ie
            model_routes._is_azure_configured = orig_mr

    def test_model_status_api(self, page, live_server):
        """/api/model/status returns JSON with expected fields."""
        resp = page.request.get(f"{live_server}/api/model/status")
        assert resp.status == 200
        body = resp.json()
        assert "azure_configured" in body
        assert "downloaded" in body


# ===================================================================
# D. Receipt upload
# ===================================================================


class TestReceiptUpload:
    def test_upload_single_receipt(self, page, test_jpeg):
        """Upload a single JPEG → preview appears in bulk area."""
        import_mock_expenses(page)
        upload_receipts_via_input(page, test_jpeg)

        # Wait for the receipt preview to appear in the bulk receipt area
        page.wait_for_selector(
            "#bulk-receipt-cell .receipt-preview, #bulk-receipt-cell .receipt-item",
            timeout=10_000,
        )

    def test_upload_multiple_receipts(self, page, test_jpegs):
        """Upload 3 files → all 3 appear as previews."""
        import_mock_expenses(page)
        upload_receipts_via_input(page, test_jpegs)

        # Each receipt should render a preview element
        page.wait_for_timeout(2000)
        previews = page.locator(
            "#bulk-receipt-cell .receipt-preview, #bulk-receipt-cell .receipt-item"
        )
        assert previews.count() >= 3

    def test_upload_invalid_file_rejected(self, page, tmp_path):
        """Uploading a .txt file shows a warning toast and isn't added."""
        import_mock_expenses(page)

        # Create a .txt file
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a receipt")

        # The hidden file input has accept="image/*,.pdf" which may silently
        # ignore .txt when set via set_input_files.  Use the JS handler directly
        # to exercise the validation branch.
        upload_receipts_via_input(page, str(txt_file))

        # Should show a toast with warning
        page.wait_for_selector(".toast-container .toast, #toast-container div", timeout=5_000)
        toast_text = page.locator("#toast-container").text_content()
        assert (
            "invalid" in toast_text.lower()
            or "no valid" in toast_text.lower()
            or "skipped" in toast_text.lower()
        )


# ===================================================================
# E. Receipt matching
# ===================================================================


class TestReceiptMatching:
    def test_match_button_disabled_without_receipts(self, page):
        """'Match receipts with expenses' button is disabled with no receipts."""
        import_mock_expenses(page)
        match_btn = page.locator("text=Match receipts with expenses")
        assert match_btn.is_disabled()

    def test_match_button_enabled_with_receipts(self, page, test_jpeg):
        """Button becomes enabled after uploading a receipt."""
        import_mock_expenses(page)
        upload_receipts_via_input(page, test_jpeg)
        page.wait_for_timeout(1000)

        match_btn = page.locator("text=Match receipts with expenses")
        assert match_btn.is_enabled()


# ===================================================================
# F. Table editing
# ===================================================================


class TestTableEditing:
    def test_add_row(self, page):
        """Clicking 'Add Row' adds a new row to the table."""
        import_mock_expenses(page)
        initial_count = page.locator("#expenses-table tbody tr").count()
        page.click("#add-row-btn")
        page.wait_for_timeout(500)
        new_count = page.locator("#expenses-table tbody tr").count()
        assert new_count == initial_count + 1

    def test_edit_expense_cell(self, page):
        """Click on an editable textarea in the table → type new value → value persists."""
        import_mock_expenses(page)
        # Table cells are <textarea class="table-input">, skip non-editable ones
        cell = page.locator(
            "#expenses-table tbody tr:first-child textarea.table-input:not(.non-editable)"
        ).first
        cell.click()
        cell.fill("TestEditValue123")
        # Click elsewhere to commit
        page.locator("header h1").click()
        page.wait_for_timeout(200)
        assert cell.input_value() == "TestEditValue123"


# ===================================================================
# G. Validation
# ===================================================================


class TestValidation:
    def test_validate_button_exists(self, page):
        """Validate Data button is present after import."""
        import_mock_expenses(page)
        btn = page.locator("#validate-data-btn")
        assert btn.is_visible()

    def test_validate_shows_guidance(self, page):
        """Clicking Validate Data shows the validation guidance area."""
        import_mock_expenses(page)
        page.click("#validate-data-btn")
        page.wait_for_timeout(500)
        guidance = page.locator("#validation-guidance")
        assert guidance.is_visible()


# ===================================================================
# H. Create expenses from receipts
# ===================================================================


class TestCreateExpensesFromReceipts:
    def test_create_expenses_button_disabled_without_receipts(self, page):
        """'Create expenses from receipts' button disabled when no receipts."""
        import_mock_expenses(page)
        create_btn = page.locator("text=Create expenses from receipts")
        assert create_btn.is_disabled()


# ===================================================================
# I. Export stats
# ===================================================================


class TestExportStats:
    def test_export_stats_visible_after_import(self, page):
        """Summary stats (Total Expenses, Matched Receipts, Completion Rate) are visible."""
        import_mock_expenses(page)
        assert page.locator("#total-expenses").is_visible()
        assert page.locator("#matched-receipts").is_visible()
        assert page.locator("#completion-rate").is_visible()

    def test_total_expenses_count(self, page):
        """Total expenses stat updates after import."""
        import_mock_expenses(page)
        total_text = page.locator("#total-expenses").text_content()
        total = int(total_text.strip())
        assert total > 0

    def test_fill_button_exists(self, page):
        """Fill Expense Report button is present."""
        import_mock_expenses(page)
        btn = page.locator("#fill-expense-report-btn")
        assert btn.is_visible()
