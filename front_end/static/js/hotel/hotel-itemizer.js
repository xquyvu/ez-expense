/**
 * Hotel Itemizer JavaScript
 * 
 * Handles the frontend logic for hotel invoice processing,
 * category validation, and MS Expense itemization.
 */

class HotelItemizer {
    constructor() {
        this.currentInvoiceData = null;
        this.categories = [];
        this.consolidatedCategories = [];
        
        this.initializeEventListeners();
        this.loadCategories();
    }

    initializeEventListeners() {
        // File upload handling
        const uploadBtn = document.getElementById('upload-btn');
        const fileInput = document.getElementById('invoice-file');
        const uploadArea = document.getElementById('upload-area');
        const extractBtn = document.getElementById('extract-btn');

        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        extractBtn.addEventListener('click', () => this.extractInvoice());

        // Drag and drop handling
        uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        uploadArea.addEventListener('drop', (e) => this.handleDrop(e));
        uploadArea.addEventListener('dragleave', () => this.handleDragLeave());

        // Validation and processing buttons
        const validateBtn = document.getElementById('validate-btn');
        const itemizeBtn = document.getElementById('itemize-btn');
        const restartBtn = document.getElementById('restart-btn');
        const addItemBtn = document.getElementById('add-item-btn');

        validateBtn.addEventListener('click', () => this.validateCategories());
        itemizeBtn.addEventListener('click', () => this.itemizeExpense());
        restartBtn.addEventListener('click', () => this.restart());
        addItemBtn.addEventListener('click', () => this.addNewLineItem());

        // Error handling
        const dismissErrorBtn = document.getElementById('dismiss-error');
        dismissErrorBtn.addEventListener('click', () => this.dismissError());
    }

    async loadCategories() {
        try {
            const response = await fetch('/api/hotel/categories');
            const data = await response.json();
            
            if (data.success) {
                this.categories = data.data.categories;
                console.log('Loaded hotel categories:', this.categories);
            } else {
                this.showError('Failed to load hotel categories');
            }
        } catch (error) {
            console.error('Error loading categories:', error);
            this.showError('Error loading categories: ' + error.message);
        }
    }

    handleFileSelection(event) {
        const file = event.target.files[0];
        if (file) {
            this.updateUploadDisplay(file);
            this.enableExtractButton();
        }
    }

    handleDragOver(event) {
        event.preventDefault();
        document.getElementById('upload-area').classList.add('drag-over');
    }

    handleDrop(event) {
        event.preventDefault();
        document.getElementById('upload-area').classList.remove('drag-over');
        
        const files = event.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                document.getElementById('invoice-file').files = files;
                this.updateUploadDisplay(file);
                this.enableExtractButton();
            } else {
                this.showError('Please upload a PDF file');
            }
        }
    }

    handleDragLeave() {
        document.getElementById('upload-area').classList.remove('drag-over');
    }

    updateUploadDisplay(file) {
        const uploadArea = document.getElementById('upload-area');
        uploadArea.querySelector('h3').textContent = `Selected: ${file.name}`;
        uploadArea.querySelector('p').textContent = `Size: ${this.formatFileSize(file.size)}`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    enableExtractButton() {
        const extractBtn = document.getElementById('extract-btn');
        const originalAmount = document.getElementById('original-amount').value;
        
        if (originalAmount && parseFloat(originalAmount) > 0) {
            extractBtn.disabled = false;
        }
        
        // Also listen for original amount changes
        document.getElementById('original-amount').addEventListener('input', () => {
            const amount = document.getElementById('original-amount').value;
            extractBtn.disabled = !(amount && parseFloat(amount) > 0);
        });
    }

    async extractInvoice() {
        const fileInput = document.getElementById('invoice-file');
        const originalAmount = document.getElementById('original-amount').value;
        
        if (!fileInput.files[0]) {
            this.showError('Please select a PDF file');
            return;
        }
        
        if (!originalAmount || parseFloat(originalAmount) <= 0) {
            this.showError('Please enter a valid original amount');
            return;
        }

        this.showLoading('Extracting invoice details...');

        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('original_amount', originalAmount);

            const response = await fetch('/api/hotel/extract', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (data.success) {
                this.currentInvoiceData = data.data;
                this.displayInvoiceDetails(data.data);
                this.showValidationSection();
            } else {
                this.showError(data.message || 'Failed to extract invoice details');
            }
        } catch (error) {
            console.error('Error extracting invoice:', error);
            this.showError('Error processing invoice: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displayInvoiceDetails(invoiceData) {
        // Display invoice summary
        const summaryHtml = `
            <div class="invoice-detail-grid">
                <div class="invoice-detail-item">
                    <span class="label">Hotel Name</span>
                    <span class="value">${invoiceData.hotel_name}</span>
                </div>
                <div class="invoice-detail-item">
                    <span class="label">Location</span>
                    <span class="value">${invoiceData.hotel_location || 'N/A'}</span>
                </div>
                <div class="invoice-detail-item">
                    <span class="label">Check-in Date</span>
                    <span class="value">${invoiceData.check_in_date}</span>
                </div>
                <div class="invoice-detail-item">
                    <span class="label">Check-out Date</span>
                    <span class="value">${invoiceData.check_out_date}</span>
                </div>
                <div class="invoice-detail-item">
                    <span class="label">Total Amount</span>
                    <span class="value amount">$${invoiceData.total_amount}</span>
                </div>
                <div class="invoice-detail-item">
                    <span class="label">Currency</span>
                    <span class="value">${invoiceData.currency}</span>
                </div>
            </div>
        `;
        
        document.getElementById('invoice-summary').innerHTML = summaryHtml;
        
        // Display line items table
        this.displayLineItems(invoiceData.line_items);
        
        // Update totals
        document.getElementById('original-total').textContent = `$${invoiceData.total_amount}`;
        
        // Enable validation when categories are assigned
        this.updateValidationStatus();
    }

    displayLineItems(lineItems) {
        const tableBody = document.querySelector('#line-items-table tbody');
        tableBody.innerHTML = '';
        
        // Populate the add item category dropdown
        this.populateAddItemCategoryDropdown();
        
        lineItems.forEach((item, index) => {
            const isDailyRate = this.isDailyRateCategory(item.suggested_category || '');
            const chargeType = isDailyRate ? 'Daily' : 'One-time';
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.description}</td>
                <td class="amount">$${item.amount}</td>
                <td>${item.service_date || 'N/A'}</td>
                <td>${item.suggested_category || 'N/A'}</td>
                <td>
                    <select class="category-select" data-index="${index}">
                        <option value="">Select category...</option>
                        ${this.categories.map(cat => 
                            `<option value="${cat.value}" ${cat.value === item.suggested_category ? 'selected' : ''}>
                                ${cat.title}
                            </option>`
                        ).join('')}
                    </select>
                </td>
                <td>
                    <span class="charge-type ${isDailyRate ? 'daily' : 'onetime'}">${chargeType}</span>
                </td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="hotelItemizer.removeLineItem(${index})">
                        Remove
                    </button>
                </td>
            `;
            
            tableBody.appendChild(row);
        });
        
        // Add event listeners to category selects
        document.querySelectorAll('.category-select').forEach(select => {
            select.addEventListener('change', () => this.updateValidationStatus());
        });
    }

    updateValidationStatus() {
        const selects = document.querySelectorAll('.category-select');
        let categorizedTotal = 0;
        let ignoredTotal = 0;
        let allCategorized = true;
        
        selects.forEach((select, index) => {
            const amount = parseFloat(this.currentInvoiceData.line_items[index].amount);
            const category = select.value;
            
            if (!category) {
                allCategorized = false;
            } else if (category === 'Ignore') {
                ignoredTotal += amount;
            } else {
                categorizedTotal += amount;
            }
        });
        
        // Update display
        document.getElementById('categorized-total').textContent = `$${categorizedTotal.toFixed(2)}`;
        document.getElementById('ignored-total').textContent = `$${ignoredTotal.toFixed(2)}`;
        
        const originalTotal = parseFloat(this.currentInvoiceData.total_amount);
        const totalDifference = Math.abs((categorizedTotal + ignoredTotal) - originalTotal);
        const isValid = allCategorized && totalDifference < 0.01;
        
        const statusElement = document.getElementById('validation-status');
        statusElement.className = `total-item validation-status ${isValid ? 'valid' : 'invalid'}`;
        statusElement.querySelector('.status').textContent = isValid ? 'Valid' : 'Invalid';
        
        // Enable/disable validate button
        document.getElementById('validate-btn').disabled = !isValid;
    }

    async validateCategories() {
        if (!this.currentInvoiceData) {
            this.showError('No invoice data available');
            return;
        }

        this.showLoading('Validating categories...');

        try {
            // Collect user-selected categories
            const selects = document.querySelectorAll('.category-select');
            const updatedLineItems = this.currentInvoiceData.line_items.map((item, index) => ({
                ...item,
                user_category: selects[index].value
            }));

            const requestData = {
                invoice_details: {
                    ...this.currentInvoiceData,
                    line_items: updatedLineItems
                }
            };

            const response = await fetch('/api/hotel/validate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (data.success) {
                this.consolidatedCategories = data.data.consolidated_categories;
                this.displayConsolidation(data.data);
                this.showConsolidationSection();
            } else {
                this.showError(data.message || 'Validation failed');
            }
        } catch (error) {
            console.error('Error validating categories:', error);
            this.showError('Error validating categories: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displayConsolidation(consolidationData) {
        const tableBody = document.querySelector('#consolidated-table tbody');
        tableBody.innerHTML = '';
        
        consolidationData.consolidated_categories.forEach(category => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${category.category}</td>
                <td class="amount">$${category.total_amount}</td>
                <td class="amount">${category.daily_rate ? `$${category.daily_rate}` : 'N/A'}</td>
                <td>${category.quantity}</td>
                <td>${category.source_items_count} item(s)</td>
            `;
            tableBody.appendChild(row);
        });

        // Update MS Expense preview
        document.getElementById('ms-total').textContent = consolidationData.total_original;
        document.getElementById('ms-itemised').textContent = consolidationData.total_itemized;
        
        const remaining = parseFloat(consolidationData.total_original) - parseFloat(consolidationData.total_itemized);
        document.getElementById('ms-remaining').textContent = remaining.toFixed(2);
    }

    async itemizeExpense() {
        this.showLoading('Creating MS Expense itemization...');

        try {
            const response = await fetch('/api/hotel/itemize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    consolidated_categories: this.consolidatedCategories,
                    invoice_details: this.currentInvoiceData
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data.data);
                this.showResultsSection();
            } else {
                this.showError(data.message || 'Itemization failed');
            }
        } catch (error) {
            console.error('Error itemizing expense:', error);
            this.showError('Error itemizing expense: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displayResults(resultsData) {
        const resultsHtml = `
            <div class="success-icon">✅</div>
            <h3>Itemization Completed Successfully!</h3>
            <p>Created ${resultsData.entries_created} itemization entries in MS Expense</p>
            <p>Total itemized amount: $${resultsData.total_itemized}</p>
            <div class="results-details">
                <p><strong>Next steps:</strong></p>
                <ol>
                    <li>Review the itemized entries in MS Expense</li>
                    <li>Verify all amounts are correct</li>
                    <li>Submit your expense report</li>
                </ol>
            </div>
        `;
        
        document.getElementById('results-summary').innerHTML = resultsHtml;
    }

    showValidationSection() {
        document.getElementById('validation-section').style.display = 'block';
    }

    showConsolidationSection() {
        document.getElementById('consolidation-section').style.display = 'block';
    }

    showResultsSection() {
        document.getElementById('results-section').style.display = 'block';
    }

    showLoading(message) {
        const loadingOverlay = document.getElementById('loading-overlay');
        const loadingText = loadingOverlay.querySelector('.loading-text');
        loadingText.textContent = message;
        loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    }

    showError(message) {
        const errorContainer = document.getElementById('error-container');
        const errorText = document.getElementById('error-text');
        errorText.textContent = message;
        errorContainer.style.display = 'flex';
    }

    dismissError() {
        document.getElementById('error-container').style.display = 'none';
    }

    populateAddItemCategoryDropdown() {
        const categorySelect = document.getElementById('new-category');
        categorySelect.innerHTML = '<option value="">Select Category</option>';
        
        this.categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat.value;
            option.textContent = cat.title;
            categorySelect.appendChild(option);
        });
    }

    isDailyRateCategory(category) {
        const dailyCategories = ['Daily Room Rate'];
        return dailyCategories.includes(category);
    }

    addNewLineItem() {
        const description = document.getElementById('new-description').value.trim();
        const amount = parseFloat(document.getElementById('new-amount').value);
        const date = document.getElementById('new-date').value;
        const category = document.getElementById('new-category').value;

        // Validation
        if (!description || !amount || isNaN(amount) || !date || !category) {
            this.showError('Please fill in all fields for the new line item');
            return;
        }

        if (amount <= 0) {
            this.showError('Amount must be greater than 0');
            return;
        }

        // Add the new item
        const newItem = {
            description: description,
            amount: amount.toFixed(2),
            service_date: date,
            suggested_category: category
        };

        if (!this.currentInvoiceData.line_items) {
            this.currentInvoiceData.line_items = [];
        }

        this.currentInvoiceData.line_items.push(newItem);

        // Update the total
        this.currentInvoiceData.total_amount = (
            parseFloat(this.currentInvoiceData.total_amount || 0) + amount
        ).toFixed(2);

        // Clear the form
        document.getElementById('new-description').value = '';
        document.getElementById('new-amount').value = '';
        document.getElementById('new-date').value = '';
        document.getElementById('new-category').value = '';

        // Refresh the display
        this.displayLineItems(this.currentInvoiceData.line_items);
        this.updateValidationStatus();

        console.log('Added new line item:', newItem);
    }

    removeLineItem(index) {
        if (this.currentInvoiceData && this.currentInvoiceData.line_items) {
            this.currentInvoiceData.line_items.splice(index, 1);
            this.displayLineItems(this.currentInvoiceData.line_items);
            this.updateValidationStatus();
        }
    }

    restart() {
        // Reset all data
        this.currentInvoiceData = null;
        this.consolidatedCategories = [];
        
        // Hide all sections except upload
        document.getElementById('validation-section').style.display = 'none';
        document.getElementById('consolidation-section').style.display = 'none';
        document.getElementById('results-section').style.display = 'none';
        
        // Reset form
        document.getElementById('invoice-file').value = '';
        document.getElementById('original-amount').value = '';
        document.getElementById('extract-btn').disabled = true;
        
        // Reset upload display
        const uploadArea = document.getElementById('upload-area');
        uploadArea.querySelector('h3').textContent = 'Drop your hotel invoice here';
        uploadArea.querySelector('p').textContent = 'Or click to select a PDF file';
    }
}

// Initialize the hotel itemizer when the page loads
let hotelItemizer;
document.addEventListener('DOMContentLoaded', () => {
    hotelItemizer = new HotelItemizer();
});