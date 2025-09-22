/**
 * EZ Expense Frontend Application
 * Handles all client-side functionality for the expense management system
 */

class EZExpenseApp {
    constructor() {
        this.expenses = [];
        this.receipts = new Map(); // Map of expense ID to array of receipt data
        this.selectedExpenses = new Set(); // Track selected expense IDs
        this.deleteConfirmationState = false; // Track if delete button is in confirmation mode
        this.confirmationTimeout = null; // Track timeout for resetting confirmation
        this.currentStep = 1;
        this.validCategories = new Set(); // Valid expense categories
        this.validationEnabled = true; // Enable/disable validation

        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        this.bindEvents();
        this.checkHealthStatus();
        this.updateExportMethodInfo();
        this.createDeleteButton(); // Initialize the delete button
        this.loadValidCategories(); // Load valid expense categories
        this.initModalEventListeners(); // Initialize modal event listeners

        // Debug: Check if column config is loaded
        if (window.COLUMN_CONFIG) {
            console.log('Column config loaded successfully:', window.COLUMN_CONFIG);
        } else {
            console.error('Column config not loaded!');
        }

        console.log('EZ Expense App initialized');
    }

    /**
     * Initialize modal event listeners for closing with Escape key and click outside
     */
    initModalEventListeners() {
        console.log('Initializing modal event listeners...');

        // Global keyboard event listener for Escape key
        document.addEventListener('keydown', (e) => {
            console.log('Key pressed:', e.key);
            if (e.key === 'Escape') {
                console.log('Escape key detected');
                // Don't close modals if user is actively typing in an input field
                const activeElement = document.activeElement;
                const isTyping = activeElement && (
                    activeElement.tagName === 'INPUT' ||
                    activeElement.tagName === 'TEXTAREA' ||
                    activeElement.isContentEditable
                );

                console.log('Is typing:', isTyping, 'Active element:', activeElement?.tagName);

                if (!isTyping) {
                    console.log('Calling closeAllModals from escape key');
                    this.closeAllModals();
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        }, true); // Use capture phase to ensure we get the event first

        // Click outside modal to close (event delegation)
        document.addEventListener('click', (e) => {
            console.log('Click detected on:', e.target.className, e.target.tagName, 'ID:', e.target.id);

            // Check if we have any open modals or tooltips
            const openModals = document.querySelectorAll('.modal[style*="block"], .modal:not([style*="none"])');
            const openTooltips = document.querySelectorAll('#receipt-tooltip, .receipt-tooltip');

            console.log('Open modals found:', openModals.length);
            console.log('Open tooltips found:', openTooltips.length);

            // If no modals or tooltips are open, don't interfere
            if (openModals.length === 0 && openTooltips.length === 0) {
                return;
            }

            // Check if clicked element is a modal backdrop (has class 'modal')
            if (e.target.classList.contains('modal')) {
                console.log('Clicked on modal backdrop, closing all modals');
                this.closeAllModals();
                e.preventDefault();
                e.stopPropagation();
                return;
            }

            // Check if we clicked inside any modal content or tooltip
            let clickedInsideModalOrTooltip = false;

            // Check modals
            for (let modal of openModals) {
                const modalContent = modal.querySelector('.modal-content');
                if (modalContent && modalContent.contains(e.target)) {
                    clickedInsideModalOrTooltip = true;
                    console.log('Clicked inside modal content');
                    break;
                }
            }

            // Check tooltips if we haven't found a modal click
            if (!clickedInsideModalOrTooltip) {
                for (let tooltip of openTooltips) {
                    if (tooltip.contains(e.target)) {
                        clickedInsideModalOrTooltip = true;
                        console.log('Clicked inside tooltip');
                        break;
                    }
                }
            }

            // If we clicked outside all modals and tooltips, close them
            if (!clickedInsideModalOrTooltip) {
                console.log('Clicked outside all modals and tooltips, closing all');
                this.closeAllModals();
                e.preventDefault();
                e.stopPropagation();
            }
        }, true); // Use capture phase to ensure we get the event first

        console.log('Modal event listeners initialized');
    }

    /**
     * Close all open modals and popups
     */
    closeAllModals() {
        console.log('Closing all modals and popups...');

        // Close all elements with class 'modal'
        const allModals = document.querySelectorAll('.modal');
        allModals.forEach(modal => {
            if (modal.style.display !== 'none') {
                console.log('Closing modal:', modal.id || modal.className);
                modal.style.display = 'none';
            }
        });

        // Close receipt modal specifically (in case it's not caught above)
        const receiptModal = document.getElementById('receipt-modal');
        if (receiptModal && receiptModal.style.display !== 'none') {
            console.log('Closing receipt modal specifically');
            receiptModal.style.display = 'none';
        }

        // Hide any tooltips using immediate hide to avoid delays
        this.hideTooltipImmediate();

        console.log('All modals and popups closed.');
    }

    /**
     * Test function to manually close all modals (can be called from console)
     */
    testCloseAllModals() {
        console.log('=== Manual test: closing all modals ===');
        this.closeAllModals();
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
                    width = config.columnWidths['Receipts'] || 280;
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
        // Don't make the receipts column or checkbox column resizable since they're sticky
        if (th.classList.contains('receipts-column') || th.classList.contains('checkbox-column')) {
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
        // Don't make the receipts column or checkbox column draggable since they're sticky
        if (th.classList.contains('receipts-column') || th.classList.contains('checkbox-column')) {
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
     * Initialize column sorting functionality
     */
    initColumnSorting() {
        // Check if sorting is enabled in configuration
        if (!window.COLUMN_CONFIG?.headerConfig?.allowSorting) return;

        const table = document.getElementById('expenses-table');
        if (!table) return;

        // Add click event listeners to all sort icons
        const sortIcons = table.querySelectorAll('.sort-icon');
        sortIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const column = icon.getAttribute('data-column');
                this.sortTable(column);
            });
        });
    }

    /**
     * Sort table by the specified column
     */
    sortTable(columnName) {
        if (!this.expenses || this.expenses.length === 0) return;

        // Get current sort state for this column
        const currentSort = this.sortState || {};
        let sortDirection = 'asc';

        // If already sorting by this column, toggle direction
        if (currentSort.column === columnName) {
            sortDirection = currentSort.direction === 'asc' ? 'desc' : 'asc';
        }

        // Update sort state
        this.sortState = {
            column: columnName,
            direction: sortDirection
        };

        // Sort the expenses array
        this.expenses.sort((a, b) => {
            let valueA = a[columnName] || '';
            let valueB = b[columnName] || '';

            // Detect and handle different data types
            const sortResult = this.compareValues(valueA, valueB, sortDirection);
            return sortResult;
        });

        // Update sort icons
        this.updateSortIcons(columnName, sortDirection);

        // Update expenses data from current table before refreshing display
        this.updateExpensesFromTable();

        // Redisplay the table with sorted data
        this.displayExpensesTable();
    }

    /**
     * Compare two values for sorting, handling different data types
     */
    compareValues(valueA, valueB, direction) {
        // Convert to strings for comparison
        const strA = String(valueA).toLowerCase().trim();
        const strB = String(valueB).toLowerCase().trim();

        // Check if values are numbers
        const numA = parseFloat(strA);
        const numB = parseFloat(strB);
        const isNumberA = !isNaN(numA) && isFinite(numA);
        const isNumberB = !isNaN(numB) && isFinite(numB);

        // Check if values are dates (YYYY-MM-DD format or other date formats)
        const dateA = new Date(strA);
        const dateB = new Date(strB);
        const isDateA = !isNaN(dateA.getTime()) && (strA.includes('-') || strA.includes('/'));
        const isDateB = !isNaN(dateB.getTime()) && (strB.includes('-') || strB.includes('/'));

        let result = 0;

        if (isDateA && isDateB) {
            // Date comparison
            result = dateA.getTime() - dateB.getTime();
        } else if (isNumberA && isNumberB) {
            // Numeric comparison
            result = numA - numB;
        } else {
            // String comparison
            result = strA.localeCompare(strB);
        }

        // Apply sort direction
        return direction === 'desc' ? -result : result;
    }

    /**
     * Update sort icons to show current sort state
     */
    updateSortIcons(activeColumn, direction) {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        // Reset all sort icons
        const allSortIcons = table.querySelectorAll('.sort-icon');
        allSortIcons.forEach(icon => {
            icon.className = 'sort-icon';
            const faIcon = icon.querySelector('i');
            if (faIcon) {
                faIcon.className = 'fas fa-sort';
            }
        });

        // Update the active column's sort icon
        const activeSortIcon = table.querySelector(`.sort-icon[data-column="${activeColumn}"]`);
        if (activeSortIcon) {
            if (direction === 'asc') {
                activeSortIcon.className = 'sort-icon sort-asc';
                const faIcon = activeSortIcon.querySelector('i');
                if (faIcon) {
                    faIcon.className = 'fas fa-sort-up';
                }
            } else {
                activeSortIcon.className = 'sort-icon sort-desc';
                const faIcon = activeSortIcon.querySelector('i');
                if (faIcon) {
                    faIcon.className = 'fas fa-sort-down';
                }
            }
        }
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

        document.getElementById('validate-data-btn').addEventListener('click', () => {
            this.validateAllFields(); // Trigger validation of all fields first
            this.showValidationSummary();
        });

        // Export events
        document.getElementById('export-enhanced-btn').addEventListener('click', () => {
            this.exportEnhanced();
        });

        // Receipts import events
        this.initBulkReceiptsImport();

        // Global drag and drop events
        document.addEventListener('dragover', this.handleDragOver.bind(this));
        document.addEventListener('drop', this.handleDrop.bind(this));

        // Checkbox events (using event delegation for dynamically created checkboxes)
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('row-checkbox')) {
                this.handleRowCheckboxChange(e.target);
            } else if (e.target.id === 'select-all-checkbox') {
                this.handleSelectAllChange(e.target);
            }
        });
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
     * Load valid expense categories from the server
     */
    async loadValidCategories() {
        try {
            const response = await fetch('/api/category-list');
            const data = await response.json();
            if (data.categories) {
                this.validCategories = new Set(data.categories);
                console.log('Loaded', this.validCategories.size, 'valid expense categories');
            }
        } catch (error) {
            console.error('Failed to load category list:', error);
            this.showToast('Warning: Could not load expense category validation list', 'warning');
        }
    }

    /**
     * Extract invoice details from a receipt file
     */
    async extractInvoiceDetails(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/receipts/extract_invoice_details', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                return result.invoice_details;
            } else {
                throw new Error(result.message || 'Failed to extract invoice details');
            }
        } catch (error) {
            console.error('Error extracting invoice details:', error);
            throw error;
        }
    }

    /**
     * Validate date format (YYYY-MM-DD)
     */
    validateDateFormat(dateString) {
        // Handle non-string values
        if (dateString === null || dateString === undefined) {
            return false;
        }

        // Convert to string if not already
        const dateStr = String(dateString).trim();

        if (dateStr === '') {
            return false;
        }

        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(dateStr)) {
            return false;
        }

        // Check if it's a valid date
        const date = new Date(dateStr);
        const [year, month, day] = dateStr.split('-').map(num => parseInt(num, 10));

        return date.getFullYear() === year &&
            date.getMonth() === month - 1 &&
            date.getDate() === day;
    }

    /**
     * Validate expense category against the valid categories list
     */
    validateExpenseCategory(category) {
        // Handle non-string values
        if (category === null || category === undefined) {
            return false;
        }

        // Convert to string if not already
        const categoryStr = String(category).trim();

        if (categoryStr === '') {
            return false; // Empty category is invalid
        }

        // Check exact match first
        if (this.validCategories.has(categoryStr)) {
            return true;
        }

        // Check case-insensitive match
        const lowerCategory = categoryStr.toLowerCase();
        for (const validCategory of this.validCategories) {
            if (validCategory.toLowerCase() === lowerCategory) {
                return true;
            }
        }

        return false;
    }

    /**
     * Validate that a value is numeric (not empty and is a valid number)
     */
    validateAmount(value) {
        // Handle null/undefined values
        if (value === null || value === undefined) {
            return false;
        }

        // Convert to string and trim
        const valueStr = String(value).trim();

        // Empty string is invalid
        if (valueStr === '') {
            return false;
        }

        // Check if it's a valid number
        const num = parseFloat(valueStr);
        return !isNaN(num) && isFinite(num);
    }

    /**
     * Validate that a value is not empty
     */
    validateNotEmpty(value) {
        // Handle null/undefined values
        if (value === null || value === undefined) {
            return false;
        }

        // Convert to string and trim
        const valueStr = String(value).trim();

        // Check if it's not empty
        return valueStr !== '';
    }

    /**
     * Validate an input field and apply visual feedback
     */
    validateField(input, columnName, value) {
        if (!this.validationEnabled || !input || !columnName) {
            return true;
        }

        // Skip validation for uneditable fields
        if (input.readOnly || input.classList.contains('non-editable')) {
            // Remove any existing validation classes from uneditable fields
            input.classList.remove('validation-error');
            const cell = input.closest('td');
            if (cell) {
                cell.classList.remove('validation-valid', 'validation-invalid');
            }
            return true;
        }

        let isValid = true;
        let hasValidation = false; // Track if this column has validation rules
        const normalizedColumnName = String(columnName).toLowerCase().trim();

        // Convert value to string and handle null/undefined
        let trimmedValue = '';
        if (value !== null && value !== undefined) {
            trimmedValue = String(value).trim();
        }

        // Check for Date column (multiple possible variations)
        if (normalizedColumnName.includes('date') ||
            normalizedColumnName === 'expense date' ||
            normalizedColumnName === 'transaction date' ||
            normalizedColumnName === 'purchase date') {
            hasValidation = true;
            isValid = this.validateDateFormat(value);
        }
        // Check for Expense category column (multiple possible variations)
        else if (normalizedColumnName.includes('category') ||
            normalizedColumnName === 'expense category' ||
            normalizedColumnName === 'expense type' ||
            normalizedColumnName.includes('expense category')) {
            hasValidation = true;
            isValid = this.validateExpenseCategory(value);
        }
        // Check for Amount column (multiple possible variations)
        else if (normalizedColumnName === 'amount') {
            hasValidation = true;
            isValid = this.validateAmount(value);
        }
        // Check for Merchant column (multiple possible variations)
        else if (normalizedColumnName === 'merchant') {
            hasValidation = true;
            isValid = this.validateNotEmpty(value);
        }
        // Check for Additional information column (multiple possible variations)
        else if (normalizedColumnName === 'additional information') {
            hasValidation = true;
            isValid = this.validateNotEmpty(value);
        }

        // Apply visual feedback to both input and cell - only for columns with validation
        const cell = input.closest('td');
        if (hasValidation) {
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
        } else {
            // For columns without validation, remove any existing validation classes
            input.classList.remove('validation-error');
            if (cell) {
                cell.classList.remove('validation-valid', 'validation-invalid');
            }
        }

        // Check if this is a "Receipts attached" column and update receipt validation
        if (normalizedColumnName.includes('receipts') && normalizedColumnName.includes('attached')) {
            // Find the expense ID from the table row
            const row = input.closest('tr');
            if (row && row.dataset.expenseId) {
                const expenseId = parseInt(row.dataset.expenseId);
                // Update the receipt validation indicator for this expense
                setTimeout(() => {
                    this.updateReceiptValidationIndicator(expenseId);
                }, 0);
            }
        }

        return isValid;
    }

    /**
     * Validate receipt attachment status
     * Checks if "Receipts attached" column matches actual receipts in "Receipts" column
     */
    validateReceiptAttachment(expenseId, receiptsAttachedValue) {
        if (!this.validationEnabled) {
            return true;
        }

        // Get the actual receipts for this expense
        const actualReceipts = this.receipts.get(expenseId) || [];
        const hasActualReceipts = actualReceipts.length > 0;

        // Normalize the receipts attached value
        let receiptsAttachedNormalized = '';
        if (receiptsAttachedValue !== null && receiptsAttachedValue !== undefined) {
            receiptsAttachedNormalized = String(receiptsAttachedValue).toLowerCase().trim();
        }

        // Check if the status matches reality
        const shouldHaveReceipts = receiptsAttachedNormalized === 'yes' || receiptsAttachedNormalized === 'true' || receiptsAttachedNormalized === '1';
        const shouldNotHaveReceipts = receiptsAttachedNormalized === 'no' || receiptsAttachedNormalized === 'false' || receiptsAttachedNormalized === '0';

        // Updated validation logic:
        // - if Receipts attached is Yes, and there's nothing in the Receipts column, pass
        // - if Receipts attached is Yes, and there's receipt in the Receipts column, fail
        // - if Receipts attached is No, and there's nothing in the Receipts column, fail
        // - if Receipts attached is No, and there's receipt in the Receipts column, pass
        let isValid = false;

        if (shouldHaveReceipts) {
            // "Receipts attached" is "Yes"
            isValid = !hasActualReceipts; // Pass only if no actual receipts
        } else if (shouldNotHaveReceipts) {
            // "Receipts attached" is "No"
            isValid = hasActualReceipts; // Pass only if has actual receipts
        } else {
            // Unknown/empty value - default to valid to avoid false negatives
            isValid = true;
        }

        return isValid;
    }

    /**
     * Update receipt validation indicator for a specific expense
     */
    updateReceiptValidationIndicator(expenseId) {
        // Find the expense to get the "Receipts attached" value
        const expense = this.expenses.find(e => e.id === expenseId);
        if (!expense) return;

        // Find the "Receipts attached" column value (case-insensitive search)
        let receiptsAttachedValue = null;
        for (const [key, value] of Object.entries(expense)) {
            const normalizedKey = key.toLowerCase().trim();
            if (normalizedKey.includes('receipts') && normalizedKey.includes('attached')) {
                receiptsAttachedValue = value;
                break;
            }
        }

        // If no "Receipts attached" column found, don't show validation
        if (receiptsAttachedValue === null) return;

        const isValid = this.validateReceiptAttachment(expenseId, receiptsAttachedValue);

        // Find and update the receipt cell
        const receiptCell = document.querySelector(`[data-expense-id="${expenseId}"].receipt-cell`);
        if (receiptCell) {
            // Remove existing validation indicator (if any)
            const existingIndicator = receiptCell.querySelector('.receipt-validation-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }

            // Remove existing validation classes
            receiptCell.classList.remove('validation-valid', 'validation-invalid');

            // Add appropriate validation class for background highlighting
            receiptCell.classList.add(isValid ? 'validation-valid' : 'validation-invalid');

            // Update the title for accessibility
            receiptCell.title = isValid ?
                'Receipt attachment status matches actual receipts' :
                'Receipt attachment status does not match actual receipts';
        }
    }

    /**
     * Update receipt validation indicators for all expenses
     */
    updateAllReceiptValidationIndicators() {
        this.expenses.forEach(expense => {
            this.updateReceiptValidationIndicator(expense.id);
        });
    }

    /**
     * Validate all visible fields in the table
     */
    validateAllFields() {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        const inputs = table.querySelectorAll('input[type="text"], textarea, select');
        let allValid = true;

        inputs.forEach(input => {
            const columnName = input.dataset.column || '';
            const value = input.value;
            const isValid = this.validateField(input, columnName, value);
            if (!isValid) {
                allValid = false;
            }
        });

        return allValid;
    }

    /**
     * Show validation summary to user
     */
    showValidationSummary() {
        const table = document.getElementById('expenses-table');
        if (!table) return;

        const errorFields = table.querySelectorAll('.validation-error');

        // Count receipt validation errors
        let receiptValidationErrors = 0;
        const receiptErrorExpenses = [];

        this.expenses.forEach(expense => {
            // Find the "Receipts attached" column value
            let receiptsAttachedValue = null;
            for (const [key, value] of Object.entries(expense)) {
                const normalizedKey = key.toLowerCase().trim();
                if (normalizedKey.includes('receipts') && normalizedKey.includes('attached')) {
                    receiptsAttachedValue = value;
                    break;
                }
            }

            // Only validate if there's a "Receipts attached" column
            if (receiptsAttachedValue !== null) {
                const isValid = this.validateReceiptAttachment(expense.id, receiptsAttachedValue);
                if (!isValid) {
                    receiptValidationErrors++;
                    receiptErrorExpenses.push(expense.id);
                }
            }
        });

        const totalErrors = errorFields.length + receiptValidationErrors;

        if (totalErrors === 0) {
            this.showToast('All fields are valid! ✓', 'success');
            return;
        }

        const errorTypes = new Set();

        // Check field validation errors
        errorFields.forEach(field => {
            const columnName = field.dataset.column || '';
            if (columnName.toLowerCase().includes('date')) {
                errorTypes.add('Date fields must be in YYYY-MM-DD format');
            } else if (columnName.toLowerCase().includes('category')) {
                errorTypes.add('Expense categories must be from the approved list');
            }
        });

        // Add receipt validation errors if any
        if (receiptValidationErrors > 0) {
            errorTypes.add('Receipt attachment status does not match actual receipts');
        }

        let errorMessage = `Found ${totalErrors} validation error(s):\n\n` +
            Array.from(errorTypes).join('\n');

        if (errorFields.length > 0) {
            errorMessage += '\n\nFields with errors are highlighted in red.';
        }

        if (receiptValidationErrors > 0) {
            errorMessage += '\n\nReceipt validation errors are highlighted in red in the Receipts column.';
        }

        this.showToast(errorMessage, 'warning');
    }

    /**
     * Handle individual row checkbox change
     */
    handleRowCheckboxChange(checkbox) {
        const expenseId = checkbox.dataset.expenseId;
        console.log('Row checkbox changed:', expenseId, 'checked:', checkbox.checked);

        if (checkbox.checked) {
            this.selectedExpenses.add(expenseId);
        } else {
            this.selectedExpenses.delete(expenseId);
        }

        console.log('Selected expenses after change:', Array.from(this.selectedExpenses));

        // Reset confirmation mode when selection changes
        if (this.deleteConfirmationState) {
            this.resetDeleteConfirmationMode();
        }

        this.updateSelectAllCheckbox();
        this.updateDeleteButton();
    }

    /**
     * Handle select all checkbox change
     */
    handleSelectAllChange(selectAllCheckbox) {
        console.log('Select all checkbox changed:', selectAllCheckbox.checked);

        const rowCheckboxes = document.querySelectorAll('.row-checkbox');
        console.log('Found row checkboxes:', rowCheckboxes.length);

        rowCheckboxes.forEach(checkbox => {
            const expenseId = checkbox.dataset.expenseId;
            checkbox.checked = selectAllCheckbox.checked;

            if (selectAllCheckbox.checked) {
                this.selectedExpenses.add(expenseId);
            } else {
                this.selectedExpenses.delete(expenseId);
            }
        });

        console.log('Selected expenses after select all:', this.selectedExpenses.size);

        // Reset confirmation mode when selection changes
        if (this.deleteConfirmationState) {
            this.resetDeleteConfirmationMode();
        }

        this.updateDeleteButton();
    }

    /**
     * Update the select all checkbox state based on individual checkboxes
     */
    updateSelectAllCheckbox() {
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        const rowCheckboxes = document.querySelectorAll('.row-checkbox');

        if (!selectAllCheckbox || rowCheckboxes.length === 0) return;

        const checkedCount = Array.from(rowCheckboxes).filter(cb => cb.checked).length;

        if (checkedCount === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (checkedCount === rowCheckboxes.length) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        }
    }

    /**
     * Update the delete button visibility and text
     */
    updateDeleteButton() {
        let deleteButton = document.getElementById('delete-selected-btn');

        if (this.selectedExpenses.size === 0) {
            if (deleteButton) {
                deleteButton.style.display = 'none';
            }
            // Reset confirmation state when no items selected
            if (this.deleteConfirmationState) {
                this.deleteConfirmationState = false;
                if (this.confirmationTimeout) {
                    clearTimeout(this.confirmationTimeout);
                    this.confirmationTimeout = null;
                }
            }
        } else {
            if (!deleteButton) {
                this.createDeleteButton();
                deleteButton = document.getElementById('delete-selected-btn');
            }

            deleteButton.style.display = 'block';

            // Always update button text to current selection count
            if (this.deleteConfirmationState) {
                // Confirmation mode
                const count = this.selectedExpenses.size;
                deleteButton.innerHTML = `
                    <i class="fas fa-exclamation-triangle"></i>
                    Click Again to Confirm (${count})
                `;
                deleteButton.classList.add('delete-confirmation-mode');
            } else {
                // Normal delete button state
                deleteButton.innerHTML = `
                    <i class="fas fa-trash"></i>
                    Delete Selected (${this.selectedExpenses.size})
                `;
                deleteButton.classList.remove('delete-confirmation-mode');
            }
        }
    }

    /**
     * Create the floating delete button
     */
    createDeleteButton() {
        const deleteButton = document.createElement('button');
        deleteButton.id = 'delete-selected-btn';
        deleteButton.className = 'btn btn-danger delete-selected-btn';
        deleteButton.style.display = 'none';

        deleteButton.addEventListener('click', () => {
            this.confirmDeleteSelected();
        });

        document.body.appendChild(deleteButton);
    }

    /**
     * Handle delete button confirmation flow
     */
    confirmDeleteSelected() {
        if (!this.deleteConfirmationState) {
            // First click - enter confirmation mode
            this.enterDeleteConfirmationMode();
        } else {
            // Second click - proceed with deletion
            this.deleteSelectedExpenses();
        }
    }

    /**
     * Enter delete confirmation mode
     */
    enterDeleteConfirmationMode() {
        this.deleteConfirmationState = true;

        // Update button text and styling
        const deleteButton = document.getElementById('delete-selected-btn');
        if (deleteButton) {
            const count = this.selectedExpenses.size;
            deleteButton.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                Click Again to Confirm (${count})
            `;
            deleteButton.classList.add('delete-confirmation-mode');
        }

        // Reset confirmation mode after 5 seconds
        if (this.confirmationTimeout) {
            clearTimeout(this.confirmationTimeout);
        }

        this.confirmationTimeout = setTimeout(() => {
            this.resetDeleteConfirmationMode();
        }, 5000);
    }

    /**
     * Reset delete confirmation mode
     */
    resetDeleteConfirmationMode() {
        this.deleteConfirmationState = false;

        if (this.confirmationTimeout) {
            clearTimeout(this.confirmationTimeout);
            this.confirmationTimeout = null;
        }

        // Update button back to normal state
        const deleteButton = document.getElementById('delete-selected-btn');
        if (deleteButton) {
            deleteButton.classList.remove('delete-confirmation-mode');
            if (this.selectedExpenses.size > 0) {
                deleteButton.innerHTML = `
                    <i class="fas fa-trash"></i>
                    Delete Selected (${this.selectedExpenses.size})
                `;
            }
        }
    }

    /**
     * Delete the selected expenses
     */
    async deleteSelectedExpenses() {
        try {
            this.showLoading('Deleting selected expenses...');

            // Update expenses data from current table before deleting
            this.updateExpensesFromTable();

            const expenseIds = Array.from(this.selectedExpenses);

            console.log('Selected expense IDs to delete:', expenseIds);
            console.log('Current expenses:', this.expenses.map(e => ({ id: e.id, type: typeof e.id })));

            const response = await fetch('/api/expenses/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ expense_ids: expenseIds })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to delete expenses');
            }

            // Remove deleted expenses from local state
            console.log('Expenses before filtering:', this.expenses.length);
            console.log('Selected expenses set:', Array.from(this.selectedExpenses));

            // Debug the filtering process
            const expensesToKeep = [];
            const expensesToDelete = [];

            this.expenses.forEach(expense => {
                const expenseIdString = String(expense.id);
                const shouldDelete = this.selectedExpenses.has(expenseIdString);
                console.log(`Expense ID: ${expense.id} (${typeof expense.id}) -> String: ${expenseIdString} -> Should delete: ${shouldDelete}`);

                if (shouldDelete) {
                    expensesToDelete.push(expense);
                } else {
                    expensesToKeep.push(expense);
                }
            });

            console.log('Expenses to delete:', expensesToDelete.length);
            console.log('Expenses to keep:', expensesToKeep.length);

            this.expenses = expensesToKeep;
            console.log('Expenses after filtering:', this.expenses.length);

            // Clear selected expenses
            this.selectedExpenses.clear();

            // Reset confirmation state
            this.resetDeleteConfirmationMode();

            // Update the table
            console.log('About to call displayExpensesTable...');
            this.displayExpensesTable();
            console.log('displayExpensesTable completed');

            // Hide delete button
            this.updateDeleteButton();

            this.showToast(`Successfully deleted ${expenseIds.length} expense${expenseIds.length > 1 ? 's' : ''}`, 'success');

        } catch (error) {
            console.error('Error deleting expenses:', error);
            this.showToast(`Error deleting expenses: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
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
     * Sort columns according to the expected priority order from the backend
     */
    sortColumnsByPriority(columns) {
        // Define the expected column priority order (matching expense_importer.py)
        const priorityOrder = [
            'Additional information',
            'Amount',
            'Currency',
            'Date',
            'Expense category',
            'Merchant',
            'Receipts attached',
            'Payment method',
            'Created ID'
        ];

        const prioritized = [];
        const remaining = [];

        // First, add columns in priority order if they exist
        priorityOrder.forEach(priorityCol => {
            if (columns.includes(priorityCol)) {
                prioritized.push(priorityCol);
            }
        });

        // Then add any remaining columns that weren't in the priority list
        columns.forEach(col => {
            if (!priorityOrder.includes(col)) {
                remaining.push(col);
            }
        });

        return [...prioritized, ...remaining];
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
     * Detect receipt-related columns in expense data
     * Returns object with receiptColumns array and hasReceiptData boolean
     */
    detectReceiptColumns(allKeys) {
        const receiptColumns = [];

        allKeys.forEach(key => {
            const normalizedKey = key.toLowerCase();
            // Only detect columns that are exactly "receipts" (case-insensitive)
            if (normalizedKey === 'receipts') {
                receiptColumns.push(key);
            }
        });

        return {
            receiptColumns,
            hasReceiptData: receiptColumns.length > 0
        };
    }

    /**
     * Extract receipt data from expense for a given receipt column
     */
    extractReceiptData(expense, receiptColumn) {
        const value = expense[receiptColumn];
        if (!value || value === '' || value === 'N/A') {
            return null;
        }

        // If it looks like file paths (contains extensions or semicolons)
        if (typeof value === 'string' && (value.includes('.') || value.includes(';'))) {
            return value.split(';').map(path => path.trim()).filter(path => path && path !== 'N/A');
        }

        // Otherwise return as-is for display
        return value;
    }

    /**
     * Display expenses in the table
     */
    displayExpensesTable() {
        console.log('displayExpensesTable called with', this.expenses.length, 'expenses');

        const tableHeader = document.getElementById('table-header');
        const tableBody = document.getElementById('table-body');
        const noExpensesMessage = document.getElementById('no-expenses-message');
        const bulkReceiptsSection = document.getElementById('bulk-receipts-section');

        // Clear existing content
        tableHeader.innerHTML = '';
        tableBody.innerHTML = '';

        if (this.expenses.length === 0) {
            console.log('No expenses to display, showing empty state');
            // Show no expenses message and hide bulk receipts section
            if (noExpensesMessage) noExpensesMessage.style.display = 'block';
            if (bulkReceiptsSection) bulkReceiptsSection.style.display = 'none';

            // Hide the table container
            const tableContainer = document.querySelector('.table-container');
            if (tableContainer) tableContainer.style.display = 'none';

            this.updateStatistics();
            return;
        }

        // Hide no expenses message and show bulk receipts section when we have expenses
        if (noExpensesMessage) noExpensesMessage.style.display = 'none';
        if (bulkReceiptsSection) {
            bulkReceiptsSection.style.display = 'block';
            // Initialize the bulk receipt action buttons
            this.updateBulkReceiptActions();
        }

        // Show the table container
        const tableContainer = document.querySelector('.table-container');
        if (tableContainer) tableContainer.style.display = 'block';

        // Get all unique keys from expenses
        const allKeys = [];
        const keySet = new Set();

        // Collect all unique keys from all expenses
        this.expenses.forEach(expense => {
            Object.keys(expense).forEach(key => {
                if (key !== 'id' && !keySet.has(key)) {
                    allKeys.push(key);
                    keySet.add(key);
                }
            });
        });

        // Sort columns according to priority order
        const sortedKeys = this.sortColumnsByPriority(allKeys);
        console.log('Final sorted column order:', sortedKeys);        // Detect receipt-related columns
        const receiptDetection = this.detectReceiptColumns(sortedKeys);
        console.log('Receipt detection result:', receiptDetection);

        // Filter out receipt-related columns from regular display
        const regularKeys = sortedKeys.filter(key =>
            !receiptDetection.receiptColumns.includes(key)
        );

        // Store receipt data for later use in createReceiptCell
        this.extractedReceiptData = new Map();
        if (receiptDetection.hasReceiptData) {
            this.expenses.forEach(expense => {
                const receiptData = {};
                receiptDetection.receiptColumns.forEach(column => {
                    const data = this.extractReceiptData(expense, column);
                    if (data !== null) {
                        receiptData[column] = data;
                    }
                });
                if (Object.keys(receiptData).length > 0) {
                    this.extractedReceiptData.set(expense.id, receiptData);
                }
            });
        }

        // Create header row
        const headerRow = document.createElement('tr');

        // Add checkbox column header
        const checkboxTh = document.createElement('th');
        checkboxTh.className = 'checkbox-column';
        checkboxTh.innerHTML = `
            <input type="checkbox" id="select-all-checkbox" class="select-all-checkbox" title="Select All">
        `;

        // Add direct event handler for select-all checkbox to prevent conflicts
        const selectAllCheckbox = checkboxTh.querySelector('#select-all-checkbox');
        selectAllCheckbox.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent column reordering/sorting conflicts
            console.log('Select all checkbox clicked directly');
        });

        headerRow.appendChild(checkboxTh);

        // Add regular columns
        regularKeys.forEach(key => {
            const th = document.createElement('th');

            // Get display name from configuration, fallback to original key
            const displayName = window.COLUMN_CONFIG?.getDisplayName ?
                window.COLUMN_CONFIG.getDisplayName(key) : key;

            // Check if sorting is enabled in configuration
            const sortingEnabled = window.COLUMN_CONFIG?.headerConfig?.allowSorting;

            if (sortingEnabled) {
                th.innerHTML = `
                    <div class="column-header">
                        <span class="column-text">${displayName}</span>
                        <span class="sort-icon" data-column="${key}">
                            <i class="fas fa-sort"></i>
                        </span>
                    </div>
                `;
            } else {
                th.textContent = displayName;
            }

            th.title = displayName; // Add tooltip with display name
            headerRow.appendChild(th);
        });

        // Add receipts column (always shown for interactivity, but enhanced with data if available)
        const receiptTh = document.createElement('th');
        receiptTh.textContent = receiptDetection.hasReceiptData ? 'Receipts & Attachments' : 'Receipts';
        receiptTh.title = receiptDetection.hasReceiptData ? 'Receipt data and file uploads' : 'Upload receipts';
        receiptTh.className = 'receipts-column';
        headerRow.appendChild(receiptTh);

        tableHeader.appendChild(headerRow);

        // Create data rows
        this.expenses.forEach((expense, index) => {
            const row = document.createElement('tr');
            row.dataset.expenseId = expense.id;
            row.dataset.rowIndex = index;

            // Add checkbox column
            const checkboxTd = document.createElement('td');
            checkboxTd.className = 'checkbox-column';
            checkboxTd.innerHTML = `
                <input type="checkbox" class="row-checkbox" data-expense-id="${expense.id}">
            `;
            row.appendChild(checkboxTd);

            // Add regular columns
            regularKeys.forEach(key => {
                const td = document.createElement('td');
                // Keep raw values as-is (especially for dates in YYYY-MM-DD format)
                const rawValue = expense[key] || '';
                const textarea = document.createElement('textarea');
                textarea.setAttribute('data-field', key);
                textarea.setAttribute('data-column', key);
                textarea.className = 'table-input';
                textarea.rows = 1;
                textarea.value = rawValue;

                // Check if this column is editable
                let isEditable = !window.COLUMN_CONFIG ||
                    !window.COLUMN_CONFIG.editableColumns ||
                    window.COLUMN_CONFIG.editableColumns.includes(key);

                // Additional check: if Payment method is CC_Amex, make specific columns uneditable
                const paymentMethod = expense['Payment method'] || '';
                if (paymentMethod === 'CC_Amex') {
                    const uneditableForAmex = ['Amount', 'Date', 'Expense category', 'Merchant'];
                    if (uneditableForAmex.includes(key)) {
                        isEditable = false;
                    }
                }

                if (!isEditable) {
                    textarea.className += ' non-editable';
                    textarea.readOnly = true;
                    textarea.tabIndex = -1; // Remove from tab order
                } else {
                    // Add validation on input only for editable columns
                    textarea.addEventListener('input', (e) => {
                        this.validateField(e.target, key, e.target.value);
                    });

                    // Add validation on blur only for editable columns
                    textarea.addEventListener('blur', (e) => {
                        this.validateField(e.target, key, e.target.value);
                    });

                    // Initial validation only for editable columns
                    this.validateField(textarea, key, rawValue);
                }

                td.appendChild(textarea);
                row.appendChild(td);
            });

            // Add receipts column (sticky on the right)
            const receiptTd = document.createElement('td');
            receiptTd.className = 'receipt-cell receipts-column';
            receiptTd.dataset.expenseId = expense.id;
            console.log(`Creating receipt cell for expense ${expense.id}`);
            const receiptCellHTML = this.createReceiptCell(expense.id);
            console.log(`Receipt cell HTML for ${expense.id}:`, receiptCellHTML);
            receiptTd.innerHTML = receiptCellHTML;
            row.appendChild(receiptTd);

            // Make row droppable for receipts
            this.makeRowDroppable(row);
            tableBody.appendChild(row);
        });

        // Apply column widths after table is created
        const allColumnNames = ['Select', ...regularKeys, 'Receipts'];
        const tableElement = document.getElementById('expenses-table');
        this.applyColumnWidths(tableElement, allColumnNames);

        // Initialize column resizing functionality
        this.initColumnResizing();

        // Initialize column reordering functionality
        this.initColumnReordering();

        // Initialize column sorting functionality
        this.initColumnSorting();

        this.updateStatistics();

        // Update receipt validation indicators
        this.updateAllReceiptValidationIndicators();

        // Validate all fields for date and category validation
        this.validateAllFields();

        // Dispatch event to notify autocomplete that table has been created
        document.dispatchEvent(new CustomEvent('expensesTableCreated'));
    }    /**
     * Create receipt cell HTML
     */
    createReceiptCell(expenseId) {
        const receipts = this.receipts.get(expenseId) || [];
        console.log(`createReceiptCell called for expense ${expenseId}, receipts:`, receipts);

        // Get extracted receipt data from original expense columns (for potential future use)
        const extractedData = this.extractedReceiptData?.get(expenseId) || {};

        let html = '';

        // Display existing receipts
        if (receipts.length > 0) {
            console.log(`Creating HTML for ${receipts.length} receipts`);
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
                        <button onclick="app.removeReceipt(${expenseId}, ${index})" class="btn btn-sm">
                            <i class="fas fa-trash"></i>
                        </button>
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
                            <div class="receipt-confidence${receipt.confidence !== null && receipt.confidence !== undefined ? '' : ' undefined'}">Match: ${receipt.confidence !== null && receipt.confidence !== undefined ? receipt.confidence + '%' : 'UNDEFINED'}</div>
                        </div>
                        ${receipt.invoiceDetails ? `
                        <div class="invoice-details">
                            <div class="invoice-details-content">
                                <div class="detail-item detail-amount">${receipt.invoiceDetails.Amount}${receipt.invoiceDetails.Currency ? ` ${receipt.invoiceDetails.Currency}` : ''}</div>
                                <div class="detail-item detail-date">${receipt.invoiceDetails.Date}</div>
                            </div>
                        </div>
                        ` : ''}
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
     * Collect current table data and update the expenses array
     */
    updateExpensesFromTable() {
        console.log('Updating expenses from current table data...');

        const tableBody = document.getElementById('table-body');
        if (!tableBody) {
            console.warn('Table body not found');
            return;
        }

        const rows = tableBody.querySelectorAll('tr[data-expense-id]');

        rows.forEach(row => {
            const expenseId = parseInt(row.dataset.expenseId);
            const expense = this.expenses.find(e => e.id === expenseId);

            if (!expense) {
                console.warn(`Expense with ID ${expenseId} not found`);
                return;
            }

            // Get all textarea inputs in this row
            const textareas = row.querySelectorAll('textarea.table-input[data-field]');

            textareas.forEach(textarea => {
                const fieldName = textarea.dataset.field;
                const currentValue = textarea.value.trim();

                // Update the expense data with current table value
                expense[fieldName] = currentValue;
            });
        });

        console.log('Expenses updated from table data');
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
        const filesToProcess = [];
        const duplicateFiles = [];

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

        this.showLoading(`Checking for duplicates in ${validFiles.length} receipts...`);

        try {
            // Check each file for duplicates and remove them first
            let totalRemovedCount = 0;
            const allRemovedFiles = [];

            for (const file of validFiles) {
                const duplicates = this.findAllDuplicates(file.name);

                if (duplicates.length > 0) {
                    const { removedCount, removedFiles } = this.removeDuplicates(duplicates);
                    totalRemovedCount += removedCount;
                    allRemovedFiles.push(...removedFiles);
                    duplicateFiles.push(file.name);
                }

                filesToProcess.push(file); // Always process the current file, even if we removed its duplicates
            }

            // Show notification about removed duplicates
            if (totalRemovedCount > 0) {
                this.showDuplicateNotification(
                    `Removed ${totalRemovedCount} duplicate file(s) (${allRemovedFiles.join(', ')}) and proceeding with upload to expense table.`,
                    'info'
                );

                // Update displays after removing duplicates
                this.updateBulkReceiptCell();
                this.displayExpensesTable();
            }

            this.showLoading(`Processing ${filesToProcess.length} receipts...`);

            // Use bulk upload endpoint for multiple files
            const formData = new FormData();

            // Add all files to process
            filesToProcess.forEach(file => {
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
                        const originalFile = filesToProcess.find(f => f.name === result.file_info.original_filename);

                        if (originalFile) {
                            // Create preview
                            let preview = '';
                            let type = 'pdf';
                            let confidence = null; // Initialize confidence as null

                            if (originalFile.type.startsWith('image/')) {
                                preview = await this.createImagePreview(originalFile);
                                type = 'image';
                            } else if (originalFile.type === 'application/pdf') {
                                preview = await this.createPDFPreview(originalFile);
                                type = 'pdf';
                            }

                            // Calculate match confidence if possible
                            try {
                                if (expense) {
                                    // Create receipt object in the same format as bulk receipts
                                    const receiptData = {
                                        name: result.file_info.original_filename,
                                        file_path: result.file_info.file_path,
                                        type: type,
                                        confidence: null // Will be updated by the endpoint
                                    };


                                    const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json'
                                        },
                                        body: JSON.stringify({
                                            receipt_data: receiptData,
                                            receipt_path: result.file_info.file_path,
                                            expense_data: expense
                                        })
                                    });

                                    if (matchResponse.ok) {
                                        const matchData = await matchResponse.json();
                                        if (matchData.success) {
                                            confidence = matchData.confidence_score;
                                            if (confidence !== null && confidence !== undefined) {
                                                if (confidence <= 1) {
                                                    confidence *= 100;
                                                }
                                                confidence = Math.round(confidence);
                                            }
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

            // Update expenses data from current table before refreshing display
            this.updateExpensesFromTable();

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

        this.showLoading('Checking for duplicates...');

        try {
            // Check for duplicates across both areas
            const duplicates = this.findAllDuplicates(file.name);

            if (duplicates.length > 0) {
                // Remove all existing duplicates
                const { removedCount, removedFiles } = this.removeDuplicates(duplicates);

                if (removedCount > 0) {
                    this.showDuplicateNotification(
                        `Removed ${removedCount} duplicate file(s) (${removedFiles.join(', ')}) and proceeding with upload to expense table.`,
                        'info'
                    );

                    // Update displays after removing duplicates
                    this.updateBulkReceiptCell();
                    this.displayExpensesTable();
                }
            }

            this.showLoading('Processing receipt...');

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

            // Update expenses data from current table before refreshing display
            this.updateExpensesFromTable();

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

            // Create receipt object in the same format as bulk receipts
            const receiptData = {
                name: uploadData.file_info.original_filename,
                file_path: uploadData.file_info.file_path,
                type: file.type.startsWith('image/') ? 'image' : 'pdf',
            };

            // Call the match-receipt endpoint
            const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    receipt_data: receiptData,
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
                if (confidence !== null && confidence !== undefined) {
                    if (confidence <= 1) {
                        confidence *= 100;
                    }
                    confidence = Math.round(confidence);
                } else {
                    confidence = null;
                }
                return {
                    confidence: confidence,
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
                    confidence: null, // Default confidence
                    filePath: uploadData.file_info.file_path,
                    savedFilename: uploadData.file_info.saved_filename,
                    originalFilename: uploadData.file_info.original_filename
                };
            }

            // Complete fallback if upload also failed
            return {
                confidence: null,
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

        // Update expenses data from current table before refreshing display
        this.updateExpensesFromTable();

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
        this.closeAllModals();
    }

    /**
     * Show tooltip with larger image preview
     */
    showTooltip(event, imageSrc, type, fileName = '') {
        // Immediately remove any existing tooltip without delay to prevent multiple tooltips
        this.hideTooltipImmediate();

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

            // Clear any existing timeout to prevent conflicts
            if (this.tooltipTimeout) {
                clearTimeout(this.tooltipTimeout);
            }

            this.tooltipTimeout = setTimeout(() => {
                if (tooltip.parentNode) {
                    tooltip.parentNode.removeChild(tooltip);
                }
                this.tooltipTimeout = null;
            }, 200);
        }
    }

    /**
     * Immediately hide tooltip without delay (used when showing new tooltip)
     */
    hideTooltipImmediate() {
        // Clear any pending timeout
        if (this.tooltipTimeout) {
            clearTimeout(this.tooltipTimeout);
            this.tooltipTimeout = null;
        }

        // Remove any existing tooltips immediately
        const existingTooltips = document.querySelectorAll('#receipt-tooltip, .receipt-tooltip');
        existingTooltips.forEach(tooltip => {
            if (tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
            }
        });
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
            // Update expenses data from current table before exporting
            this.updateExpensesFromTable();

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
                    // Use average confidence or highest confidence, excluding null values
                    const validConfidences = receipts.filter(r => r.confidence !== null && r.confidence !== undefined).map(r => r.confidence);
                    if (validConfidences.length > 0) {
                        exportRow.receipt_confidence = Math.round(
                            validConfidences.reduce((sum, c) => sum + c, 0) / validConfidences.length
                        );
                    } else {
                        exportRow.receipt_confidence = 'UNDEFINED';
                    }
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

            // Update expenses data from current table before exporting
            this.updateExpensesFromTable();

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
                    // Use average confidence or highest confidence, excluding null values
                    const validConfidences = receipts.filter(r => r.confidence !== null && r.confidence !== undefined).map(r => r.confidence);
                    if (validConfidences.length > 0) {
                        exportRow.receipt_confidence = Math.round(
                            validConfidences.reduce((sum, c) => sum + c, 0) / validConfidences.length
                        );
                    } else {
                        exportRow.receipt_confidence = 'UNDEFINED';
                    }
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
            sourceType: 'expense',
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

        // Reset any inline opacity styles for backward compatibility
        const receiptPreview = event.target.closest('.receipt-preview');
        if (receiptPreview) {
            receiptPreview.style.opacity = '';
        }

        // Remove any remaining drag-over classes
        document.querySelectorAll('.drag-over, .receipt-drag-over, .file-drag-over').forEach(el => {
            el.classList.remove('drag-over', 'receipt-drag-over', 'file-drag-over');
        });
    }

    /**
     * Handle receipt drop onto an expense row
     */
    async handleReceiptDrop(draggedReceipt, targetExpenseId) {
        const { sourceType, sourceIndex, receipt, fromExpenseId, receiptIndex } = draggedReceipt;

        // Handle bulk receipt drops
        if (sourceType === 'bulk') {
            console.log('Moving bulk receipt:', receipt.name, 'to expense:', targetExpenseId);

            try {
                this.showLoading('Attaching receipt...');

                // Add bulk receipt to target expense
                const targetReceipts = this.receipts.get(targetExpenseId) || [];

                // Get the original receipt with file object from bulk receipts array
                const originalReceipt = this.bulkReceipts[sourceIndex];
                if (!originalReceipt) {
                    throw new Error('Original bulk receipt not found');
                }

                // Calculate actual confidence score using receipt_match_score function
                let receiptData = { ...originalReceipt };
                let confidence = null; // Initialize confidence as null

                try {
                    // Check if receipt already has a filePath (was previously uploaded)
                    if (originalReceipt.filePath) {
                        console.log('Receipt already uploaded, using existing file path:', originalReceipt.filePath);

                        // Get expense data for this expense ID
                        const expense = this.expenses.find(e => e.id === targetExpenseId);
                        if (!expense) {
                            throw new Error('Expense not found');
                        }

                        // Call the match-receipt endpoint directly
                        const receiptData = {
                            filePath: originalReceipt.filePath,
                            type: 'existing'
                        };

                        // Include invoiceDetails if available
                        if (originalReceipt.invoiceDetails) {
                            receiptData.invoiceDetails = originalReceipt.invoiceDetails;
                        }

                        const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                receipt_data: receiptData,
                                expense_data: expense,
                                receipt_path: originalReceipt.filePath
                            })
                        });

                        if (matchResponse.ok) {
                            const matchData = await matchResponse.json();
                            if (matchData.success) {
                                confidence = matchData.confidence_score;
                                if (confidence !== null && confidence !== undefined) {
                                    if (confidence <= 1) {
                                        confidence *= 100;
                                    }
                                    confidence = Math.round(confidence);
                                }
                                console.log('Calculated confidence score for existing file:', confidence);
                            }
                        }

                    } else if (originalReceipt.file) {
                        // Debug the file object
                        console.log('Original receipt object:', originalReceipt);
                        console.log('File object:', originalReceipt.file);
                        console.log('File name:', originalReceipt.file.name);
                        console.log('File type:', originalReceipt.file.type);
                        console.log('File size:', originalReceipt.file.size);

                        // For bulk receipts, we need to upload the file first
                        console.log('Uploading bulk receipt file for match scoring:', originalReceipt.file.name);

                        const formData = new FormData();
                        formData.append('file', originalReceipt.file);
                        formData.append('expense_id', targetExpenseId);

                        const uploadResponse = await fetch('/api/receipts/upload', {
                            method: 'POST',
                            body: formData
                        });

                        if (!uploadResponse.ok) {
                            const errorText = await uploadResponse.text();
                            console.error('Upload failed:', uploadResponse.status, errorText);
                            throw new Error(`Upload failed: ${uploadResponse.status}`);
                        }

                        const uploadData = await uploadResponse.json();
                        console.log('Upload successful, now calculating match score');

                        // Get expense data for this expense ID
                        const expense = this.expenses.find(e => e.id === targetExpenseId);
                        if (!expense) {
                            throw new Error('Expense not found');
                        }

                        // Call the match-receipt endpoint
                        const receiptData = {
                            filePath: uploadData.file_info.file_path,
                            type: 'uploaded'
                        };

                        // Include invoiceDetails if available
                        if (originalReceipt.invoiceDetails) {
                            receiptData.invoiceDetails = originalReceipt.invoiceDetails;
                        }

                        const matchResponse = await fetch('/api/expenses/match-receipt?debug=true', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                receipt_data: receiptData,
                                expense_data: expense,
                                receipt_path: uploadData.file_info.file_path
                            })
                        });

                        if (matchResponse.ok) {
                            const matchData = await matchResponse.json();
                            if (matchData.success) {
                                confidence = matchData.confidence_score;
                                if (confidence !== null && confidence !== undefined) {
                                    if (confidence <= 1) {
                                        confidence *= 100;
                                    }
                                    confidence = Math.round(confidence);
                                }
                                console.log('Calculated confidence score:', confidence);
                            }
                        }

                        // Update receipt data with file upload information
                        receiptData.filePath = uploadData.file_info.file_path;
                        receiptData.filename = uploadData.file_info.saved_filename;
                        receiptData.originalFilename = uploadData.file_info.original_filename;
                    } else {
                        console.log('No file object or file path available for receipt:', originalReceipt.name);
                        // Use default confidence and existing receipt data
                    }
                } catch (error) {
                    console.warn('Failed to calculate match score for bulk receipt:', error);
                    // Continue with default confidence
                }

                // Create a copy of the receipt for the expense
                const newReceipt = {
                    ...receiptData,
                    confidence: confidence
                };

                targetReceipts.push(newReceipt);
                this.receipts.set(targetExpenseId, targetReceipts);

                // Remove from bulk receipts
                this.bulkReceipts.splice(sourceIndex, 1);
                this.updateBulkReceiptCell();

                // Refresh the table display
                this.displayExpensesTable();

                this.showToast(`Receipt "${receipt.name}" attached to expense`, 'success');
            } catch (error) {
                console.error('Error attaching bulk receipt:', error);
                this.showToast(`Failed to attach receipt: ${error.message}`, 'error');
            } finally {
                this.hideLoading();
            }
            return;
        }

        // Handle regular receipt moves between expenses
        // Don't allow dropping on the same expense
        if (fromExpenseId === targetExpenseId) {
            this.showToast('Cannot move receipt to the same expense', 'warning');
            return;
        }

        console.log('Moving receipt:', receipt.name, 'from expense:', fromExpenseId, 'to expense:', targetExpenseId);
        console.log('Original receipt object:', receipt);

        try {
            this.showLoading('Moving receipt...');

            // Get target expense data for confidence calculation
            const targetExpense = this.expenses.find(e => e.id === targetExpenseId);

            // Prepare receipt data with proper filename field for API
            const receiptDataForAPI = {
                ...receipt,
                filename: receipt.filename || receipt.name || receipt.originalFilename
            };

            console.log('Receipt data being sent to API:', receiptDataForAPI);
            console.log('Target expense data:', targetExpense);

            // Call the backend API to move the receipt
            const response = await fetch('/api/receipts/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    receipt_data: receiptDataForAPI,
                    from_expense_id: fromExpenseId,
                    to_expense_id: targetExpenseId,
                    to_expense_data: targetExpense
                })
            });

            const data = await response.json();

            if (data.success) {
                // Use the updated receipt data from the backend (includes new confidence score)
                const updatedReceipt = data.receipt_data || receipt;

                // Log the confidence score update
                if (data.new_confidence_score !== null && data.new_confidence_score !== undefined) {
                    console.log(`Updated confidence score: ${data.new_confidence_score}% for receipt moved to expense ${targetExpenseId}`);
                }

                // Update the frontend receipts data with the updated receipt
                this.moveReceiptInFrontend(fromExpenseId, receiptIndex, targetExpenseId, updatedReceipt);

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
     * Handle dropping a receipt back to the bulk receipt area
     */
    async handleReceiptDropToBulkArea(draggedReceipt) {
        const { sourceType, sourceIndex, receipt, fromExpenseId, receiptIndex } = draggedReceipt;

        // Only handle receipts coming from expense rows (not bulk to bulk)
        if (sourceType === 'bulk') {
            this.showToast('Receipt is already in the bulk area', 'info');
            return;
        }

        // Handle receipts from expense rows
        if (sourceType === 'expense' && fromExpenseId !== undefined && receiptIndex !== undefined) {
            console.log('Moving receipt from expense back to bulk area:', receipt.name);

            try {
                this.showLoading('Moving receipt to bulk area...');

                // Remove from the expense
                const sourceReceipts = this.receipts.get(fromExpenseId) || [];
                sourceReceipts.splice(receiptIndex, 1);
                this.receipts.set(fromExpenseId, sourceReceipts);

                // Add to bulk receipts (create a copy preserving all properties including invoiceDetails)
                const bulkReceipt = {
                    ...receipt, // Copy all properties including invoiceDetails
                    name: receipt.name || receipt.filename,
                    originalFilename: receipt.originalFilename || receipt.name || receipt.filename
                };

                this.bulkReceipts.push(bulkReceipt);

                // Update displays
                this.updateBulkReceiptCell();
                this.displayExpensesTable();

                this.showToast(`Receipt "${bulkReceipt.name}" moved to bulk area`, 'success');

            } catch (error) {
                console.error('Error moving receipt to bulk area:', error);
                this.showToast(`Failed to move receipt to bulk area: ${error.message}`, 'error');
            } finally {
                this.hideLoading();
            }
        }
    }

    // ===== BULK RECEIPTS IMPORT FUNCTIONALITY =====

    /**
     * Initialize bulk receipts import functionality (similar to receipts column)
     */
    initBulkReceiptsImport() {
        this.bulkReceipts = []; // Store bulk imported receipts using same structure as receipts column

        const container = document.getElementById('receipts-import-container');

        // Make the container droppable for files
        this.makeBulkReceiptContainerDroppable(container);

        // Initialize the display
        this.updateBulkReceiptCell();
    }

    /**
     * Make the bulk receipt container droppable for files and receipts
     */
    makeBulkReceiptContainerDroppable(container) {
        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            const isDraggingFile = e.dataTransfer.types.includes('Files');
            const isDraggingReceipt = e.dataTransfer.types.includes('application/x-receipt-data');

            console.log('Drag over bulk container - File:', isDraggingFile, 'Receipt:', isDraggingReceipt);

            if (isDraggingFile) {
                container.classList.add('drag-over', 'file-drag-over');
            } else if (isDraggingReceipt) {
                container.classList.add('drag-over', 'receipt-drag-over');
            }
        });

        container.addEventListener('dragleave', (e) => {
            if (!container.contains(e.relatedTarget)) {
                container.classList.remove('drag-over', 'file-drag-over', 'receipt-drag-over');
            }
        });

        container.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            container.classList.remove('drag-over', 'file-drag-over', 'receipt-drag-over');

            console.log('Drop event on bulk container');

            // Handle receipt drops first
            const receiptData = e.dataTransfer.getData('application/x-receipt-data');
            if (receiptData) {
                console.log('Receipt drop detected:', receiptData);
                const draggedReceipt = JSON.parse(receiptData);
                this.handleReceiptDropToBulkArea(draggedReceipt);
                return;
            }

            // Handle file drops
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                console.log('File drop detected:', files.length, 'files');
                this.handleBulkReceiptSelection(files);
            }
        });
    }

    /**
     * Select bulk receipts (triggered by button click)
     */
    selectBulkReceipts() {
        document.getElementById('bulk-receipt-input').click();
    }

    /**
     * Handle bulk receipt file selection (follows same pattern as handleMultipleReceiptSelection)
     */
    async handleBulkReceiptSelection(files) {
        if (!files || files.length === 0) return;

        const filesArray = Array.from(files);
        const validFiles = [];
        const invalidFiles = [];
        const duplicateFiles = [];
        const skippedFiles = [];

        // Validate files using same logic as receipts column
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

        // Show validation errors
        if (invalidFiles.length > 0) {
            this.showToast(`Skipped ${invalidFiles.length} invalid files: ${invalidFiles.join(', ')}`, 'warning');
        }

        if (validFiles.length === 0) {
            this.showToast('No valid files to upload', 'error');
            return;
        }

        this.showLoading(`Checking for duplicates in ${validFiles.length} receipts...`);

        try {
            // Check for duplicates before processing
            const filesToProcess = [];

            for (const file of validFiles) {
                const duplicates = this.findAllDuplicates(file.name);
                if (duplicates.length > 0) {
                    duplicateFiles.push(file.name);
                    skippedFiles.push(file);
                } else {
                    filesToProcess.push(file);
                }
            }

            // Show duplicate notification
            if (duplicateFiles.length > 0) {
                this.showDuplicateNotification(
                    `Skipped ${duplicateFiles.length} duplicate file(s): ${duplicateFiles.join(', ')}. These files are already present in the bulk upload area or expense table.`,
                    'warning'
                );
            }

            if (filesToProcess.length === 0) {
                this.showToast('All files were duplicates - no new files to process', 'info');
                return;
            }

            const aiExtractionEnabled = this.isAIExtractionEnabled();
            const loadingMessage = aiExtractionEnabled
                ? `Processing ${filesToProcess.length} new receipts with AI extraction...`
                : `Processing ${filesToProcess.length} new receipts...`;

            this.showLoading(loadingMessage);

            // Process each non-duplicate file and add to bulk receipts in parallel
            const receiptPromises = filesToProcess.map(async (file) => {
                // Create receipt object using same structure as receipts column
                let preview = '';
                let type = 'pdf';

                if (file.type.startsWith('image/')) {
                    preview = await this.createImagePreview(file);
                    type = 'image';
                } else if (file.type === 'application/pdf') {
                    preview = await this.createPDFPreview(file);
                    type = 'pdf';
                }

                // Extract invoice details for this receipt (only if AI extraction is enabled)
                let invoiceDetails = null;
                const aiExtractionEnabled = this.isAIExtractionEnabled();

                if (aiExtractionEnabled) {
                    try {
                        invoiceDetails = await this.extractInvoiceDetails(file);
                    } catch (error) {
                        console.warn(`Failed to extract invoice details for ${file.name}:`, error);
                        // Continue processing even if extraction fails
                    }
                } else {
                    console.log(`Skipping AI extraction for ${file.name} - AI extraction disabled`);
                }

                return {
                    name: file.name,
                    file_path: file.name, // This would normally be a server path
                    preview: preview,
                    type: type,
                    confidence: null, // No confidence for bulk imports
                    file: file, // Keep the file object for potential later upload
                    invoiceDetails: invoiceDetails // Add extracted invoice details
                };
            });

            // Wait for all receipts to be processed in parallel
            const receipts = await Promise.all(receiptPromises);

            // Add all processed receipts to bulk receipts
            this.bulkReceipts.push(...receipts);

            let successMessage = `Successfully imported ${filesToProcess.length} receipts`;
            if (!aiExtractionEnabled) {
                successMessage += ' (without AI extraction)';
            }
            if (duplicateFiles.length > 0) {
                successMessage += ` (${duplicateFiles.length} duplicates skipped)`;
            }
            this.showToast(successMessage, 'success');
            this.updateBulkReceiptCell();
        } catch (error) {
            console.error('Error processing receipts:', error);
            this.showToast('Error processing some receipts', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Match bulk receipts with expenses using the backend matching algorithm
     */
    async matchReceiptsWithExpenses() {
        if (this.bulkReceipts.length === 0) {
            this.showToast('No receipts to match. Please add receipts first.', 'warning');
            return;
        }

        if (this.expenses.length === 0) {
            this.showToast('No expenses to match with. Please add expenses first.', 'warning');
            return;
        }

        this.showLoading(`Matching ${this.bulkReceipts.length} receipts with ${this.expenses.length} expenses...`);

        try {
            // Prepare data for the backend
            const receiptData = this.bulkReceipts.map(receipt => {
                // Include ALL fields from receipt using spread operator, excluding file object
                const { file, ...receiptRecord } = receipt;
                return receiptRecord;
            });

            const expenseData = this.expenses.map(expense => {
                // Include ALL fields from the expense data
                const expenseRecord = { ...expense };

                // Ensure receipts field is included for matching context
                expenseRecord.receipts = this.receipts.get(expense.id) || [];

                return expenseRecord;
            });

            console.log('Data being sent to backend:');
            console.log('Receipt data sample:', receiptData[0]);
            console.log('Expense data sample:', expenseData[0]);

            // Call the backend matching endpoint
            const response = await fetch('/api/receipts/match_bulk_receipts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    bulk_receipts: receiptData,
                    expense_data: expenseData
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                const matchedExpenseData = result.matched_expense_data || [];
                const unmatchedReceipts = result.unmatched_receipts || [];

                // Calculate number of matched receipts
                const totalMatchedReceipts = matchedExpenseData.reduce((count, expense) => {
                    return count + (expense.receipts ? expense.receipts.length : 0);
                }, 0);

                this.showToast(`Matching completed! Attached ${totalMatchedReceipts} receipts to expenses.`, 'success');

                // Update the expense data with the matched results
                this.updateExpenseDataWithMatches(matchedExpenseData, unmatchedReceipts);

            } else {
                throw new Error(result.message || 'Matching failed');
            }

        } catch (error) {
            console.error('Error matching receipts with expenses:', error);
            this.showToast('Error matching receipts with expenses: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Update expense data table with matched results from backend
     */
    updateExpenseDataWithMatches(matchedExpenseData, unmatchedReceipts) {
        console.log('updateExpenseDataWithMatches called with:', {
            matchedExpenseData,
            unmatchedReceipts
        });

        // Update this.expenses with the matched expense data
        this.expenses = matchedExpenseData;
        console.log('Updated this.expenses:', this.expenses);

        // Clear and rebuild the receipts map based on the matched data
        this.receipts.clear();

        // Process each expense from the matched data
        this.expenses.forEach(expense => {
            console.log('Processing expense:', expense.id, 'receipts:', expense.receipts);
            if (expense.receipts && expense.receipts.length > 0) {
                // Convert backend receipt format to frontend format
                const formattedReceipts = expense.receipts.map(receipt => ({
                    name: receipt.name,
                    type: receipt.type || (receipt.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'image'),
                    preview: receipt.preview || null,
                    confidence: 100, // Backend matches are considered high confidence
                    file: null, // File object not available from backend
                    filePath: receipt.filePath || receipt.file_path,
                    filename: receipt.filename || receipt.name,
                    originalFilename: receipt.originalFilename || receipt.name,
                    invoiceDetails: receipt.invoiceDetails
                }));

                console.log('Setting receipts for expense', expense.id, ':', formattedReceipts);
                this.receipts.set(expense.id, formattedReceipts);
            }
        });

        console.log('Final receipts map:', this.receipts);

        // Update bulk receipts with only the unmatched ones
        this.bulkReceipts = unmatchedReceipts;

        // Refresh the display
        console.log('Calling displayExpensesTable() after matching...');
        this.displayExpensesTable();
        console.log('Calling updateBulkReceiptCell() after matching...');
        this.updateBulkReceiptCell();
        console.log('Calling updateStatistics() after matching...');
        this.updateStatistics();

        // Show success message with details
        const totalAttachedReceipts = Array.from(this.receipts.values()).reduce((count, receipts) => count + receipts.length, 0);
        console.log('Final state after matching:');
        console.log('- this.expenses:', this.expenses);
        console.log('- this.receipts map:', this.receipts);
        console.log('- totalAttachedReceipts:', totalAttachedReceipts);

        // Verify each expense has the correct receipts
        this.expenses.forEach(expense => {
            const receiptsForExpense = this.receipts.get(expense.id);
            console.log(`Expense ${expense.id} has ${receiptsForExpense ? receiptsForExpense.length : 0} receipts:`, receiptsForExpense);
        });

        this.showToast(`Successfully updated expense table! ${totalAttachedReceipts} receipts attached, ${unmatchedReceipts.length} receipts remain unmatched.`, 'success');
    }

    /**
     * Display matching results to the user
     */
    showMatchingResults(matches) {
        let message = `Found ${matches.length} potential matches:\n\n`;

        matches.forEach((match, index) => {
            message += `${index + 1}. Receipt: "${match.receipt.name}" ➔ Expense: "${match.expense.description}" (Score: ${(match.score * 100).toFixed(1)}%)\n`;
            if (match.receipt.invoiceDetails) {
                message += `   Amount: ${match.receipt.invoiceDetails.amount || 'N/A'} | Date: ${match.receipt.invoiceDetails.date || 'N/A'}\n`;
            }
            message += '\n';
        });

        message += 'Would you like to apply these matches automatically?';

        if (confirm(message)) {
            this.applyMatches(matches);
        }
    }

    /**
     * Apply the matched receipts to their corresponding expenses
     */
    async applyMatches(matches) {
        let appliedCount = 0;

        for (const match of matches) {
            try {
                // Find the expense in our current data
                const expenseIndex = this.expenses.findIndex(exp => exp.id === match.expense.id);
                if (expenseIndex === -1) continue;

                // Find the receipt in our bulk receipts
                const receiptIndex = this.bulkReceipts.findIndex(receipt => receipt.name === match.receipt.name);
                if (receiptIndex === -1) continue;

                const expense = this.expenses[expenseIndex];
                const receipt = this.bulkReceipts[receiptIndex];

                // Initialize receipts array if not exists
                if (!expense.receipts) {
                    expense.receipts = [];
                }

                // Add receipt to expense (avoid duplicates)
                const existingReceipt = expense.receipts.find(r => r.name === receipt.name);
                if (!existingReceipt) {
                    expense.receipts.push({
                        name: receipt.name,
                        file_path: receipt.file_path,
                        preview: receipt.preview,
                        type: receipt.type,
                        confidence: match.score
                    });

                    // Remove from bulk receipts
                    this.bulkReceipts.splice(receiptIndex, 1);
                    appliedCount++;
                }

            } catch (error) {
                console.error('Error applying match:', error);
            }
        }

        // Update the display
        this.updateBulkReceiptCell();
        this.updateTable();

        this.showToast(`Successfully applied ${appliedCount} matches!`, 'success');
    }

    /**
     * Update bulk receipt cell display (follows same pattern as createReceiptCell)
     */
    updateBulkReceiptCell() {
        const cell = document.getElementById('bulk-receipt-cell');
        if (!cell) return;

        const receipts = this.bulkReceipts;
        let html = '';

        // Display existing receipts using same pattern as createReceiptCell
        if (receipts.length > 0) {
            html += '<div class="receipts-container">';
            receipts.forEach((receipt, index) => {
                // Escape quotes in preview URL for HTML attributes
                const escapedPreview = receipt.preview ? receipt.preview.replace(/'/g, '&#39;') : '';
                const escapedName = receipt.name ? receipt.name.replace(/'/g, '&#39;') : '';

                html += `
                    <div class="receipt-preview"
                         data-receipt-index="${index}"
                         data-bulk-receipt="true"
                         draggable="true"
                         ondragstart="app.handleBulkReceiptDragStart(event, ${index})"
                         ondragend="app.handleReceiptDragEnd(event)">
                        <button onclick="app.removeBulkReceipt(${index})" class="btn btn-sm">
                            <i class="fas fa-trash"></i>
                        </button>
                        ${receipt.type === 'image' ?
                        `<img src="${receipt.preview}" alt="Receipt" class="receipt-thumbnail"
                              onclick="app.showBulkReceiptModal(${index})"
                              onmouseenter="app.showTooltip(event, '${escapedPreview}', 'image')"
                              onmouseleave="app.hideTooltip()">` :
                        receipt.preview && receipt.preview.startsWith('data:image') ?
                            `<img src="${receipt.preview}" alt="PDF Preview" class="receipt-thumbnail"
                                  onclick="app.showBulkReceiptModal(${index})"
                                  onmouseenter="app.showTooltip(event, '${escapedPreview}', 'pdf')"
                                  onmouseleave="app.hideTooltip()">` :
                            `<div class="pdf-preview receipt-thumbnail"
                                  onclick="app.showBulkReceiptModal(${index})"
                                  onmouseenter="app.showTooltip(event, null, 'pdf', '${escapedName}')"
                                  onmouseleave="app.hideTooltip()">
                            <i class="fas fa-file-pdf"></i>
                            <div class="pdf-label">PDF</div>
                        </div>`
                    }
                        <div class="receipt-info">
                            <div class="receipt-name">${receipt.name}</div>
                            <div class="receipt-confidence">Bulk Import</div>
                        </div>
                        ${receipt.invoiceDetails ? `
                        <div class="invoice-details">
                            <div class="invoice-details-content">
                                <div class="detail-item detail-amount">${receipt.invoiceDetails.Amount}${receipt.invoiceDetails.Currency ? ` ${receipt.invoiceDetails.Currency}` : ''}</div>
                                <div class="detail-item detail-date">${receipt.invoiceDetails.Date}</div>
                                <div class="detail-item detail-category">${receipt.invoiceDetails['Expense category']}</div>
                            </div>
                        </div>
                        ` : ''}
                        <div class="drag-indicator">
                            <i class="fas fa-arrows-alt"></i>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        // Show the file input but hidden
        html += `
            <input type="file" id="bulk-receipt-input" accept="image/*,.pdf" multiple style="display: none;"
                   onchange="app.handleBulkReceiptSelection(this.files)">
        `;

        // Show drag instructions when no receipts are present
        if (receipts.length === 0) {
            html += `
                <div class="drag-instructions">
                    <small><i class="fas fa-arrows-alt"></i> Drag receipts here from table or drop files to import</small>
                </div>
            `;
        }

        cell.innerHTML = html;

        // Update the action buttons in the header
        this.updateBulkReceiptActions();
    }

    /**
     * Update the bulk receipt action buttons in the header
     */
    updateBulkReceiptActions() {
        const actionsContainer = document.getElementById('bulk-receipt-actions');
        if (!actionsContainer) return;

        const receipts = this.bulkReceipts;
        let html = '';

        // Always show the attach receipt button
        html += `
            <button onclick="app.selectBulkReceipts()" class="btn btn-primary btn-sm">
                <i class="fas fa-paperclip"></i> ${receipts.length > 0 ? 'Add More Receipts' : 'Attach Receipts'}
            </button>
        `;

        // Show match button when there are receipts
        if (receipts.length > 0) {
            html += `
                <button onclick="app.matchReceiptsWithExpenses()" class="btn btn-success btn-sm">
                    <i class="fas fa-link"></i> Match receipts with expenses
                </button>
            `;
        }

        actionsContainer.innerHTML = html;
    }

    /**
     * Handle bulk receipt drag start (similar to handleReceiptDragStart)
     */
    handleBulkReceiptDragStart(event, receiptIndex) {
        const receipt = this.bulkReceipts[receiptIndex];
        if (!receipt) return;

        // Set drag data but exclude the file object since it can't be serialized
        const dragData = {
            sourceType: 'bulk',
            sourceIndex: receiptIndex,
            receipt: {
                ...receipt,
                file: null // Remove file object since it can't be JSON stringified
            }
        };

        event.dataTransfer.setData('application/x-receipt-data', JSON.stringify(dragData));
        event.dataTransfer.effectAllowed = 'move';

        // Add visual feedback using CSS class (consistent with handleReceiptDragStart)
        event.target.closest('.receipt-preview').classList.add('being-dragged');
    }

    /**
     * Remove a bulk receipt
     */
    removeBulkReceipt(index) {
        if (index >= 0 && index < this.bulkReceipts.length) {
            const receipt = this.bulkReceipts[index];
            this.bulkReceipts.splice(index, 1);
            this.updateBulkReceiptCell();
            this.showToast(`Removed ${receipt.name}`, 'info');
        }
    }

    /**
     * Show bulk receipt in modal (similar to showReceiptModal)
     */
    showBulkReceiptModal(receiptIndex) {
        const receipt = this.bulkReceipts[receiptIndex];
        if (!receipt) return;

        // Use existing modal functionality
        this.showReceiptInModal(receipt);
    }

    /**
     * Show receipt in modal (reusable for both bulk and expense receipts)
     */
    showReceiptInModal(receipt) {
        const modal = document.getElementById('receipt-modal');
        const modalBody = modal.querySelector('.modal-body #receipt-preview');

        if (receipt.type === 'image' || (receipt.preview && receipt.preview.startsWith('data:image'))) {
            modalBody.innerHTML = `<img src="${receipt.preview}" alt="Receipt" style="max-width: 100%; height: auto;">`;
        } else {
            modalBody.innerHTML = `
                <div style="text-align: center; padding: 2rem;">
                    <i class="fas fa-file-pdf" style="font-size: 4rem; color: #dc3545; margin-bottom: 1rem;"></i>
                    <h4>${receipt.name}</h4>
                    <p>PDF preview not available in modal</p>
                </div>
            `;
        }

        modal.style.display = 'block';
    }

    // ===== END BULK RECEIPTS IMPORT FUNCTIONALITY =====

    // ===== AI EXTRACTION CONTROL =====

    /**
     * Check if AI extraction is enabled based on checkbox state
     */
    isAIExtractionEnabled() {
        const checkbox = document.getElementById('ai-extraction-checkbox');
        return checkbox ? checkbox.checked : true; // Default to true if checkbox not found
    }

    // ===== END AI EXTRACTION CONTROL =====

    // ===== DUPLICATE DETECTION FUNCTIONALITY =====

    /**
     * Check if a file is a duplicate based on filename only
     */
    isDuplicateFile(newFileName, existingFile) {
        // Simple filename comparison
        return newFileName === existingFile.name;
    }

    /**
     * Find duplicates in bulk receipts area
     */
    findDuplicatesInBulkReceipts(newFileName) {
        const duplicates = [];
        for (let i = 0; i < this.bulkReceipts.length; i++) {
            const existingReceipt = this.bulkReceipts[i];
            if (this.isDuplicateFile(newFileName, existingReceipt)) {
                duplicates.push({ type: 'bulk', index: i, receipt: existingReceipt });
            }
        }
        return duplicates;
    }

    /**
     * Find duplicates in expense table receipts
     */
    findDuplicatesInExpenseReceipts(newFileName) {
        const duplicates = [];
        for (const [expenseId, receipts] of this.receipts.entries()) {
            for (let i = 0; i < receipts.length; i++) {
                const existingReceipt = receipts[i];
                if (this.isDuplicateFile(newFileName, existingReceipt)) {
                    duplicates.push({
                        type: 'expense',
                        expenseId: expenseId,
                        index: i,
                        receipt: existingReceipt
                    });
                }
            }
        }
        return duplicates;
    }

    /**
     * Find all duplicates of a file across both areas
     */
    findAllDuplicates(newFileName) {
        const bulkDuplicates = this.findDuplicatesInBulkReceipts(newFileName);
        const expenseDuplicates = this.findDuplicatesInExpenseReceipts(newFileName);
        return [...bulkDuplicates, ...expenseDuplicates];
    }    /**
     * Remove duplicates from both areas
     */
    removeDuplicates(duplicates) {
        // Sort by type and index in reverse order to maintain correct indices while removing
        const sortedDuplicates = duplicates.sort((a, b) => {
            if (a.type !== b.type) {
                return a.type === 'bulk' ? -1 : 1; // Remove bulk first
            }
            return b.index - a.index; // Remove from end to beginning
        });

        let removedCount = 0;
        const removedFiles = [];

        for (const duplicate of sortedDuplicates) {
            if (duplicate.type === 'bulk') {
                if (duplicate.index < this.bulkReceipts.length) {
                    const removed = this.bulkReceipts.splice(duplicate.index, 1)[0];
                    removedFiles.push(removed.name);
                    removedCount++;
                }
            } else if (duplicate.type === 'expense') {
                const receipts = this.receipts.get(duplicate.expenseId);
                if (receipts && duplicate.index < receipts.length) {
                    const removed = receipts.splice(duplicate.index, 1)[0];
                    removedFiles.push(removed.name);
                    removedCount++;

                    // Update the receipts map
                    if (receipts.length === 0) {
                        this.receipts.delete(duplicate.expenseId);
                    } else {
                        this.receipts.set(duplicate.expenseId, receipts);
                    }
                }
            }
        }

        return { removedCount, removedFiles };
    }

    /**
     * Show notification for duplicate handling
     */
    showDuplicateNotification(message, type = 'info') {
        this.showToast(message, type);
    }

    // ===== END DUPLICATE DETECTION FUNCTIONALITY =====

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
    if (window.app) {
        window.app.closeAllModals();
    } else {
        // Fallback if app is not initialized yet
        const modal = document.getElementById('receipt-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new EZExpenseApp();
});
