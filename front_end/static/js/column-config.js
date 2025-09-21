/**
 * Column Configuration for EZ Expense Table
 * Defines width and display settings for table columns
 */

const COLUMN_CONFIG = {
    // Default column widths (in pixels)
    defaultWidth: 150,

    // Column display name mapping - maps internal column names to display names
    displayNames: {
        'Additional information': 'Expense Description',
        // Add more mappings here as needed
    },

    // Specific column widths - customize these as needed
    columnWidths: {
        // Special columns
        'Select': 50,  // Checkbox column

        // Common expense fields
        'Date': 130,
        'Amount': 135,
        'Expense category': 140,
        'Merchant': 120,
        'Payment method': 110,
        'Receipts attached': 110,

        // Special columns
        'Receipts': 280  // This is handled separately as sticky column
    },

    // Minimum column width
    minWidth: 80,

    // Maximum column width
    maxWidth: 400,

    // Whether to auto-resize columns based on content
    autoResize: false,

    // Padding for auto-resize calculation
    autoResizePadding: 20,

    // Header text behavior
    headerConfig: {
        centerText: true,
        allowWrapping: true,
        maxLines: 3,  // Maximum number of lines for wrapped headers
        allowReordering: true,  // Enable drag and drop column reordering
        allowSorting: true  // Enable column sorting functionality
    },

    // Autocomplete configuration
    autocompleteConfig: {
        maxDropdownWidth: 400,  // Maximum width for autocomplete dropdowns in pixels
        minDropdownWidth: 250,  // Minimum width for autocomplete dropdowns in pixels
        allowExtendBeyondColumn: true  // Allow dropdown to extend beyond column boundaries
    },

    // Editable columns configuration
    // Only these columns can be edited by the user
    editableColumns: [
        'Additional information',
        'Date',
        'Amount',
        'Expense category',
        'Merchant'
    ],

    // Get display name for a column (returns original name if no mapping exists)
    getDisplayName(columnName) {
        return this.displayNames[columnName] || columnName;
    }
};

// Export for use in main app
if (typeof module !== 'undefined' && module.exports) {
    module.exports = COLUMN_CONFIG;
} else if (typeof window !== 'undefined') {
    window.COLUMN_CONFIG = COLUMN_CONFIG;
}