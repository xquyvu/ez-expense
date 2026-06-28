/**
 * ItemizationManager — owns the hotel-itemization review UI.
 *
 * Lifecycle:
 *   1. `extract()` — POST /api/expenses/itemize/extract for all hotel expenses with receipts
 *      and render the editable review tables.
 *   2. User edits the tables (validations applied live, like the main expense table).
 *   3. `confirm()` — validate all rows. If valid, lock the tables (read-only) and flip the
 *      action button to "Edit". Confirmed itemization is then filled into MyExpense as part
 *      of the main "Fill Expense Report" flow.
 *   4. `edit()` — unlock the tables for further edits.
 *   5. `clear()` — hide the review section and reset state.
 *
 * The class is instantiated by `EZExpenseApp` and accessed via `app.itemization`. Inline
 * `onclick="…"` attributes call into `app.itemization.METHOD(...)` exactly like the rest of
 * the app's event wiring.
 */
class ItemizationManager {
    constructor(app) {
        this.app = app;
        this.subcategories = null;
        this.results = [];
        this.confirmed = false;
    }

    // ── Public API ──────────────────────────────────────────────────────────

    /**
     * Are we in the locked/confirmed state? Used by the main fill flow.
     */
    isConfirmed() {
        return this.confirmed;
    }

    /**
     * Is the review section currently visible (i.e. has the user extracted itemization)?
     */
    isVisible() {
        const section = document.getElementById('itemization-review-inline');
        return !!section && section.style.display !== 'none';
    }

    /**
     * Are there any non-empty rows ready to fill? (Used to skip the fill step when empty.)
     */
    hasItems() {
        return this.collectItemsForFill().length > 0;
    }

    /**
     * Hotel expenses (category "Hotel") that have at least one matched receipt.
     */
    getHotelExpensesWithReceipts() {
        const expenses = this.app.expenses || [];
        return expenses.filter(exp => {
            const category = (exp['Expense category'] || '').toString().trim().toLowerCase();
            if (category !== 'hotel') return false;
            const receipts = this.app.receipts.get(exp.id) || exp.Receipts || exp.receipts || [];
            return receipts.length > 0;
        });
    }

    /**
     * Load (and cache) the valid hotel itemization subcategories from the backend.
     */
    async loadSubcategories() {
        if (this.subcategories) return this.subcategories;
        try {
            const response = await fetch('/api/expenses/hotel-subcategories');
            const data = await response.json();
            this.subcategories = (data && data.success && Array.isArray(data.subcategories))
                ? data.subcategories : [];
        } catch (error) {
            console.warn('Could not load hotel subcategories:', error);
            this.subcategories = [];
        }
        return this.subcategories;
    }

    /**
     * Extract itemization for all hotel expenses with receipts, then show the inline review.
     */
    async extract() {
        const hotelExpenses = this.getHotelExpensesWithReceipts();
        if (hotelExpenses.length === 0) {
            this.app.showToast('No Hotel expenses with a matched receipt to itemize. Match receipts first.', 'warning');
            return;
        }

        try {
            this.app.showLoading(`Extracting itemization for ${hotelExpenses.length} hotel expense(s)...`);
            await this.loadSubcategories();

            const payload = {
                expenses: hotelExpenses.map(exp => ({
                    ...exp,
                    Receipts: this.app.receipts.get(exp.id) || exp.Receipts || exp.receipts || []
                })),
                provider: this.app.aiSelectedProvider || undefined
            };

            const response = await fetch('/api/expenses/itemize/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            this.app.hideLoading();

            if (!response.ok || !result.success) {
                this.app.showToast(`Itemization extraction failed: ${result.message || response.status}`, 'error');
                return;
            }

            this.results = result.results || [];
            this.confirmed = false;
            this._renderReview(this.results);
            this._show();
            // Validate everything once on render so any extracted-but-invalid values surface in red.
            this.validateAllRows();
        } catch (error) {
            this.app.hideLoading();
            console.error('Error extracting hotel itemization:', error);
            this.app.showToast(`Error extracting hotel itemization: ${error.message}`, 'error');
        }
    }

    /**
     * Validate all rows; if everything is OK, lock the table and flip the button to "Edit".
     */
    confirm() {
        const allValid = this.validateAllRows();
        const unbalanced = this._getUnbalancedExpenses();

        if (!allValid) {
            this.app.showToast(
                'Please fix the highlighted itemization errors before confirming.',
                'warning'
            );
            return;
        }
        if (unbalanced.length > 0) {
            this.app.showToast(
                `Itemized totals do not match expense amounts:\n\n${unbalanced.join('\n')}\n\n` +
                `Adjust the lines so each block reconciles before confirming.`,
                'warning'
            );
            return;
        }

        // No rows at all? Nothing to confirm — but still tolerate an empty confirm so the
        // user can proceed to "Fill Expense Report" without itemization.
        if (!this.hasItems()) {
            this.app.showToast('No itemization rows to confirm — nothing will be filled.', 'info');
        }

        this._setLocked(true);
        this.confirmed = true;
        this._updateActionButton();
        this.app.showToast('Itemization confirmed. It will be filled when you click "Fill Expense Report".', 'success');
    }

    /**
     * Unlock the tables for further edits.
     */
    edit() {
        this._setLocked(false);
        this.confirmed = false;
        this._updateActionButton();
    }

    /**
     * Hide the review section and reset state.
     */
    clear() {
        this._hide();
        this.results = [];
        this.confirmed = false;
    }

    /**
     * Fill the confirmed itemization into MyExpense. Returns {success, message, results?}.
     * Caller (fillExpenseReport) is responsible for showing the loading overlay.
     */
    async fillIntoMyExpense() {
        const items = this.collectItemsForFill();
        if (items.length === 0) {
            return { success: true, message: 'No itemization rows to fill.', results: [] };
        }

        try {
            const response = await fetch('/api/expenses/itemize/fill', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items, timestamp: new Date().toISOString() })
            });
            const result = await response.json();
            return {
                success: response.ok && !!result.success,
                message: result.message || (response.ok ? 'Itemization filled.' : `HTTP ${response.status}`),
                results: result.results || []
            };
        } catch (error) {
            console.error('Error filling itemization:', error);
            return { success: false, message: `Error filling itemization: ${error.message}`, results: [] };
        }
    }

    // ── Row management (called inline from rendered HTML) ───────────────────

    addRow(expIdx) {
        if (this.confirmed) return;
        const block = document.querySelector(`.itemization-expense[data-expense-index="${expIdx}"]`);
        if (!block) return;
        const tbody = block.querySelector('tbody.itemization-rows');
        const lineIdx = tbody.querySelectorAll('tr.itemization-row').length;
        tbody.insertAdjacentHTML('beforeend', this._renderRow({}, expIdx, lineIdx));
        this.recalcTotals(expIdx);
    }

    removeRow(btn) {
        if (this.confirmed) return;
        const row = btn.closest('tr.itemization-row');
        if (!row) return;
        const expIdx = row.dataset.expenseIndex;
        row.remove();
        if (expIdx !== undefined) this.recalcTotals(parseInt(expIdx));
    }

    recalcTotals(expIdx) {
        const block = document.querySelector(`.itemization-expense[data-expense-index="${expIdx}"]`);
        if (!block) return;
        const footer = block.querySelector('.itemization-totals');
        if (!footer) return;

        const { itemized, amount, difference, balanced } = this._computeBalance(block);
        const fmt = (n) => (n === null || n === undefined) ? '—' : n.toFixed(2);

        footer.classList.remove('is-balanced', 'is-unbalanced', 'is-unknown');

        if (amount === null) {
            footer.classList.add('is-unknown');
            footer.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <span>Itemized total: <strong>${fmt(itemized)}</strong> — expense amount unknown, cannot validate.</span>`;
            return;
        }
        if (balanced) {
            footer.classList.add('is-balanced');
            footer.innerHTML = `<i class="fas fa-check-circle"></i> <span>Itemized <strong>${fmt(itemized)}</strong> matches expense amount <strong>${fmt(amount)}</strong>.</span>`;
        } else {
            footer.classList.add('is-unbalanced');
            footer.innerHTML = `<i class="fas fa-exclamation-circle"></i> <span>Itemized <strong>${fmt(itemized)}</strong> ≠ expense amount <strong>${fmt(amount)}</strong> (difference <strong>${fmt(difference)}</strong>). Adjust the lines so they reconcile.</span>`;
        }
    }

    // ── Validation ──────────────────────────────────────────────────────────

    /**
     * Validate a single field input and apply visual feedback. Mirrors the main table's
     * validateField behavior: `.validation-error` on the input, `.validation-invalid` /
     * `.validation-valid` on the cell.
     */
    validateField(input) {
        if (!input) return true;
        const field = input.dataset.field;
        const value = (input.value || '').trim();

        let isValid = true;
        switch (field) {
            case 'Subcategory':
                isValid = value !== '';
                break;
            case 'Start date':
                isValid = this._isValidMDYDate(value);
                break;
            case 'Daily rate':
            case 'Quantity':
                isValid = this._isPositiveNumber(value);
                break;
            default:
                return true;
        }

        const cell = input.closest('td');
        if (isValid) {
            input.classList.remove('validation-error');
            if (cell) {
                cell.classList.remove('validation-invalid');
                cell.classList.add('validation-valid');
            }
        } else {
            input.classList.add('validation-error');
            if (cell) {
                cell.classList.remove('validation-valid');
                cell.classList.add('validation-invalid');
            }
        }
        return isValid;
    }

    /**
     * Validate every input in every itemization row. Returns true iff all are valid.
     */
    validateAllRows() {
        const inputs = document.querySelectorAll(
            '#itemization-review-body .itemization-row [data-field]'
        );
        let allValid = true;
        inputs.forEach(input => {
            if (!this.validateField(input)) allValid = false;
        });
        return allValid;
    }

    /**
     * Build the items array sent to /api/expenses/itemize/fill from the current DOM state.
     */
    collectItemsForFill() {
        const blocks = document.querySelectorAll('#itemization-review-body .itemization-expense');
        const items = [];
        blocks.forEach(block => {
            const lines = [];
            block.querySelectorAll('tr.itemization-row').forEach(row => {
                const getVal = (field) => {
                    const el = row.querySelector(`[data-field="${field}"]`);
                    return el ? el.value.trim() : '';
                };
                const subcategory = getVal('Subcategory');
                const startDate = getVal('Start date');
                const dailyRate = getVal('Daily rate');
                const quantity = getVal('Quantity');
                if (!subcategory && !startDate && !dailyRate && !quantity) return;
                lines.push({
                    'Subcategory': subcategory,
                    'Start date': startDate,
                    'Daily rate': parseFloat(dailyRate) || 0,
                    'Quantity': parseFloat(quantity) || 0
                });
            });
            if (lines.length === 0) return;
            items.push({
                id: block.dataset.expenseId || null,
                created_id: block.dataset.createdId || null,
                amount: this.app.parseAmount(block.dataset.amount),
                lines
            });
        });
        return items;
    }

    // ── Internal helpers ────────────────────────────────────────────────────

    _show() {
        const section = document.getElementById('itemization-review-inline');
        if (!section) return;
        section.style.display = 'block';
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    _hide() {
        const section = document.getElementById('itemization-review-inline');
        if (!section) return;
        section.style.display = 'none';
        const body = document.getElementById('itemization-review-body');
        if (body) body.innerHTML = '';
        this._setLocked(false);
        this._updateActionButton();
    }

    /**
     * Switch the "Confirm" / "Edit" action button label and styling based on current state.
     */
    _updateActionButton() {
        const btn = document.getElementById('itemization-confirm-btn');
        if (!btn) return;
        if (this.confirmed) {
            btn.innerHTML = '<i class="fas fa-pen"></i> Edit';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-warning');
            btn.setAttribute('onclick', 'app.itemization.edit()');
            btn.title = 'Unlock the table to edit rows again';
        } else {
            btn.innerHTML = '<i class="fas fa-check"></i> Confirm';
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-primary');
            btn.setAttribute('onclick', 'app.itemization.confirm()');
            btn.title = 'Validate and lock the itemization data';
        }
    }

    /**
     * Toggle the locked (read-only) state on all rendered itemization tables.
     */
    _setLocked(locked) {
        const body = document.getElementById('itemization-review-body');
        if (!body) return;

        body.querySelectorAll('.itemization-expense').forEach(block => {
            block.classList.toggle('is-locked', locked);
        });
        body.querySelectorAll('.itemization-row [data-field]').forEach(input => {
            if (input.tagName === 'SELECT') {
                input.disabled = locked;
            } else {
                input.readOnly = locked;
            }
        });
    }

    _computeBalance(block) {
        let itemized = 0;
        block.querySelectorAll('tr.itemization-row').forEach(row => {
            const rate = parseFloat(row.querySelector('[data-field="Daily rate"]')?.value) || 0;
            const qty = parseFloat(row.querySelector('[data-field="Quantity"]')?.value) || 0;
            itemized += Math.round(rate * qty * 100) / 100;
        });
        itemized = Math.round(itemized * 100) / 100;
        const amount = this.app.parseAmount(block.dataset.amount);
        const difference = (amount !== null) ? Math.round((itemized - amount) * 100) / 100 : null;
        const balanced = (amount !== null) && Math.abs(difference) <= 0.01;
        return { itemized, amount, difference, balanced };
    }

    _getUnbalancedExpenses() {
        const blocks = document.querySelectorAll('#itemization-review-body .itemization-expense');
        const unbalanced = [];
        blocks.forEach(block => {
            // Empty blocks (no rows) are fine — nothing will be filled.
            const hasRows = block.querySelectorAll('tr.itemization-row').length > 0;
            if (!hasRows) return;
            const { balanced, itemized, amount } = this._computeBalance(block);
            if (!balanced) {
                const label = block.querySelector('.merchant-name')?.textContent?.trim()
                    || block.dataset.createdId || 'expense';
                unbalanced.push(`• ${label}: itemized ${itemized.toFixed(2)} vs amount ${amount === null ? '?' : amount.toFixed(2)}`);
            }
        });
        return unbalanced;
    }

    // ── Rendering ───────────────────────────────────────────────────────────

    _renderReview(results) {
        const body = document.getElementById('itemization-review-body');
        if (!body) return;

        if (!results || results.length === 0) {
            body.innerHTML = '<p style="color:#6c757d; font-style:italic;">No itemization data was extracted.</p>';
            return;
        }

        const escape = (v) => this.app.escapeHtml(v);
        const formatAmount = (val) => {
            if (val === null || val === undefined || val === '') return null;
            const n = this.app.parseAmount(val);
            return (n === null) ? escape(String(val)) : n.toFixed(2);
        };

        body.innerHTML = results.map((res, expIdx) => {
            const title = res.merchant || res.created_id || `Hotel expense ${expIdx + 1}`;
            const amountFmt = formatAmount(res.amount);
            const amountHtml = amountFmt !== null
                ? `<span class="itemization-expense-amount">Amount: ${amountFmt}</span>`
                : '';
            const errorHtml = res.error
                ? `<div class="itemization-error"><i class="fas fa-exclamation-circle"></i> Extraction error: ${escape(res.error)}</div>`
                : '';
            const rowsHtml = (res.lines || []).map((line, lineIdx) => this._renderRow(line, expIdx, lineIdx)).join('');
            const receiptHtml = this._renderReceiptPane(res);

            return `
                <div class="itemization-expense" data-expense-index="${expIdx}" data-expense-id="${res.id ?? ''}" data-created-id="${res.created_id ?? ''}" data-amount="${res.amount ?? ''}">
                    <div class="itemization-expense-header">
                        <div class="itemization-expense-title">
                            <i class="fas fa-hotel"></i>
                            <span class="merchant-name">${escape(title)}</span>
                        </div>
                        ${amountHtml}
                    </div>
                    <div class="itemization-expense-body">
                        <div class="itemization-pane-left">
                            ${errorHtml}
                            <div class="table-container itemization-table-container">
                                <table class="data-table itemization-table">
                                    <colgroup>
                                        <col class="col-subcategory">
                                        <col class="col-date">
                                        <col class="col-rate">
                                        <col class="col-qty">
                                        <col class="col-actions">
                                    </colgroup>
                                    <thead>
                                        <tr>
                                            <th>Subcategory</th>
                                            <th>Start date</th>
                                            <th>Daily rate</th>
                                            <th>Qty</th>
                                            <th aria-label="Actions"></th>
                                        </tr>
                                    </thead>
                                    <tbody class="itemization-rows">
                                        ${rowsHtml}
                                    </tbody>
                                </table>
                            </div>
                            <div class="itemization-table-actions">
                                <button class="btn btn-outline btn-sm itemization-add-row-btn" onclick="app.itemization.addRow(${expIdx})">
                                    <i class="fas fa-plus"></i> Add Row
                                </button>
                            </div>
                            <div class="itemization-totals"></div>
                        </div>
                        <div class="itemization-pane-right">
                            ${receiptHtml}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        results.forEach((_, expIdx) => this.recalcTotals(expIdx));
    }

    /**
     * Render the receipt preview (image or PDF) pane for one expense, looking up the
     * attached receipt from the app's main receipts map by expense id. Falls back to
     * the server-side receipt_path filename when no client-side receipt is registered.
     */
    _renderReceiptPane(res) {
        const escape = (v) => this.app.escapeHtml(v);
        const receipts = (this.app.receipts && res.id !== undefined && res.id !== null)
            ? (this.app.receipts.get(res.id)
                || this.app.receipts.get(String(res.id))
                || this.app.receipts.get(Number(res.id))
                || [])
            : [];

        // Pick the first usable receipt; fall back to deriving a filename from receipt_path.
        let receipt = receipts.find(r => r && (r.filename || r.preview || r.filePath));
        if (!receipt && res.receipt_path) {
            const fname = String(res.receipt_path).split(/[\\/]/).pop();
            receipt = { filename: fname, name: fname };
        }
        if (!receipt) {
            return `
                <div class="itemization-receipt-empty">
                    <i class="fas fa-receipt"></i>
                    <div>No receipt preview available</div>
                </div>
            `;
        }

        const name = receipt.name || receipt.filename || 'Receipt';
        const lowerName = name.toLowerCase();
        const isPdf = lowerName.endsWith('.pdf');
        const isHtml = lowerName.endsWith('.html') || lowerName.endsWith('.htm');
        const previewUrl = receipt.filename
            ? `/api/receipts/preview/${encodeURIComponent(receipt.filename)}`
            : '';

        // PDFs render via PDF.js into a canvas — <embed> doesn't render reliably in all
        // browsers (e.g. headless Chromium), and PDF.js keeps the styling consistent.
        if (isPdf) {
            if (!previewUrl) {
                return `<div class="itemization-receipt-empty"><i class="fas fa-file-pdf"></i><div>PDF not available</div></div>`;
            }
            const canvasId = `itemization-pdf-canvas-${res.id ?? 'x'}-${Math.random().toString(36).slice(2, 8)}`;
            // Trigger PDF.js rendering after the HTML is in the DOM.
            setTimeout(() => this._renderPdfInto(canvasId, previewUrl), 0);
            return `
                <div class="itemization-receipt-frame">
                    <div class="itemization-receipt-name" title="${escape(name)}">
                        <i class="fas fa-file-pdf" style="color:#dc3545;"></i> ${escape(name)}
                        <a href="${previewUrl}" target="_blank" class="itemization-receipt-open" title="Open in new tab">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                    </div>
                    <div class="itemization-receipt-image-wrap">
                        <canvas id="${canvasId}" class="itemization-receipt-canvas"></canvas>
                    </div>
                </div>
            `;
        }

        if (isHtml) {
            return `
                <div class="itemization-receipt-frame">
                    <div class="itemization-receipt-name" title="${escape(name)}">
                        <i class="fas fa-code" style="color:#6c757d;"></i> ${escape(name)}
                        <a href="${previewUrl}" target="_blank" class="itemization-receipt-open" title="Open in new tab">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                    </div>
                    <iframe src="${previewUrl}" class="itemization-receipt-pdf" sandbox=""></iframe>
                </div>
            `;
        }

        // Image (jpg/png/etc.) — defer to the app's resolver for the best source URL.
        const imgSrc = this.app.receiptImageSrc(receipt);
        if (!imgSrc) {
            return `<div class="itemization-receipt-empty"><i class="fas fa-image"></i><div>Cannot preview ${escape(name)}</div></div>`;
        }
        return `
            <div class="itemization-receipt-frame">
                <div class="itemization-receipt-name" title="${escape(name)}">
                    <i class="fas fa-image" style="color:#6c757d;"></i> ${escape(name)}
                    <a href="${imgSrc}" target="_blank" class="itemization-receipt-open" title="Open in new tab">
                        <i class="fas fa-external-link-alt"></i>
                    </a>
                </div>
                <div class="itemization-receipt-image-wrap">
                    <img src="${imgSrc}" alt="Receipt" class="itemization-receipt-image">
                </div>
            </div>
        `;
    }

    /**
     * Render a PDF URL into a <canvas> at the canvas' container width using PDF.js.
     */
    async _renderPdfInto(canvasId, url) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        if (typeof pdfjsLib === 'undefined') {
            canvas.replaceWith(Object.assign(document.createElement('div'), {
                className: 'itemization-receipt-empty',
                innerHTML: '<i class="fas fa-file-pdf"></i><div>PDF.js not loaded</div>'
            }));
            return;
        }
        try {
            const pdf = await pdfjsLib.getDocument(url).promise;
            const page = await pdf.getPage(1);
            const wrap = canvas.parentElement;
            const targetWidth = Math.max(200, (wrap?.clientWidth || 400) - 4);
            const baseViewport = page.getViewport({ scale: 1 });
            const scale = targetWidth / baseViewport.width;
            const viewport = page.getViewport({ scale });
            const ctx = canvas.getContext('2d');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = viewport.width + 'px';
            canvas.style.height = viewport.height + 'px';
            await page.render({ canvasContext: ctx, viewport }).promise;
        } catch (err) {
            console.warn('PDF render failed:', err);
            canvas.replaceWith(Object.assign(document.createElement('div'), {
                className: 'itemization-receipt-empty',
                innerHTML: `<i class="fas fa-file-pdf"></i><div>Could not render PDF</div>`
            }));
        }
    }

    _renderRow(line, expIdx, lineIdx) {
        line = line || {};
        const escape = (v) => this.app.escapeHtml(v);
        const subValue = line['Subcategory'] || '';
        const subField = (this.subcategories && this.subcategories.length > 0)
            ? this._renderSubcategorySelect(subValue)
            : `<input type="text" class="table-input" data-field="Subcategory" value="${escape(subValue)}" oninput="app.itemization.validateField(this)">`;

        const rate = (line['Daily rate'] !== undefined && line['Daily rate'] !== null) ? line['Daily rate'] : '';
        const qty = (line['Quantity'] !== undefined && line['Quantity'] !== null) ? line['Quantity'] : 1;

        return `
            <tr class="itemization-row" data-expense-index="${expIdx}" data-line-index="${lineIdx}">
                <td>${subField}</td>
                <td><input type="text" class="table-input" data-field="Start date" value="${escape(line['Start date'] || '')}" placeholder="M/D/YYYY" oninput="app.itemization.validateField(this)"></td>
                <td><input type="number" step="any" class="table-input" data-field="Daily rate" value="${escape(String(rate))}" oninput="app.itemization.onAmountChange(this, ${expIdx})"></td>
                <td><input type="number" step="any" class="table-input" data-field="Quantity" value="${escape(String(qty))}" oninput="app.itemization.onAmountChange(this, ${expIdx})"></td>
                <td><button type="button" class="itemization-row-remove" title="Remove row" aria-label="Remove row" onclick="app.itemization.removeRow(this)"><i class="fas fa-trash"></i></button></td>
            </tr>
        `;
    }

    _renderSubcategorySelect(selected) {
        const escape = (v) => this.app.escapeHtml(v);
        const options = this.subcategories.map(sub => {
            const sel = (sub === selected) ? ' selected' : '';
            return `<option value="${escape(sub)}"${sel}>${escape(sub)}</option>`;
        }).join('');
        const extra = (selected && !this.subcategories.includes(selected))
            ? `<option value="${escape(selected)}" selected>${escape(selected)} (unlisted)</option>`
            : '';
        return `<select class="table-input" data-field="Subcategory" onchange="app.itemization.validateField(this)"><option value="">— select —</option>${options}${extra}</select>`;
    }

    /**
     * Combined oninput handler for Daily rate and Quantity: validates then recalcs totals.
     */
    onAmountChange(input, expIdx) {
        this.validateField(input);
        this.recalcTotals(expIdx);
    }

    // ── Format helpers ──────────────────────────────────────────────────────

    _isValidMDYDate(value) {
        if (!value) return false;
        const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value);
        if (!m) return false;
        const month = parseInt(m[1], 10);
        const day = parseInt(m[2], 10);
        const year = parseInt(m[3], 10);
        const date = new Date(year, month - 1, day);
        return date.getFullYear() === year
            && date.getMonth() === month - 1
            && date.getDate() === day;
    }

    _isPositiveNumber(value) {
        if (value === '' || value === null || value === undefined) return false;
        const n = parseFloat(value);
        return !isNaN(n) && isFinite(n) && n > 0;
    }
}

// Expose globally so inline `onclick="app.itemization.…"` handlers can resolve it.
window.ItemizationManager = ItemizationManager;
