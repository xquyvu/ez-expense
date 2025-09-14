/**
 * Column Configuration for EZ Expense Table
 * Defines width and display settings for table columns
 */

const COLUMN_CONFIG = {
    // Default column widths (in pixels)
    defaultWidth: 150,

    // Specific column widths - customize these as needed
    columnWidths: {
        // Common expense fields
        'Date': 130,
        'Amount': 110,
        'Expense category': 120,
        'Merchant': 120,
        'Payment method': 100,
        'Receipts attached': 100,

        // Special columns
        'Receipts': 250  // This is handled separately as sticky column
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
    }
};

// Export for use in main app
if (typeof module !== 'undefined' && module.exports) {
    module.exports = COLUMN_CONFIG;
} else if (typeof window !== 'undefined') {
    window.COLUMN_CONFIG = COLUMN_CONFIG;
}