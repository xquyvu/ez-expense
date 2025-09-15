/**
 * Autocomplete functionality for expense categories
 * Provides dropdown suggestions with filtering and debounced updates
 */

class CategoryAutocomplete {
    constructor() {
        this.categories = [];
        this.currentInput = null;
        this.currentDropdown = null;
        this.searchTimeout = null;
        this.scrollListener = null; // Track scroll listener for cleanup
        this.scrollContainers = null; // Track scroll containers for cleanup
        this.SEARCH_DELAY = 200; // 0.2 seconds as requested

        this.init();
    }

    async init() {
        console.log('CategoryAutocomplete: Initializing...');

        // Load categories from the API
        await this.loadCategories();
        console.log('CategoryAutocomplete: Categories loaded:', this.categories.length);

        // Set up event delegation for dynamically created input fields
        this.setupEventDelegation();
        console.log('CategoryAutocomplete: Event delegation setup complete');
    }

    async loadCategories() {
        try {
            const response = await fetch('/api/expenses/categories');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.categories = data.categories || [];
            console.log(`Loaded ${this.categories.length} categories for autocomplete`);
        } catch (error) {
            console.error('Failed to load categories:', error);
            this.categories = [];
        }
    }

    setupEventDelegation() {
        // Use event delegation to handle dynamically created inputs
        document.addEventListener('click', (e) => {
            // Close dropdown if clicking outside
            if (!e.target.closest('.autocomplete-container')) {
                this.hideDropdown();
            }
        });

        document.addEventListener('input', (e) => {
            if (this.isExpenseCategoryInput(e.target)) {
                this.handleInput(e.target);
            }
        });

        document.addEventListener('focus', (e) => {
            console.log('CategoryAutocomplete: Focus event on:', e.target);
            if (this.isExpenseCategoryInput(e.target)) {
                console.log('CategoryAutocomplete: Focus on expense category input detected');
                this.handleFocus(e.target);
            }
        }, true); // Use capture phase

        document.addEventListener('blur', (e) => {
            if (this.isExpenseCategoryInput(e.target)) {
                // Delay hiding to allow for dropdown clicks
                setTimeout(() => this.handleBlur(e.target), 150);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (this.isExpenseCategoryInput(e.target)) {
                this.handleKeydown(e);
            }
        });
    }

    isExpenseCategoryInput(element) {
        const result = element.tagName === 'INPUT' &&
            element.dataset.field === 'Expense category';
        if (element.tagName === 'INPUT') {
            console.log('CategoryAutocomplete: Input field detected:', {
                tag: element.tagName,
                dataField: element.dataset.field,
                isExpenseCategory: result
            });
        }
        return result;
    }

    handleInput(input) {
        console.log('CategoryAutocomplete: Handle input called for:', input.dataset.field);
        this.currentInput = input;

        // Ensure autocomplete container exists
        this.setupAutocompleteContainer(input);

        // Clear existing timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        // Set new timeout for debounced search
        this.searchTimeout = setTimeout(() => {
            this.showDropdown(input);
        }, this.SEARCH_DELAY);
    }

    handleFocus(input) {
        console.log('CategoryAutocomplete: handleFocus called for input:', input.value);
        this.currentInput = input;
        this.setupAutocompleteContainer(input);
        console.log('CategoryAutocomplete: About to call showDropdown...');
        this.showDropdown(input);
        console.log('CategoryAutocomplete: showDropdown call completed');
    }

    handleBlur(input) {
        // Only hide if we're not interacting with the dropdown
        if (!this.currentDropdown || !this.currentDropdown.matches(':hover')) {
            this.hideDropdown();
        }
    }

    handleKeydown(e) {
        if (!this.currentDropdown) return;

        const items = this.currentDropdown.querySelectorAll('.autocomplete-item');
        const currentActive = this.currentDropdown.querySelector('.autocomplete-item.active');
        let activeIndex = -1;

        if (currentActive) {
            activeIndex = Array.from(items).indexOf(currentActive);
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                this.setActiveItem(items, activeIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                activeIndex = Math.max(activeIndex - 1, -1);
                this.setActiveItem(items, activeIndex);
                break;
            case 'Enter':
                e.preventDefault();
                if (currentActive) {
                    this.selectCategory(currentActive.textContent);
                }
                break;
            case 'Escape':
                this.hideDropdown();
                break;
        }
    }

    setupAutocompleteContainer(input) {
        console.log('CategoryAutocomplete: Setting up container for input:', input);

        // Check if container already exists
        let container = input.closest('.autocomplete-container');
        if (container) {
            console.log('CategoryAutocomplete: Container already exists');
            return;
        }

        // Create autocomplete container
        container = document.createElement('div');
        container.className = 'autocomplete-container';

        console.log('CategoryAutocomplete: Creating new container');

        // Wrap the input with the container
        input.parentNode.insertBefore(container, input);
        container.appendChild(input);

        console.log('CategoryAutocomplete: Container created and input wrapped');
    }

    showDropdown(input) {
        console.log('CategoryAutocomplete: showDropdown called for input:', input.value);

        // For focus events, show all categories; for typing, filter them
        const query = input.value.toLowerCase().trim();
        const categoriesToShow = query ? this.filterCategories(query) : this.categories.slice(0, 10);
        console.log('CategoryAutocomplete: Showing categories:', categoriesToShow.length, categoriesToShow.slice(0, 3));

        // Hide existing dropdown
        this.hideDropdown();

        if (categoriesToShow.length === 0) {
            console.log('CategoryAutocomplete: No categories to show, returning early');
            return;
        }

        // Ensure autocomplete container exists
        this.setupAutocompleteContainer(input);

        // Create dropdown
        console.log('CategoryAutocomplete: Creating dropdown...');
        this.currentDropdown = document.createElement('div');
        this.currentDropdown.className = 'autocomplete-dropdown';

        // Add inline styles with modern, pleasant colors
        this.currentDropdown.style.backgroundColor = '#ffffff';
        this.currentDropdown.style.border = '1px solid #e2e8f0';
        this.currentDropdown.style.borderRadius = '8px';
        this.currentDropdown.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.1)';
        this.currentDropdown.style.maxHeight = '200px';
        this.currentDropdown.style.overflowY = 'auto';
        this.currentDropdown.style.fontSize = '14px';
        this.currentDropdown.style.display = 'block';
        this.currentDropdown.style.backdropFilter = 'blur(8px)';
        this.currentDropdown.style.borderTop = '2px solid #3b82f6';

        categoriesToShow.forEach((category, index) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.style.padding = '12px 16px';
            item.style.cursor = 'pointer';
            item.style.borderBottom = index < categoriesToShow.length - 1 ? '1px solid #f1f5f9' : 'none';
            item.style.whiteSpace = 'nowrap';
            item.style.overflow = 'hidden';
            item.style.textOverflow = 'ellipsis';
            item.style.transition = 'all 0.15s ease-in-out';
            item.style.backgroundColor = 'white'; // Default white background
            item.style.color = '#374151';
            item.style.fontSize = '14px';
            item.style.fontWeight = '500';
            item.title = category; // Show full text on hover

            // Set text content with highlighting if there's a query
            const query = input.value.toLowerCase().trim();
            if (query) {
                const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
                item.innerHTML = category.replace(regex, '<span style="color: #2563eb; font-weight: bold;">$1</span>');
            } else {
                item.textContent = category;
            }

            item.addEventListener('mouseenter', () => {
                // Remove active class from all items first
                const allItems = this.currentDropdown.querySelectorAll('.autocomplete-item');
                allItems.forEach(i => {
                    i.classList.remove('active');
                    i.style.backgroundColor = 'white';
                });
                // Set this item as active
                item.classList.add('active');
                item.style.backgroundColor = '#e3f2fd'; // Light blue on hover
            });

            item.addEventListener('mouseleave', () => {
                // Check if item should remain active (keyboard navigation might have set it)
                if (item.classList.contains('active')) {
                    item.style.backgroundColor = '#e3f2fd'; // Keep active styling
                } else {
                    item.style.backgroundColor = 'white'; // White when not active
                }
            });

            item.addEventListener('click', () => {
                this.selectCategory(category);
            });

            this.currentDropdown.appendChild(item);
        });

        // Position and show dropdown
        console.log('CategoryAutocomplete: Appending dropdown to body for fixed positioning');
        document.body.appendChild(this.currentDropdown);

        // Position dropdown
        this.positionDropdown(input);

        // Add scroll listener to reposition dropdown
        this.addScrollListener(input);

        // Debug: Check if dropdown is in DOM and visible
        console.log('CategoryAutocomplete: Dropdown in DOM:', document.contains(this.currentDropdown));
        console.log('CategoryAutocomplete: Dropdown element:', this.currentDropdown);
        console.log('CategoryAutocomplete: Dropdown styles:', {
            display: this.currentDropdown.style.display,
            position: this.currentDropdown.style.position,
            top: this.currentDropdown.style.top,
            left: this.currentDropdown.style.left,
            width: this.currentDropdown.style.width,
            zIndex: this.currentDropdown.style.zIndex
        });

        // Force a visible test dropdown
        setTimeout(() => {
            if (this.currentDropdown) {
                this.currentDropdown.style.backgroundColor = 'white';
                this.currentDropdown.style.border = '2px solid blue';
                console.log('CategoryAutocomplete: Applied test styles to make dropdown more visible');
            }
        }, 100);

        console.log('CategoryAutocomplete: Dropdown positioned and should be visible');
    }

    hideDropdown() {
        if (this.currentDropdown) {
            this.currentDropdown.remove();
            this.currentDropdown = null;
        }
        this.removeScrollListener(); // Clean up scroll listener
        this.currentInput = null;
    }

    addScrollListener(input) {
        // Remove existing listener if any
        this.removeScrollListener();

        // Store the input reference for the scroll listener
        this.scrollTargetInput = input;

        // Create new scroll listener - simple and universal
        this.scrollListener = (event) => {
            console.log('🔄 SCROLL EVENT DETECTED:', event?.target?.tagName || 'no-target', event?.target?.className || 'no-class');
            console.log('🔍 Dropdown exists:', !!this.currentDropdown);
            console.log('🔍 Scroll target input:', !!this.scrollTargetInput);

            if (this.currentDropdown && this.scrollTargetInput) {
                console.log('📍 Repositioning dropdown...');
                this.positionDropdown(this.scrollTargetInput);
            } else {
                console.log('❌ No dropdown or scroll target input');
                if (!this.currentDropdown) console.log('   - No dropdown');
                if (!this.scrollTargetInput) console.log('   - No scroll target input');
            }
        };

        // Listen to ALL scroll events on the entire document
        // This catches scroll events from any element, anywhere
        document.addEventListener('scroll', this.scrollListener, {
            passive: true,
            capture: true  // Capture phase catches events before they bubble
        });

        // Also listen on window for good measure
        window.addEventListener('scroll', this.scrollListener, { passive: true });

        console.log('✅ CategoryAutocomplete: Added universal scroll listeners');
        console.log('🔍 Input stored:', !!input);
        console.log('🔍 Dropdown exists at setup:', !!this.currentDropdown);
    }

    removeScrollListener() {
        if (this.scrollListener) {
            document.removeEventListener('scroll', this.scrollListener, { capture: true });
            window.removeEventListener('scroll', this.scrollListener);
            this.scrollListener = null;
            this.scrollTargetInput = null; // Clean up the input reference
        }
    }

    filterCategories(query) {
        console.log('CategoryAutocomplete: filterCategories called with query:', query);

        if (!query) {
            console.log('CategoryAutocomplete: No query, returning first 10 categories');
            return this.categories.slice(0, 10); // Show first 10 items when no query
        }

        const filtered = this.categories
            .filter(category =>
                category.toLowerCase().includes(query)
            )
            .sort((a, b) => {
                // Prioritize categories that start with the query
                const aStarts = a.toLowerCase().startsWith(query);
                const bStarts = b.toLowerCase().startsWith(query);

                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;

                return a.localeCompare(b);
            })
            .slice(0, 10); // Limit to 10 results

        console.log('CategoryAutocomplete: Filtered results:', filtered.length, filtered.slice(0, 3));
        return filtered;
    }

    setActiveItem(items, activeIndex) {
        // Remove active class from all items and reset background
        items.forEach(item => {
            item.classList.remove('active');
            item.style.backgroundColor = 'white'; // Reset to default
        });

        // Add active class to selected item and set background
        if (activeIndex >= 0 && activeIndex < items.length) {
            items[activeIndex].classList.add('active');
            items[activeIndex].style.backgroundColor = '#e3f2fd'; // Light blue for active state
            items[activeIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    selectCategory(category) {
        console.log('CategoryAutocomplete: Selecting category:', category);

        // Use the current input or the scroll target input as fallback
        const targetInput = this.currentInput || this.scrollTargetInput;

        if (targetInput) {
            console.log('CategoryAutocomplete: Setting input value to:', category);
            targetInput.value = category;

            // Trigger multiple events to ensure table updates
            const inputEvent = new Event('input', { bubbles: true });
            const changeEvent = new Event('change', { bubbles: true });
            const blurEvent = new Event('blur', { bubbles: true });

            targetInput.dispatchEvent(inputEvent);
            targetInput.dispatchEvent(changeEvent);
            targetInput.dispatchEvent(blurEvent);

            console.log('CategoryAutocomplete: Events dispatched, new value:', targetInput.value);
        } else {
            console.error('CategoryAutocomplete: No target input found for selection');
        }

        this.hideDropdown();
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    positionDropdown(input) {
        if (!this.currentDropdown) return;

        console.log('CategoryAutocomplete: Positioning dropdown...');

        // Use fixed positioning for clean layering
        this.currentDropdown.style.position = 'fixed';
        this.currentDropdown.style.zIndex = '9999';

        const inputRect = input.getBoundingClientRect();

        // Get autocomplete configuration
        const config = window.COLUMN_CONFIG?.autocompleteConfig || {
            maxDropdownWidth: 300,
            minDropdownWidth: 150,
            allowExtendBeyondColumn: true
        };

        // Calculate dropdown width
        let dropdownWidth = inputRect.width;

        if (config.allowExtendBeyondColumn) {
            dropdownWidth = Math.max(config.minDropdownWidth, inputRect.width);
            dropdownWidth = Math.min(dropdownWidth, config.maxDropdownWidth);
        }

        // Position relative to viewport
        let top = inputRect.bottom + 2;
        let left = inputRect.left;

        // Adjust left position if dropdown would go off-screen
        const viewportWidth = window.innerWidth;
        if (left + dropdownWidth > viewportWidth) {
            left = Math.max(0, viewportWidth - dropdownWidth - 10);
        }

        this.currentDropdown.style.top = `${top}px`;
        this.currentDropdown.style.left = `${left}px`;
        this.currentDropdown.style.width = `${dropdownWidth}px`;
        this.currentDropdown.style.maxHeight = '200px';
        this.currentDropdown.style.overflowY = 'auto';

        console.log('CategoryAutocomplete: Dropdown positioned at:', { top, left, width: dropdownWidth });
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// Initialize autocomplete when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('CategoryAutocomplete: DOM loaded, initializing...');
    window.categoryAutocomplete = new CategoryAutocomplete();
});

// Also initialize when expenses table is dynamically created
document.addEventListener('expensesTableCreated', () => {
    if (window.categoryAutocomplete) {
        // Re-setup event delegation for new inputs
        console.log('Expenses table created, autocomplete ready for new inputs');

        // Debug: Check if there are any expense category inputs in the table
        const expenseCategoryInputs = document.querySelectorAll('input[data-field="Expense category"]');
        console.log('CategoryAutocomplete: Found', expenseCategoryInputs.length, 'expense category inputs');

        expenseCategoryInputs.forEach((input, index) => {
            console.log(`CategoryAutocomplete: Input ${index}:`, input.dataset.field, input.value);
        });
    }
});