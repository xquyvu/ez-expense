/**
 * EZ Expense Frontend Application
 * Handles all client-side functionality for the expense management system
 */

class EZExpenseApp {
    constructor() {
        this.expenses = [];
        this.receipts = new Map(); // Map of expense ID to array of receipt data
        this.currentStep = 1;

        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        this.bindEvents();
        this.checkHealthStatus();
        this.updateExportMethodInfo();

        // Debug: Check if column config is loaded
        if (window.COLUMN_CONFIG) {
            console.log('Column config loaded successfully:', window.COLUMN_CONFIG);
        } else {
            console.error('Column config not loaded!');
        }

        console.log('EZ Expense App initialized');
    }

    /**
     * Get column width from configuration
     */
    getColumnWidth(columnName) {
        if (!window.COLUMN_CONFIG) {
            return 150; // fallback default
        }

        const config = window.COLUMN_CONFIG;
        return config.columnWidths[columnName] || config.defaultWidth;
    }

    /**
     * Calculate column width based on content if auto-resize is enabled
     */
    calculateColumnWidth(columnName, values) {
        if (!window.COLUMN_CONFIG || !window.COLUMN_CONFIG.autoResize) {
            return this.getColumnWidth(columnName);
        }

        const config = window.COLUMN_CONFIG;

        // Create a temporary element to measure text width
        const tempElement = document.createElement('span');
        tempElement.style.visibility = 'hidden';
        tempElement.style.position = 'absolute';
        tempElement.style.fontSize = '14px'; // Match table font size
        tempElement.style.fontFamily = 'inherit';
        document.body.appendChild(tempElement);

        // Measure column header width
        tempElement.textContent = columnName;
        let maxWidth = tempElement.offsetWidth;

        // Measure content widths (sample first 10 values for performance)
        const sampleValues = values.slice(0, 10);
        sampleValues.forEach(value => {
            tempElement.textContent = String(value || '');
            maxWidth = Math.max(maxWidth, tempElement.offsetWidth);
        });

        document.body.removeChild(tempElement);

        // Add padding and constrain to min/max
        const calculatedWidth = maxWidth + config.autoResizePadding;
        const configuredWidth = this.getColumnWidth(columnName);

        return Math.max(
            config.minWidth,
            Math.min(
                config.maxWidth,
                Math.max(calculatedWidth, configuredWidth)
            )
        );
    }

    /**
     * Apply column widths to table
     */
    applyColumnWidths(tableElement, columnNames) {
        if (!tableElement || !window.COLUMN_CONFIG) {
            console.warn('Cannot apply column widths - missing table or config');
            return;
        }

        const headerCells = tableElement.querySelectorAll('thead th');
        const config = window.COLUMN_CONFIG;

        console.log('Applying column widths:', {
            autoResize: config.autoResize,
            columnNames: columnNames,
            columnWidths: config.columnWidths
        });

        headerCells.forEach((th, index) => {
            const columnName = columnNames[index];
            if (columnName) {
                let width;

                if (columnName === 'Receipts') {
                    // Special handling for receipts column
                    width = config.columnWidths['Receipts'] || 250;
                } else if (config.autoResize) {
                    // Get sample values for this column
                    const values = this.expenses.map(expense => expense[columnName]);
                    width = this.calculateColumnWidth(columnName, values);
                } else {
                    width = this.getColumnWidth(columnName);
                }

                console.log(`Setting column "${columnName}" to width: ${width}px`);

                th.style.width = `${width}px`;
                th.style.minWidth = `${width}px`;
                th.style.maxWidth = `${width}px`;

                // Apply the same width to all cells in this column
                const columnCells = tableElement.querySelectorAll(`tbody td:nth-child(${index + 1})`);
                columnCells.forEach(td => {
                    td.style.width = `${width}px`;
                    td.style.minWidth = `${width}px`;
                    td.style.maxWidth = `${width}px`;
                });
            }
        });
    }

    /**
     * Initialize column resizing functionality
     */
    initColumnResizing() {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        const headers = table.querySelectorAll('thead th');
        headers.forEach((th, index) => {
            this.makeColumnResizable(th, index);
        });
    }

    /**
     * Make a column header resizable
     */
    makeColumnResizable(th, columnIndex) {
        // Don't make the receipts column resizable since it's sticky
        if (th.classList.contains('receipts-column')) {
            return;
        }

        // Create resize handle
        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'column-resize-handle';
        resizeHandle.style.cssText = `
            position: absolute;
            top: 0;
            right: 0;
            width: 5px;
            height: 100%;
            cursor: col-resize;
            background: transparent;
            z-index: 20;
        `;

        // Make the th position relative so the handle can be positioned absolutely
        th.style.position = 'relative';
        th.appendChild(resizeHandle);

        // Add resize functionality
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = th.offsetWidth;

            // Add visual feedback
            resizeHandle.style.background = 'rgba(0, 123, 255, 0.3)';
            document.body.style.cursor = 'col-resize';

            // Prevent text selection during resize
            document.body.style.userSelect = 'none';

            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const deltaX = e.clientX - startX;
            const newWidth = Math.max(80, startWidth + deltaX); // Minimum width of 80px

            this.resizeColumn(columnIndex, newWidth);
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;

                // Remove visual feedback
                resizeHandle.style.background = 'transparent';
                document.body.style.cursor = '';
                document.body.style.userSelect = '';

                // Save the new width to config (optional)
                this.saveColumnWidth(columnIndex, th.offsetWidth);
            }
        });

        // Add hover effect
        resizeHandle.addEventListener('mouseenter', () => {
            if (!isResizing) {
                resizeHandle.style.background = 'rgba(0, 123, 255, 0.1)';
            }
        });

        resizeHandle.addEventListener('mouseleave', () => {
            if (!isResizing) {
                resizeHandle.style.background = 'transparent';
            }
        });
    }

    /**
     * Resize a column to a specific width
     */
    resizeColumn(columnIndex, newWidth) {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        // Update header cell
        const th = table.querySelector(`thead th:nth-child(${columnIndex + 1})`);
        if (th) {
            th.style.width = `${newWidth}px`;
            th.style.minWidth = `${newWidth}px`;
            th.style.maxWidth = `${newWidth}px`;
        }

        // Update all data cells in this column
        const tds = table.querySelectorAll(`tbody td:nth-child(${columnIndex + 1})`);
        tds.forEach(td => {
            td.style.width = `${newWidth}px`;
            td.style.minWidth = `${newWidth}px`;
            td.style.maxWidth = `${newWidth}px`;
        });
    }

    /**
     * Save column width to config (optional - for persistence)
     */
    saveColumnWidth(columnIndex, width) {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        const th = table.querySelector(`thead th:nth-child(${columnIndex + 1})`);
        if (th && window.COLUMN_CONFIG) {
            const columnName = th.textContent.trim();

            // Update the runtime config
            window.COLUMN_CONFIG.columnWidths[columnName] = width;

            console.log(`Saved column "${columnName}" width: ${width}px`);

            // Note: This only saves to memory, not to the actual file
            // To persist changes, you'd need to implement server-side saving
        }
    }

    /**
     * Initialize column reordering functionality
     */
    initColumnReordering() {
        if (!window.COLUMN_CONFIG?.headerConfig?.allowReordering) return;

        const table = document.getElementById('expenses-table');
        if (!table) return;

        const headers = table.querySelectorAll('thead th');
        headers.forEach((th, index) => {
            this.makeColumnDraggable(th, index);
        });
    }

    /**
     * Make a column header draggable for reordering
     */
    makeColumnDraggable(th, columnIndex) {
        // Don't make the receipts column draggable since it's sticky
        if (th.classList.contains('receipts-column')) {
            return;
        }

        // Create drag handle area (separate from resize handle)
        const dragHandle = document.createElement('div');
        dragHandle.className = 'column-drag-handle';
        dragHandle.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 8px;
            height: 100%;
            cursor: grab;
            z-index: 15;
        `;

        th.appendChild(dragHandle);

        // Make the column draggable
        th.draggable = false; // We'll handle this manually

        let isDragging = false;
        let dragStartX = 0;
        let dragThreshold = 5; // Minimum pixels to move before starting drag

        dragHandle.addEventListener('mousedown', (e) => {
            // Only start drag on left mouse button
            if (e.button !== 0) return;

            dragStartX = e.clientX;
            isDragging = false;

            const mouseMoveHandler = (moveEvent) => {
                const deltaX = Math.abs(moveEvent.clientX - dragStartX);

                if (!isDragging && deltaX > dragThreshold) {
                    // Start dragging
                    isDragging = true;
                    this.startColumnDrag(th, columnIndex, moveEvent);
                    dragHandle.style.cursor = 'grabbing';
                    document.body.style.cursor = 'grabbing';
                }
            };

            const mouseUpHandler = () => {
                document.removeEventListener('mousemove', mouseMoveHandler);
                document.removeEventListener('mouseup', mouseUpHandler);

                if (isDragging) {
                    this.endColumnDrag();
                    dragHandle.style.cursor = 'grab';
                    document.body.style.cursor = '';
                }
            };

            document.addEventListener('mousemove', mouseMoveHandler);
            document.addEventListener('mouseup', mouseUpHandler);

            e.preventDefault();
        });

        // Hover effects
        dragHandle.addEventListener('mouseenter', () => {
            if (!isDragging) {
                th.style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
            }
        });

        dragHandle.addEventListener('mouseleave', () => {
            if (!isDragging) {
                th.style.backgroundColor = '';
            }
        });
    }

    /**
     * Start dragging a column
     */
    startColumnDrag(th, columnIndex, event) {
        this.dragData = {
            sourceIndex: columnIndex,
            sourceTh: th,
            ghost: null
        };

        // Create ghost element
        const ghost = th.cloneNode(true);
        ghost.style.cssText = `
            position: fixed;
            top: ${event.clientY - 20}px;
            left: ${event.clientX - th.offsetWidth / 2}px;
            width: ${th.offsetWidth}px;
            height: ${th.offsetHeight}px;
            background: rgba(0, 123, 255, 0.9);
            color: white;
            border-radius: 4px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            pointer-events: none;
            opacity: 0.8;
        `;

        document.body.appendChild(ghost);
        this.dragData.ghost = ghost;

        // Add visual feedback to source column
        th.style.opacity = '0.5';

        // Set up drop zones
        this.setupDropZones();

        // Track mouse movement for ghost
        this.ghostMoveHandler = (e) => {
            if (this.dragData.ghost) {
                this.dragData.ghost.style.left = `${e.clientX - th.offsetWidth / 2}px`;
                this.dragData.ghost.style.top = `${e.clientY - 20}px`;
            }
        };

        document.addEventListener('mousemove', this.ghostMoveHandler);
    }

    /**
     * Set up drop zones for column reordering
     */
    setupDropZones() {
        const table = document.getElementById('expenses-table');
        const headers = table.querySelectorAll('thead th:not(.receipts-column)');

        headers.forEach((th, index) => {
            if (index === this.dragData.sourceIndex) return;

            th.addEventListener('mouseenter', this.handleDropZoneEnter.bind(this, index));
            th.addEventListener('mouseleave', this.handleDropZoneLeave.bind(this, index));
        });
    }

    /**
     * Handle mouse entering a drop zone
     */
    handleDropZoneEnter(targetIndex, event) {
        const th = event.currentTarget;
        th.style.backgroundColor = 'rgba(40, 167, 69, 0.2)';
        th.style.borderLeft = '3px solid #28a745';

        this.dragData.targetIndex = targetIndex;
    }

    /**
     * Handle mouse leaving a drop zone
     */
    handleDropZoneLeave(targetIndex, event) {
        const th = event.currentTarget;
        th.style.backgroundColor = '';
        th.style.borderLeft = '';

        if (this.dragData.targetIndex === targetIndex) {
            this.dragData.targetIndex = null;
        }
    }

    /**
     * End column dragging
     */
    endColumnDrag() {
        if (!this.dragData) return;

        // Remove ghost
        if (this.dragData.ghost) {
            document.body.removeChild(this.dragData.ghost);
        }

        // Remove mouse move handler
        if (this.ghostMoveHandler) {
            document.removeEventListener('mousemove', this.ghostMoveHandler);
        }

        // Restore source column appearance
        this.dragData.sourceTh.style.opacity = '';
        this.dragData.sourceTh.style.backgroundColor = '';

        // Clean up drop zones
        this.cleanupDropZones();

        // Perform the reorder if we have a valid target
        if (this.dragData.targetIndex !== null && this.dragData.targetIndex !== this.dragData.sourceIndex) {
            this.reorderColumn(this.dragData.sourceIndex, this.dragData.targetIndex);
        }

        this.dragData = null;
    }

    /**
     * Clean up drop zone styling
     */
    cleanupDropZones() {
        const table = document.getElementById('expenses-table');
        const headers = table.querySelectorAll('thead th:not(.receipts-column)');

        headers.forEach((th) => {
            th.style.backgroundColor = '';
            th.style.borderLeft = '';
            th.removeEventListener('mouseenter', this.handleDropZoneEnter);
            th.removeEventListener('mouseleave', this.handleDropZoneLeave);
        });
    }

    /**
     * Reorder columns in the table
     */
    reorderColumn(fromIndex, toIndex) {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        console.log(`Reordering column from index ${fromIndex} to ${toIndex}`);

        // Get all rows (header and data)
        const headerRow = table.querySelector('thead tr');
        const dataRows = table.querySelectorAll('tbody tr');

        // Move header cell
        const headerCells = Array.from(headerRow.children);
        const sourceHeaderCell = headerCells[fromIndex];

        if (toIndex < fromIndex) {
            headerRow.insertBefore(sourceHeaderCell, headerCells[toIndex]);
        } else {
            headerRow.insertBefore(sourceHeaderCell, headerCells[toIndex + 1]);
        }

        // Move data cells in all rows
        dataRows.forEach(row => {
            const cells = Array.from(row.children);
            const sourceCell = cells[fromIndex];

            if (toIndex < fromIndex) {
                row.insertBefore(sourceCell, cells[toIndex]);
            } else {
                row.insertBefore(sourceCell, cells[toIndex + 1]);
            }
        });

        // Reinitialize functionality for the reordered table
        setTimeout(() => {
            this.initColumnResizing();
            this.initColumnReordering();
        }, 100);

        console.log('Column reorder completed');
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Import expenses events
        document.getElementById('import-from-website-btn').addEventListener('click', () => {
            this.importFromWebsite();
        });

        document.getElementById('upload-csv-btn').addEventListener('click', () => {
            document.getElementById('csv-file-input').click();
        });

        document.getElementById('csv-file-input').addEventListener('change', (e) => {
            this.handleCSVUpload(e.target.files[0]);
        });

        // Table management events
        document.getElementById('add-row-btn').addEventListener('click', () => {
            this.addNewRow();
        });

        // Export events
        document.getElementById('export-enhanced-btn').addEventListener('click', () => {
            this.exportEnhanced();
        });

        // Global drag and drop events
        document.addEventListener('dragover', this.handleDragOver.bind(this));
        document.addEventListener('drop', this.handleDrop.bind(this));
    }

    /**
     * Check if the backend is healthy
     */
    async checkHealthStatus() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            if (data.status === 'healthy') {
                console.log('Backend connection established');
            }
        } catch (error) {
            console.error('Backend connection failed:', error);
            this.showToast('Unable to connect to backend server', 'error');
        }
    }

    /**
     * Import expenses from My Expense system
     */
    async importFromWebsite() {
        this.showLoading('Importing expenses from My Expense...');

        try {
            // The backend now automatically handles DEBUG vs non-DEBUG mode
            console.log('Importing expenses (backend will choose mock vs real based on DEBUG setting)');
            const response = await fetch('/api/expenses/import', { method: 'POST' });

            const data = await response.json();

            if (data.success) {
                console.log(`Successfully imported ${data.count} expenses from ${data.source} source`);
                // Map all expense data, preserving all columns from the imported data
                this.expenses = data.data.map((expense, index) => {
                    // Start with all the original data
                    const mappedExpense = { ...expense };

                    // Ensure we have a consistent id field
                    if (!mappedExpense.id) {
                        mappedExpense.id = expense.id || expense['Created ID'] || index + 1;
                    }

                    return mappedExpense;
                });

                this.displayExpensesTable();
                this.showToast(data.message || 'Expenses imported successfully', 'success');
                this.showStep(2);
            } else {
                throw new Error(data.message || 'Import failed');
            }

        } catch (error) {
            console.error('Error importing expenses:', error);
            this.showToast('Failed to import expenses from My Expense: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Handle CSV file upload
     */
    async handleCSVUpload(file) {
        if (!file || !file.name.toLowerCase().endsWith('.csv')) {
            this.showToast('Please select a valid CSV file', 'error');
            return;
        }

        this.showLoading('Processing CSV file...');

        try {
            const csvText = await this.readFileAsText(file);
            const expenses = this.parseCSV(csvText);

            if (expenses.length === 0) {
                throw new Error('No valid expense data found in CSV');
            }

            this.expenses = expenses;
            this.displayExpensesTable();
            this.showToast(`Loaded ${expenses.length} expenses from CSV`, 'success');
            this.showStep(2);

        } catch (error) {
            console.error('Error processing CSV:', error);
            this.showToast('Failed to process CSV file: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Parse CSV content into expense objects
     */
    parseCSV(csvText) {
        const lines = csvText.trim().split('\n');
        if (lines.length < 2) {
            throw new Error('CSV file must have at least a header row and one data row');
        }

        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const expenses = [];

        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
            if (values.length !== headers.length) continue;

            const expense = { id: i };
            headers.forEach((header, index) => {
                expense[header] = values[index];
            });
            expenses.push(expense);
        }

        return expenses;
    }

    /**
     * Display expenses in the table
     */
    displayExpensesTable() {
        if (this.expenses.length === 0) return;

        const tableHeader = document.getElementById('table-header');
        const tableBody = document.getElementById('table-body');

        // Clear existing content
        tableHeader.innerHTML = '';
        tableBody.innerHTML = '';

        // Get all unique keys from expenses
        const allKeys = new Set();
        this.expenses.forEach(expense => {
            Object.keys(expense).forEach(key => {
                if (key !== 'id') allKeys.add(key);
            });
        });

        // Convert to array for regular columns
        const regularKeys = Array.from(allKeys);

        // Create header row
        const headerRow = document.createElement('tr');

        // Add regular columns
        regularKeys.forEach(key => {
            const th = document.createElement('th');
            th.textContent = key;
            th.title = key; // Add tooltip with full column name
            headerRow.appendChild(th);
        });

        // Add receipts column (sticky on the right)
        const receiptTh = document.createElement('th');
        receiptTh.textContent = 'Receipts';
        receiptTh.title = 'Receipts'; // Add tooltip
        receiptTh.className = 'receipts-column';
        headerRow.appendChild(receiptTh);

        tableHeader.appendChild(headerRow);

        // Create data rows
        this.expenses.forEach((expense, index) => {
            const row = document.createElement('tr');
            row.dataset.expenseId = expense.id;
            row.dataset.rowIndex = index;

            // Add regular columns
            regularKeys.forEach(key => {
                const td = document.createElement('td');
                const formattedValue = this.formatDateValue(expense[key] || '');
                td.innerHTML = `<input type="text" value="${formattedValue}" data-field="${key}" class="table-input">`;
                row.appendChild(td);
            });

            // Add receipts column (sticky on the right)
            const receiptTd = document.createElement('td');
            receiptTd.className = 'receipt-cell receipts-column';
            receiptTd.innerHTML = this.createReceiptCell(expense.id);
            row.appendChild(receiptTd);

            // Make row droppable for receipts
            this.makeRowDroppable(row);
            tableBody.appendChild(row);
        });

        // Apply column widths after table is created
        const allColumnNames = [...regularKeys, 'Receipts'];
        const tableElement = document.getElementById('expenses-table');
        this.applyColumnWidths(tableElement, allColumnNames);

        // Initialize column resizing functionality
        this.initColumnResizing();

        // Initialize column reordering functionality
        this.initColumnReordering();

        this.updateStatistics();
    }    /**
     * Format date values from JSON to YYYY-MM-DD format
     */
    formatDateValue(value) {
        if (!value || typeof value !== 'string') {
            return value;
        }

        // Detect various date formats
        // ISO 8601: "2025-09-14T10:30:00", "2025-09-14T10:30:00.123Z", "2025-09-14"
        const isoDateTimeRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
        const isoDateOnlyRegex = /^\d{4}-\d{2}-\d{2}$/;

        // JavaScript Date.toString() format: "Tue, 09 Sep 2025 00:00:00 GMT"
        const jsDateStringRegex = /^[A-Za-z]{3},\s\d{2}\s[A-Za-z]{3}\s\d{4}\s\d{2}:\d{2}:\d{2}\sGMT$/;

        // RFC 2822 format: "Tue Sep 09 2025 00:00:00 GMT+0000"
        const rfc2822Regex = /^[A-Za-z]{3}\s[A-Za-z]{3}\s\d{2}\s\d{4}\s\d{2}:\d{2}:\d{2}/;

        // Try pattern matching first
        if (isoDateTimeRegex.test(value) || isoDateOnlyRegex.test(value) ||
            jsDateStringRegex.test(value) || rfc2822Regex.test(value)) {
            try {
                const date = new Date(value);
                if (!isNaN(date.getTime())) {
                    // Return in YYYY-MM-DD format
                    return date.toISOString().split('T')[0];
                }
            } catch (error) {
                console.warn('Error parsing date:', value, error);
            }
        }

        // Fallback: Try to parse any string that might be a date
        // This is more aggressive but helps catch edge cases
        try {
            const date = new Date(value);
            // Check if it's a valid date and the original value looks date-like
            if (!isNaN(date.getTime()) &&
                (value.includes('GMT') || value.includes('UTC') ||
                    value.match(/\d{4}/) || value.includes('Jan') || value.includes('Feb') ||
                    value.includes('Mar') || value.includes('Apr') || value.includes('May') ||
                    value.includes('Jun') || value.includes('Jul') || value.includes('Aug') ||
                    value.includes('Sep') || value.includes('Oct') || value.includes('Nov') ||
                    value.includes('Dec'))) {
                // Log for debugging
                console.log('Date detected and converted:', value, '→', date.toISOString().split('T')[0]);
                return date.toISOString().split('T')[0];
            }
        } catch (error) {
            // Silent fallback - not a date
        }

        return value; // Return original if not a date or parsing failed
    }    /**
     * Create receipt cell HTML
     */
    createReceiptCell(expenseId) {
        const receipts = this.receipts.get(expenseId) || [];

        let html = '';

        // Display existing receipts
        if (receipts.length > 0) {
            html += '<div class="receipts-container">';
            receipts.forEach((receipt, index) => {
                // Escape quotes in preview URL for HTML attributes
                const escapedPreview = receipt.preview ? receipt.preview.replace(/'/g, '&#39;') : '';
                const escapedName = receipt.name ? receipt.name.replace(/'/g, '&#39;') : '';

                html += `
                    <div class="receipt-preview"
                         data-receipt-index="${index}"
                         data-expense-id="${expenseId}"
                         draggable="true"
                         ondragstart="app.handleReceiptDragStart(event, ${expenseId}, ${index})"
                         ondragend="app.handleReceiptDragEnd(event)">
                        ${receipt.type === 'image' ?
                        `<img src="${receipt.preview}" alt="Receipt" class="receipt-thumbnail"
                              onclick="app.showReceiptModal(${expenseId}, ${index})"
                              onmouseenter="app.showTooltip(event, '${escapedPreview}', 'image')"
                              onmouseleave="app.hideTooltip()">` :
                        receipt.preview && receipt.preview.startsWith('data:image') ?
                            `<img src="${receipt.preview}" alt="PDF Preview" class="receipt-thumbnail"
                                  onclick="app.showReceiptModal(${expenseId}, ${index})"
                                  onmouseenter="app.showTooltip(event, '${escapedPreview}', 'pdf')"
                                  onmouseleave="app.hideTooltip()">` :
                            `<div class="pdf-preview receipt-thumbnail"
                                  onclick="app.showReceiptModal(${expenseId}, ${index})"
                                  onmouseenter="app.showTooltip(event, null, 'pdf', '${escapedName}')"
                                  onmouseleave="app.hideTooltip()">
                            <i class="fas fa-file-pdf"></i>
                            <div class="pdf-label">PDF</div>
                        </div>`
                    }
                        <div class="receipt-info">
                            <div class="receipt-name">${receipt.name}</div>
                            <div class="receipt-confidence">Match: ${receipt.confidence}%</div>
                        </div>
                        <button onclick="app.removeReceipt(${expenseId}, ${index})" class="btn btn-sm">
                            <i class="fas fa-trash"></i>
                        </button>
                        <div class="drag-indicator">
                            <i class="fas fa-arrows-alt"></i>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        // Always show the attach receipt button
        html += `
            <button onclick="app.selectReceipt(${expenseId})" class="attach-receipt-btn">
                <i class="fas fa-paperclip"></i> ${receipts.length > 0 ? 'Add More Receipts' : 'Attach Receipts'}
            </button>
            <input type="file" id="receipt-input-${expenseId}" accept="image/*,.pdf" multiple style="display: none;"
                   onchange="app.handleMultipleReceiptSelection(${expenseId}, this.files)">
        `;

        return html;
    }

    /**
     * Make a table row droppable for receipt files and receipt transfers
     */
    makeRowDroppable(row) {
        row.addEventListener('dragover', (e) => {
            e.preventDefault();

            // Check if we're dragging a receipt (not a file)
            const isDraggingReceipt = e.dataTransfer.types.includes('application/x-receipt-data');
            const isDraggingFile = e.dataTransfer.types.includes('Files');

            if (isDraggingReceipt || isDraggingFile) {
                row.classList.add('drag-over');

                // Add different styles for receipt vs file drops
                if (isDraggingReceipt) {
                    row.classList.add('receipt-drag-over');
                } else {
                    row.classList.add('file-drag-over');
                }
            }
        });

        row.addEventListener('dragleave', (e) => {
            // Only remove highlight if we're actually leaving the row
            if (!row.contains(e.relatedTarget)) {
                row.classList.remove('drag-over', 'receipt-drag-over', 'file-drag-over');
            }
        });

        row.addEventListener('drop', (e) => {
            e.preventDefault();
            row.classList.remove('drag-over', 'receipt-drag-over', 'file-drag-over');

            const expenseId = parseInt(row.dataset.expenseId);

            // Check if we're dropping a receipt from another expense
            const receiptData = e.dataTransfer.getData('application/x-receipt-data');
            if (receiptData) {
                const draggedReceipt = JSON.parse(receiptData);
                this.handleReceiptDrop(draggedReceipt, expenseId);
                return;
            }

            // Otherwise, handle file drops
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                // Use the new multiple file handler
                this.handleMultipleReceiptSelection(expenseId, files);
            }
        });
    }

    /**
     * Handle drag over events
     */
    handleDragOver(e) {
        e.preventDefault();
    }

    /**
     * Handle drop events
     */
    handleDrop(e) {
        e.preventDefault();
        // Handled by individual row drop handlers
    }

    /**
     * Select receipt file for an expense
     */
    selectReceipt(expenseId) {
        document.getElementById(`receipt-input-${expenseId}`).click();
    }

    /**
     * Handle multiple receipt file selection
     */
    async handleMultipleReceiptSelection(expenseId, files) {
        if (!files || files.length === 0) return;

        const filesArray = Array.from(files);
        const validFiles = [];
        const invalidFiles = [];

        // Validate all files first
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'application/pdf'];
        const maxFileSize = 16 * 1024 * 1024; // 16MB

        for (const file of filesArray) {
            if (!allowedTypes.includes(file.type)) {
                invalidFiles.push(`${file.name}: Invalid file type`);
            } else if (file.size > maxFileSize) {
                invalidFiles.push(`${file.name}: File too large (max 16MB)`);
            } else {
                validFiles.push(file);
            }
        }

        // Show errors for invalid files
        if (invalidFiles.length > 0) {
            this.showToast(`Skipped ${invalidFiles.length} invalid files: ${invalidFiles.join(', ')}`, 'warning');
        }

        if (validFiles.length === 0) {
            this.showToast('No valid files to upload', 'error');
            return;
        }

        // If only one file, use the single file handler for consistency
        if (validFiles.length === 1) {
            return this.handleReceiptSelection(expenseId, validFiles[0]);
        }

        this.showLoading(`Processing ${validFiles.length} receipts...`);

        try {
            // Use bulk upload endpoint for multiple files
            const formData = new FormData();

            // Add all valid files
            validFiles.forEach(file => {
                formData.append('files', file);
            });

            formData.append('expense_id', expenseId);

            const uploadResponse = await fetch('/api/receipts/upload-multiple', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error('Failed to upload receipts');
            }

            const uploadData = await uploadResponse.json();

            if (!uploadData.success) {
                throw new Error(uploadData.message || 'Upload failed');
            }

            // Process each successfully uploaded file
            const expense = this.expenses.find(e => e.id === expenseId);
            const existingReceipts = this.receipts.get(expenseId) || [];

            let successCount = 0;
            let failCount = 0;

            for (const result of uploadData.results) {
                if (result.success) {
                    try {
                        // Find the original file object
                        const originalFile = validFiles.find(f => f.name === result.file_info.original_filename);

                        if (originalFile) {
                            // Create preview
                            let preview = '';
                            let type = 'pdf';

                            if (originalFile.type.startsWith('image/')) {
                                preview = await this.createImagePreview(originalFile);
                                type = 'image';
                            } else if (originalFile.type === 'application/pdf') {
                                preview = await this.createPDFPreview(originalFile);
                                type = 'pdf';
                            }

                            // Calculate match confidence if possible
                            let confidence = 85; // Default confidence
                            try {
                                if (expense) {
                                    const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json'
                                        },
                                        body: JSON.stringify({
                                            expense_data: expense,
                                            receipt_path: result.file_info.file_path
                                        })
                                    });

                                    if (matchResponse.ok) {
                                        const matchData = await matchResponse.json();
                                        if (matchData.success) {
                                            confidence = matchData.confidence_score;
                                            if (confidence <= 1) {
                                                confidence *= 100;
                                            }
                                            confidence = Math.round(confidence);
                                        }
                                    }
                                }
                            } catch (matchError) {
                                console.warn('Could not calculate match confidence:', matchError);
                            }

                            // Add new receipt to the array
                            const newReceipt = {
                                name: result.file_info.original_filename,
                                type: type,
                                preview: preview,
                                confidence: confidence,
                                file: originalFile,
                                filePath: result.file_info.file_path,
                                filename: result.file_info.saved_filename,  // Store the saved filename for API calls
                                originalFilename: result.file_info.original_filename
                            };

                            existingReceipts.push(newReceipt);
                            successCount++;
                        }
                    } catch (error) {
                        console.error(`Error processing ${result.file_info.original_filename}:`, error);
                        failCount++;
                    }
                } else {
                    failCount++;
                }
            }

            // Store updated receipts array
            if (existingReceipts.length > 0) {
                this.receipts.set(expenseId, existingReceipts);
            }

            // Refresh the table display
            this.displayExpensesTable();
            this.showStep(2);

            // Show summary message
            if (successCount > 0 && failCount === 0) {
                this.showToast(`Successfully attached ${successCount} receipt${successCount > 1 ? 's' : ''}`, 'success');
            } else if (successCount > 0 && failCount > 0) {
                this.showToast(`Attached ${successCount} receipts, ${failCount} failed`, 'warning');
            } else {
                this.showToast('Failed to attach any receipts', 'error');
            }

        } catch (error) {
            console.error('Error processing multiple receipts:', error);
            this.showToast('Failed to process receipts: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Handle receipt file selection
     */
    async handleReceiptSelection(expenseId, file) {
        if (!file) return;

        // Validate file type
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'application/pdf'];
        if (!allowedTypes.includes(file.type)) {
            this.showToast('Please select an image or PDF file', 'error');
            return;
        }

        // Validate file size (16MB max)
        if (file.size > 16 * 1024 * 1024) {
            this.showToast('File size must be less than 16MB', 'error');
            return;
        }

        this.showLoading('Processing receipt...');

        try {
            // Create preview
            let preview = '';
            let type = 'pdf';

            if (file.type.startsWith('image/')) {
                preview = await this.createImagePreview(file);
                type = 'image';
            } else if (file.type === 'application/pdf') {
                preview = await this.createPDFPreview(file);
                type = 'pdf';
            }

            // Calculate actual confidence score using backend API
            const matchResult = await this.calculateReceiptMatchScore(expenseId, file);

            // Get existing receipts array or create new one
            const existingReceipts = this.receipts.get(expenseId) || [];

            // Add new receipt to the array
            const newReceipt = {
                name: file.name,
                type: type,
                preview: preview,
                confidence: matchResult.confidence,
                file: file,
                filePath: matchResult.filePath,  // Store the absolute file path
                filename: matchResult.savedFilename,  // Store the saved filename for API calls
                originalFilename: matchResult.originalFilename
            };

            existingReceipts.push(newReceipt);

            // Store updated receipts array
            this.receipts.set(expenseId, existingReceipts);

            // Refresh the table display
            this.displayExpensesTable();
            this.showToast('Receipt attached successfully', 'success');
            this.showStep(2);

        } catch (error) {
            console.error('Error processing receipt:', error);
            this.showToast('Failed to process receipt file', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Calculate receipt match confidence score using backend API
     */
    async calculateReceiptMatchScore(expenseId, file) {
        let uploadData = null;

        try {
            // First, upload the receipt file to get a file path
            const formData = new FormData();
            formData.append('file', file);
            formData.append('expense_id', expenseId);

            const uploadResponse = await fetch('/api/receipts/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error('Failed to upload receipt');
            }

            uploadData = await uploadResponse.json();
            const receiptPath = uploadData.file_info.file_path;

            // Get expense data for this expense ID
            const expense = this.expenses.find(e => e.id === expenseId);
            if (!expense) {
                throw new Error('Expense not found');
            }

            // Call the match-receipt endpoint
            const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expense_data: expense,
                    receipt_path: receiptPath
                })
            });

            if (!matchResponse.ok) {
                throw new Error('Failed to calculate match score');
            }

            const matchData = await matchResponse.json();

            if (matchData.success) {
                // Convert to percentage (multiply by 100 if needed)
                let confidence = matchData.confidence_score;
                if (confidence <= 1) {
                    confidence *= 100;
                }
                return {
                    confidence: Math.round(confidence),
                    filePath: receiptPath,
                    savedFilename: uploadData.file_info.saved_filename,
                    originalFilename: uploadData.file_info.original_filename
                };
            } else {
                throw new Error(matchData.message || 'Match calculation failed');
            }

        } catch (error) {
            console.warn('Error calculating confidence score:', error);

            // If we have upload data, use it even if match calculation failed
            if (uploadData && uploadData.file_info) {
                return {
                    confidence: 85, // Default confidence
                    filePath: uploadData.file_info.file_path,
                    savedFilename: uploadData.file_info.saved_filename,
                    originalFilename: uploadData.file_info.original_filename
                };
            }

            // Complete fallback if upload also failed
            return {
                confidence: 85,
                filePath: null,
                savedFilename: null,
                originalFilename: file.name
            };
        }
    }

    /**
     * Remove receipt from expense
     */
    removeReceipt(expenseId, receiptIndex = null) {
        const existingReceipts = this.receipts.get(expenseId) || [];

        if (receiptIndex !== null && receiptIndex >= 0 && receiptIndex < existingReceipts.length) {
            // Remove specific receipt by index
            existingReceipts.splice(receiptIndex, 1);

            if (existingReceipts.length > 0) {
                this.receipts.set(expenseId, existingReceipts);
            } else {
                this.receipts.delete(expenseId);
            }

            this.showToast('Receipt removed', 'info');
        } else {
            // Remove all receipts for the expense (legacy support)
            this.receipts.delete(expenseId);
            this.showToast('All receipts removed', 'info');
        }

        this.displayExpensesTable();
    }

    /**
     * Create image preview URL
     */
    createImagePreview(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(file);
        });
    }

    /**
     * Create PDF preview (first page as image)
     */
    async createPDFPreview(file) {
        try {
            // For now, we'll use the PDF.js library if available, otherwise return a data URL for the PDF
            // This requires PDF.js library to be loaded
            if (typeof pdfjsLib !== 'undefined') {
                const arrayBuffer = await file.arrayBuffer();
                const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
                const page = await pdf.getPage(1);

                const scale = 1.5; // High quality preview scale for better tooltip display
                const viewport = page.getViewport({ scale });

                const canvas = document.createElement('canvas');
                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                await page.render({
                    canvasContext: context,
                    viewport: viewport
                }).promise;

                return canvas.toDataURL();
            } else {
                // Fallback: return data URL for the PDF file itself
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = (e) => resolve(e.target.result);
                    reader.readAsDataURL(file);
                });
            }
        } catch (error) {
            console.warn('Error creating PDF preview:', error);
            // Return a default PDF data URL
            return 'data:application/pdf;base64,';
        }
    }

    /**
     * Show receipt in modal for full view
     */
    showReceiptModal(expenseId, receiptIndex = 0) {
        const receipts = this.receipts.get(expenseId);
        if (!receipts || receipts.length === 0) return;

        const receipt = receipts[receiptIndex];
        if (!receipt) return;

        // Create modal if it doesn't exist
        let modal = document.getElementById('receipt-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'receipt-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Receipt Preview</h3>
                        <span class="close" onclick="app.closeReceiptModal()">&times;</span>
                    </div>
                    <div class="modal-body">
                        <div id="receipt-navigation" class="receipt-navigation"></div>
                        <div id="receipt-content"></div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Update navigation if multiple receipts
        const navigationDiv = document.getElementById('receipt-navigation');
        if (receipts.length > 1) {
            navigationDiv.innerHTML = `
                <div class="navigation-controls">
                    <span class="receipt-counter">${receiptIndex + 1} of ${receipts.length}</span>
                    <button onclick="app.showReceiptModal(${expenseId}, ${Math.max(0, receiptIndex - 1)})"
                            ${receiptIndex === 0 ? 'disabled' : ''} class="nav-btn">
                        <i class="fas fa-chevron-left"></i> Previous
                    </button>
                    <button onclick="app.showReceiptModal(${expenseId}, ${Math.min(receipts.length - 1, receiptIndex + 1)})"
                            ${receiptIndex === receipts.length - 1 ? 'disabled' : ''} class="nav-btn">
                        Next <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
                <div class="receipt-title">${receipt.name}</div>
            `;
        } else {
            navigationDiv.innerHTML = `<div class="receipt-title">${receipt.name}</div>`;
        }

        const contentDiv = document.getElementById('receipt-content');

        if (receipt.type === 'image') {
            contentDiv.innerHTML = `<img src="${receipt.preview}" alt="Receipt" style="max-width: 100%; max-height: 80vh;">`;
        } else if (receipt.type === 'pdf') {
            // For PDF, show embedded PDF viewer
            const pdfUrl = URL.createObjectURL(receipt.file);
            contentDiv.innerHTML = `
                <iframe src="${pdfUrl}" width="100%" height="600px" style="border: none;">
                    <p>PDF cannot be displayed. <a href="${pdfUrl}" target="_blank">Click here to open in new tab</a></p>
                </iframe>
            `;
        }

        modal.style.display = 'block';
    }

    /**
     * Close receipt modal
     */
    closeReceiptModal() {
        const modal = document.getElementById('receipt-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Show tooltip with larger image preview
     */
    showTooltip(event, imageSrc, type, fileName = '') {
        // Remove any existing tooltip
        this.hideTooltip();

        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.id = 'receipt-tooltip';
        tooltip.className = 'receipt-tooltip';

        if (type === 'image' && imageSrc) {
            tooltip.innerHTML = `
                <div class="tooltip-content">
                    <img src="${imageSrc}" alt="Receipt Preview" class="tooltip-image">
                </div>
            `;
        } else if (type === 'pdf' && imageSrc && imageSrc.startsWith('data:image')) {
            // PDF with rendered preview image - show the preview image enlarged
            tooltip.innerHTML = `
                <div class="tooltip-content">
                    <img src="${imageSrc}" alt="PDF Preview" class="tooltip-image">
                </div>
            `;
        } else if (type === 'pdf') {
            // PDF without preview image - show info card
            tooltip.innerHTML = `
                <div class="tooltip-content pdf-tooltip">
                    <i class="fas fa-file-pdf"></i>
                    <div class="tooltip-text">
                        <strong>PDF Receipt</strong>
                        <div class="tooltip-filename">${fileName}</div>
                        <div class="tooltip-hint">Click to view full document</div>
                    </div>
                </div>
            `;
        }

        document.body.appendChild(tooltip);

        // Wait for the tooltip to be fully rendered before positioning
        setTimeout(() => {
            // Position tooltip in upper-right direction from mouse
            const mouseX = event.clientX;
            const mouseY = event.clientY;
            const offset = 15;

            // Get actual dimensions after rendering
            const tooltipRect = tooltip.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            // Calculate initial position (upper-right from mouse)
            let left = mouseX + offset;
            let top = mouseY - tooltipRect.height - offset;

            // Adjust horizontally if tooltip would go off right edge
            if (left + tooltipRect.width > viewportWidth) {
                left = mouseX - tooltipRect.width - offset; // Move to upper-left instead
            }

            // Adjust vertically if tooltip would go off top edge
            if (top < 0) {
                top = mouseY + offset; // Move to lower position instead

                // If it still doesn't fit at the bottom, center it vertically
                if (top + tooltipRect.height > viewportHeight) {
                    top = Math.max(0, (viewportHeight - tooltipRect.height) / 2);
                }
            }

            // Ensure tooltip doesn't go off left edge
            if (left < 0) {
                left = offset;
            }

            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';

            // Add entrance animation
            tooltip.classList.add('tooltip-visible');
        }, 10);
    }

    /**
     * Hide tooltip
     */
    hideTooltip() {
        const tooltip = document.getElementById('receipt-tooltip');
        if (tooltip) {
            tooltip.classList.remove('tooltip-visible');
            setTimeout(() => {
                if (tooltip.parentNode) {
                    tooltip.parentNode.removeChild(tooltip);
                }
            }, 200);
        }
    }

    /**
     * Add new empty row to the table
     */
    addNewRow() {
        if (this.expenses.length === 0) {
            this.showToast('Please import expenses first', 'error');
            return;
        }

        // Get the structure from the first expense
        const newExpense = { id: Date.now() }; // Use timestamp as temporary ID

        // Copy the structure from the first expense
        Object.keys(this.expenses[0]).forEach(key => {
            if (key !== 'id') {
                newExpense[key] = '';
            }
        });

        this.expenses.push(newExpense);
        this.displayExpensesTable();
        this.showToast('New row added', 'success');
    }

    /**
     * Export data to CSV
     */
    async exportToCSV() {
        if (this.expenses.length === 0) {
            this.showToast('No expenses to export', 'error');
            return;
        }

        this.showLoading('Exporting expenses...');

        try {
            // Prepare data for export
            const exportData = this.expenses.map(expense => {
                const exportRow = { ...expense };

                // Add receipt information
                const receipts = this.receipts.get(expense.id) || [];
                if (receipts.length > 0) {
                    // Join multiple receipt names with semicolon
                    exportRow.receipt_names = receipts.map(r => r.name).join('; ');
                    // Join multiple receipt file paths with semicolon
                    exportRow.receipt_file_paths = receipts.map(r => r.filePath || 'N/A').join('; ');
                    // Use average confidence or highest confidence
                    exportRow.receipt_confidence = Math.round(
                        receipts.reduce((sum, r) => sum + r.confidence, 0) / receipts.length
                    );
                    exportRow.receipt_count = receipts.length;
                } else {
                    exportRow.receipt_names = '';
                    exportRow.receipt_file_paths = '';
                    exportRow.receipt_confidence = '';
                    exportRow.receipt_count = 0;
                }

                // Remove internal ID
                delete exportRow.id;

                return exportRow;
            });

            const defaultFilename = `ez-expense-export-${new Date().toISOString().split('T')[0]}.csv`;

            // Check if File System Access API is supported
            if ('showSaveFilePicker' in window) {
                await this.exportWithFilePicker(exportData, defaultFilename);
            } else {
                // Fallback to traditional server-side export
                await this.exportTraditional(exportData, defaultFilename);
            }

        } catch (error) {
            console.error('Export error:', error);
            this.showToast(`Export failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Export using File System Access API (modern browsers)
     */
    async exportWithFilePicker(exportData, defaultFilename) {
        try {
            // Show file picker
            const fileHandle = await window.showSaveFilePicker({
                suggestedName: defaultFilename,
                types: [{
                    description: 'CSV files',
                    accept: { 'text/csv': ['.csv'] },
                }],
            });

            // Get CSV data from backend
            const response = await fetch('/api/expenses/export/data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expenses: exportData,
                    filename: defaultFilename
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || 'Failed to generate CSV data');
            }

            if (result.success) {
                // Write to the chosen file
                const writable = await fileHandle.createWritable();
                await writable.write(result.export_data.csv_data);
                await writable.close();

                this.showToast(
                    `Expenses exported successfully to your chosen location!\n\nExpenses: ${result.export_data.expense_count}`,
                    'success'
                );

                console.log('Export completed successfully using File System Access API');
                console.log('Expense count:', result.export_data.expense_count);
            } else {
                throw new Error(result.message || 'Export failed');
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                // User cancelled the file picker
                this.showToast('Export cancelled', 'info');
                return;
            }

            console.warn('File System Access API failed, falling back to traditional export:', error);
            // Fall back to traditional export
            await this.exportTraditional(exportData, defaultFilename);
        }
    }

    /**
     * Traditional export method (server-side storage or direct download)
     */
    async exportTraditional(exportData, defaultFilename) {
        // Try client-side download first, then fallback to server-side
        try {
            const response = await fetch('/api/expenses/export/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expenses: exportData,
                    filename: defaultFilename
                })
            });

            if (response.ok) {
                // Trigger download
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;

                // Get filename from Content-Disposition header
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = defaultFilename;
                if (contentDisposition) {
                    const matches = /filename="([^"]*)"/.exec(contentDisposition);
                    if (matches && matches[1]) {
                        filename = matches[1];
                    }
                }
                a.download = filename;

                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                this.showToast(
                    `Expenses exported successfully!\n\nFile: ${filename}\nLocation: Downloads folder\nExpenses: ${exportData.length}`,
                    'success'
                );

                console.log('Export completed successfully using direct download');
                console.log('Filename:', filename);
                console.log('Expense count:', exportData.length);
                return;
            }
        } catch (error) {
            console.warn('Direct download failed, falling back to server-side export:', error);
        }

        // Final fallback to server-side export
        const response = await fetch('/api/expenses/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                expenses: exportData,
                filename: defaultFilename
            })
        });

        const result = await response.json();
        console.log('Export response:', result); // Debug log

        if (!response.ok) {
            throw new Error(result.message || 'Export failed');
        }

        if (result.success) {
            const exportInfo = result.export_info;

            // Show success message with full absolute path
            this.showToast(
                `Expenses exported successfully!\n\nFile saved to:\n${exportInfo.file_path}\n\nFile size: ${this.formatFileSize(exportInfo.file_size)}\nExpenses: ${exportInfo.expense_count}`,
                'success'
            );

            // Also log to console for easy copying
            console.log('Export completed successfully:');
            console.log('Absolute file path:', exportInfo.file_path);
            console.log('Filename:', exportInfo.filename);
            console.log('File size:', this.formatFileSize(exportInfo.file_size));
            console.log('Expense count:', exportInfo.expense_count);
        } else {
            throw new Error(result.message || 'Export failed');
        }
    }

    /**
     * Enhanced export with folder selection and receipt copying
     */
    async exportEnhanced() {
        if (this.expenses.length === 0) {
            this.showToast('No expenses to export', 'error');
            return;
        }

        try {
            this.showLoading('Preparing enhanced export...');

            // Prepare data for export
            const exportData = this.expenses.map(expense => {
                const exportRow = { ...expense };

                // Add receipt information
                const receipts = this.receipts.get(expense.id) || [];
                if (receipts.length > 0) {
                    // Join multiple receipt names with semicolon
                    exportRow.receipt_names = receipts.map(r => r.name).join('; ');
                    // Join multiple receipt file paths with semicolon
                    exportRow.receipt_file_paths = receipts.map(r => r.filePath || 'N/A').join('; ');
                    // Use average confidence or highest confidence
                    exportRow.receipt_confidence = Math.round(
                        receipts.reduce((sum, r) => sum + r.confidence, 0) / receipts.length
                    );
                    exportRow.receipt_count = receipts.length;
                } else {
                    exportRow.receipt_names = '';
                    exportRow.receipt_file_paths = '';
                    exportRow.receipt_confidence = '';
                    exportRow.receipt_count = 0;
                }

                // Remove internal ID
                delete exportRow.id;

                return exportRow;
            });

            const defaultFilename = `ez-expense-export-${new Date().toISOString().split('T')[0]}.csv`;

            // Check if Directory Picker is supported for enhanced workflow
            if ('showDirectoryPicker' in window) {
                await this.exportEnhancedWithDirectoryPicker(exportData, defaultFilename);
            } else {
                await this.exportEnhancedFallback(exportData, defaultFilename);
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                // User cancelled the directory picker
                this.showToast('Export cancelled', 'info');
                return;
            }

            console.error('Enhanced export error:', error);
            this.showToast(`Enhanced export failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Enhanced export using Directory Picker API
     */
    async exportEnhancedWithDirectoryPicker(exportData, defaultFilename) {
        // Show directory picker
        const directoryHandle = await window.showDirectoryPicker();

        // Create timestamped export folder
        const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, '').replace('T', '-');
        const exportFolderName = `ez-expense-${timestamp}`;
        const exportDirectoryHandle = await directoryHandle.getDirectoryHandle(exportFolderName, { create: true });

        // Create receipts subfolder within the export folder
        const receiptsDirectoryHandle = await exportDirectoryHandle.getDirectoryHandle('receipts', { create: true });

        // Generate CSV content
        const response = await fetch('/api/expenses/export/data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                expenses: exportData,
                filename: defaultFilename
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || 'Failed to generate CSV data');
        }

        // Save CSV file in the export folder
        const csvFileHandle = await exportDirectoryHandle.getFileHandle(result.export_data.filename, { create: true });
        const csvWritable = await csvFileHandle.createWritable();
        await csvWritable.write(result.export_data.csv_data);
        await csvWritable.close();

        // Copy receipt files
        let copiedReceipts = 0;
        let failedReceipts = 0;
        const failedReceiptNames = [];
        const copiedReceiptMapping = new Map(); // Track which receipts were successfully copied

        console.log('Starting receipt copying process...');
        console.log('Total expenses:', this.expenses.length);
        console.log('Receipts Map contents:', this.receipts);
        console.log('Receipts Map size:', this.receipts.size);

        // Debug: Log all entries in the receipts map
        for (const [expenseId, receipts] of this.receipts.entries()) {
            console.log(`Receipts Map - Expense ${expenseId}:`, receipts);
        }

        for (const expense of this.expenses) {
            const receipts = this.receipts.get(expense.id) || [];
            console.log(`Expense ${expense.id} has ${receipts.length} receipts:`, receipts);

            for (const receipt of receipts) {
                console.log('Processing receipt:', receipt);
                try {
                    if (receipt.filePath) {
                        // Extract the actual saved filename from the file path
                        const savedFilename = receipt.filePath.split('/').pop() || receipt.filePath.split('\\').pop();
                        console.log('Saved filename:', savedFilename, 'Original name:', receipt.name);

                        // Fetch the receipt file from the server using the actual saved filename
                        const receiptResponse = await fetch(`/api/receipts/download/${encodeURIComponent(savedFilename)}`);
                        console.log('Receipt download response status:', receiptResponse.status);

                        if (receiptResponse.ok) {
                            const receiptBlob = await receiptResponse.blob();
                            console.log('Receipt blob size:', receiptBlob.size);

                            // Save to receipts folder using the original name (not the timestamped name)
                            const receiptFileHandle = await receiptsDirectoryHandle.getFileHandle(receipt.name, { create: true });
                            const receiptWritable = await receiptFileHandle.createWritable();
                            await receiptWritable.write(receiptBlob);
                            await receiptWritable.close();

                            console.log('Successfully copied receipt:', receipt.name);
                            copiedReceipts++;
                            copiedReceiptMapping.set(receipt.name, `receipts/${receipt.name}`);
                        } else {
                            console.error('Failed to download receipt:', savedFilename, 'Status:', receiptResponse.status);
                            failedReceipts++;
                            failedReceiptNames.push(receipt.name);
                        }
                    } else {
                        console.warn('Receipt has no filePath:', receipt);
                    }
                } catch (error) {
                    console.error(`Failed to copy receipt ${receipt.name}:`, error);
                    failedReceipts++;
                    failedReceiptNames.push(receipt.name);
                }
            }
        }

        console.log('Receipt copying completed. Copied:', copiedReceipts, 'Failed:', failedReceipts);

        // Update CSV data to point to the new receipt locations
        const updatedExportData = exportData.map(expense => {
            const updatedExpense = { ...expense };

            // Update receipt_file_paths to point to receipts subfolder
            if (updatedExpense.receipt_names) {
                const receiptNames = updatedExpense.receipt_names.split('; ');
                const updatedPaths = receiptNames.map(name => {
                    return copiedReceiptMapping.get(name.trim()) || 'N/A';
                });
                updatedExpense.receipt_file_paths = updatedPaths.join('; ');
            }

            return updatedExpense;
        });

        // Generate updated CSV content
        const updatedCsvContent = this.convertToCSV(updatedExportData);

        // Overwrite the CSV file with updated content in the export folder
        const updatedCsvFileHandle = await exportDirectoryHandle.getFileHandle(result.export_data.filename, { create: true });
        const updatedCsvWritable = await updatedCsvFileHandle.createWritable();
        await updatedCsvWritable.write(updatedCsvContent);
        await updatedCsvWritable.close();

        this.showToast(
            `Enhanced export completed successfully!\n\n` +
            `📁 Export Folder: ${exportFolderName}\n` +
            `📄 CSV File: ${result.export_data.filename}\n` +
            `📎 Receipts: ${copiedReceipts} copied${failedReceipts > 0 ? `, ${failedReceipts} failed` : ''}\n` +
            `📊 Expenses: ${result.export_data.expense_count}\n\n` +
            `Files saved to your selected folder.`,
            'success'
        );

        console.log('Enhanced export completed successfully');
        console.log('Export folder:', exportFolderName);
        console.log('Receipts copied:', copiedReceipts);
        console.log('Receipts failed:', failedReceipts);
        if (failedReceiptNames.length > 0) {
            console.warn('Failed receipts:', failedReceiptNames);
        }
    }

    /**
     * Enhanced export fallback for browsers without Directory Picker
     */
    async exportEnhancedFallback(exportData, defaultFilename) {
        this.showToast(
            'Enhanced export with folder selection is not supported in this browser.\n\n' +
            'Using enhanced export with ZIP download instead...',
            'info'
        );

        // Create a zip file with CSV and receipts
        if (typeof JSZip === 'undefined') {
            // Fallback to server-side zip creation
            const response = await fetch('/api/expenses/export/zip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expenses: exportData,
                    filename: defaultFilename
                })
            });

            if (response.ok) {
                // Trigger download
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `ez-expense-enhanced-export-${new Date().toISOString().split('T')[0]}.zip`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                this.showToast(
                    `Enhanced export completed!\n\n` +
                    `📦 ZIP File: ${a.download}\n` +
                    `📁 Contains: CSV file + receipts folder\n` +
                    `📊 Expenses: ${exportData.length}\n\n` +
                    `Downloaded to your Downloads folder.`,
                    'success'
                );
            } else {
                throw new Error('Failed to create ZIP export');
            }
        } else {
            // Client-side zip creation (if JSZip is available)
            this.showToast('Client-side ZIP creation not implemented yet. Use Quick Export instead.', 'info');
        }
    }

    /**
     * Format file size in human readable format
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Update export method information based on browser capabilities
     */
    updateExportMethodInfo() {
        const exportMethodInfo = document.getElementById('export-method-info');
        if (!exportMethodInfo) return;

        if ('showDirectoryPicker' in window) {
            exportMethodInfo.innerHTML = `
                <li><i class="fas fa-check-circle" style="color: #28a745;"></i> <strong>Choose destination folder:</strong> Select where to save your organized export</li>
                <li><i class="fas fa-folder" style="color: #17a2b8;"></i> <strong>Timestamped folder:</strong> Creates ez-expense-YYYYMMDD-HHMMSS folder</li>
                <li><i class="fas fa-file-csv" style="color: #28a745;"></i> <strong>Complete package:</strong> CSV file + receipts subfolder with original names</li>
            `;
        } else {
            exportMethodInfo.innerHTML = `
                <li><i class="fas fa-download" style="color: #007bff;"></i> <strong>ZIP download:</strong> Downloads complete package to Downloads folder</li>
                <li><i class="fas fa-info-circle" style="color: #ffc107;"></i> <strong>Folder selection:</strong> Not supported in this browser</li>
                <li><i class="fas fa-file-archive" style="color: #6c757d;"></i> <strong>Fallback mode:</strong> Creates ZIP with CSV + receipts folder</li>
            `;
        }
    }

    /**
     * Convert array of objects to CSV string
     */
    convertToCSV(data) {
        if (data.length === 0) return '';

        const headers = Object.keys(data[0]);
        const csvHeaders = headers.join(',');

        const csvRows = data.map(row => {
            return headers.map(header => {
                const value = row[header] || '';
                // Escape commas and quotes
                return `"${value.toString().replace(/"/g, '""')}"`;
            }).join(',');
        });

        return [csvHeaders, ...csvRows].join('\n');
    }

    /**
     * Update statistics display
     */
    updateStatistics() {
        const totalExpenses = this.expenses.length;

        // Count total receipts across all expenses
        let totalReceipts = 0;
        for (const receipts of this.receipts.values()) {
            totalReceipts += receipts.length;
        }

        const expensesWithReceipts = this.receipts.size;
        const completionRate = totalExpenses > 0 ? Math.round((expensesWithReceipts / totalExpenses) * 100) : 0;

        document.getElementById('total-expenses').textContent = totalExpenses;
        document.getElementById('matched-receipts').textContent = `${totalReceipts} (${expensesWithReceipts} expenses)`;
        document.getElementById('completion-rate').textContent = `${completionRate}%`;

        // Export section is now always visible as part of Step 2
        // No need to show a separate step
    }

    /**
     * Show specific step section
     */
    showStep(step) {
        // With the new structure, we only have 2 steps:
        // Step 1: Import (always visible)
        // Step 2: Review, Edit, and Export (expenses-section)

        if (step >= 2) {
            const expensesSection = document.getElementById('expenses-section');
            if (expensesSection) {
                expensesSection.style.display = 'block';
            }
        }

        this.currentStep = Math.max(this.currentStep, step);
    }

    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const text = document.getElementById('loading-text');
        text.textContent = message;
        overlay.style.display = 'flex';
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = 'none';
    }

    /**
     * Handle receipt drag start
     */
    handleReceiptDragStart(event, expenseId, receiptIndex) {
        const receipt = this.receipts.get(expenseId)[receiptIndex];
        const dragData = {
            receipt: receipt,
            fromExpenseId: expenseId,
            receiptIndex: receiptIndex
        };

        // Set drag data
        event.dataTransfer.setData('application/x-receipt-data', JSON.stringify(dragData));
        event.dataTransfer.effectAllowed = 'move';

        // Add visual feedback to the dragged element
        event.target.classList.add('being-dragged');

        console.log('Starting drag of receipt:', receipt.name, 'from expense:', expenseId);
        console.log('Receipt data:', receipt);
    }

    /**
     * Handle receipt drag end
     */
    handleReceiptDragEnd(event) {
        // Remove visual feedback
        event.target.classList.remove('being-dragged');

        // Remove any remaining drag-over classes
        document.querySelectorAll('.drag-over, .receipt-drag-over, .file-drag-over').forEach(el => {
            el.classList.remove('drag-over', 'receipt-drag-over', 'file-drag-over');
        });
    }

    /**
     * Handle receipt drop onto an expense row
     */
    async handleReceiptDrop(draggedReceipt, targetExpenseId) {
        const { receipt, fromExpenseId, receiptIndex } = draggedReceipt;

        // Don't allow dropping on the same expense
        if (fromExpenseId === targetExpenseId) {
            this.showToast('Cannot move receipt to the same expense', 'warning');
            return;
        }

        console.log('Moving receipt:', receipt.name, 'from expense:', fromExpenseId, 'to expense:', targetExpenseId);
        console.log('Original receipt object:', receipt);

        try {
            this.showLoading('Moving receipt...');

            // Prepare receipt data with proper filename field for API
            const receiptDataForAPI = {
                ...receipt,
                filename: receipt.filename || receipt.name || receipt.originalFilename
            };

            console.log('Receipt data being sent to API:', receiptDataForAPI);

            // Call the backend API to move the receipt
            const response = await fetch('/api/receipts/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    receipt_data: receiptDataForAPI,
                    from_expense_id: fromExpenseId,
                    to_expense_id: targetExpenseId
                })
            });

            const data = await response.json();

            if (data.success) {
                // Update the frontend receipts data
                this.moveReceiptInFrontend(fromExpenseId, receiptIndex, targetExpenseId, receipt);

                // Refresh the table display
                this.displayExpensesTable();

                this.showToast(`Receipt "${receipt.name}" moved successfully`, 'success');
            } else {
                throw new Error(data.message || 'Move failed');
            }

        } catch (error) {
            console.error('Error moving receipt:', error);
            this.showToast(`Failed to move receipt: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Move receipt in frontend data structures
     */
    moveReceiptInFrontend(fromExpenseId, receiptIndex, toExpenseId, receipt) {
        // Remove from source expense
        const sourceReceipts = this.receipts.get(fromExpenseId) || [];
        sourceReceipts.splice(receiptIndex, 1);
        this.receipts.set(fromExpenseId, sourceReceipts);

        // Add to target expense
        const targetReceipts = this.receipts.get(toExpenseId) || [];
        targetReceipts.push(receipt);
        this.receipts.set(toExpenseId, targetReceipts);

        // Update stats
        this.updateStatistics();
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        // Handle multiline messages by replacing \n with <br>
        const formattedMessage = message.replace(/\n/g, '<br>');

        toast.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                <span style="flex: 1; line-height: 1.4; white-space: pre-line;">${formattedMessage}</span>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; cursor: pointer; font-size: 1.2rem; padding: 0; color: inherit; opacity: 0.7;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        container.appendChild(toast);

        // Auto remove after longer time for longer messages
        const autoRemoveTime = message.length > 100 ? 10000 : 5000;
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, autoRemoveTime);
    }

    /**
     * Read file as text
     */
    readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    /**
     * Utility function to create delay
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Global functions for HTML onclick handlers
function closeReceiptModal() {
    document.getElementById('receipt-modal').style.display = 'none';
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new EZExpenseApp();
});
