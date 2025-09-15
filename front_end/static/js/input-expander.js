/**
 * Auto-expanding textarea functionality
 * Makes textarea elements automatically resize to fit their content
 */

class TextareaAutoResize {
    constructor() {
        this.init();
    }

    init() {
        // Use event delegation to handle dynamically created textareas
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('table-input') && e.target.tagName.toLowerCase() === 'textarea') {
                this.autoResize(e.target);
            }
        });

        document.addEventListener('focus', (e) => {
            if (e.target.classList.contains('table-input') && e.target.tagName.toLowerCase() === 'textarea') {
                this.autoResize(e.target);
            }
        });

        // Handle existing textareas when the table is created
        document.addEventListener('expensesTableCreated', () => {
            this.processExistingTextareas();
        });

        // Process any textareas that already exist
        setTimeout(() => {
            this.processExistingTextareas();
        }, 100);
    }

    processExistingTextareas() {
        const textareas = document.querySelectorAll('textarea.table-input');
        console.log('Processing', textareas.length, 'existing textareas');
        textareas.forEach(textarea => {
            this.autoResize(textarea);
        });
    }

    autoResize(textarea) {
        // Reset height to allow proper measurement
        textarea.style.height = 'auto';

        // Calculate the height needed
        const scrollHeight = textarea.scrollHeight;
        const minHeight = 32; // Minimum height (roughly 1.5em)
        const maxHeight = 200; // Maximum height before scrolling

        // Set height based on content, but within bounds
        const newHeight = Math.max(minHeight, Math.min(scrollHeight + 2, maxHeight));

        textarea.style.height = newHeight + 'px';

        // If content exceeds max height, enable scrolling
        if (scrollHeight > maxHeight - 2) {
            textarea.style.overflowY = 'auto';
        } else {
            textarea.style.overflowY = 'hidden';
        }

        // Ensure the parent table cell expands too
        const td = textarea.closest('td');
        if (td) {
            td.style.height = 'auto';
            td.style.verticalAlign = 'top';
        }

        // Ensure the parent table row expands
        const tr = textarea.closest('tr');
        if (tr) {
            tr.style.height = 'auto';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('TextareaAutoResize: Initializing...');
    window.textareaAutoResize = new TextareaAutoResize();
});