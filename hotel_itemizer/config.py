"""
Configuration for Hotel Itemizer functionality.

This module contains hotel-specific configurations, categories,
and AI prompts for invoice processing.
"""

# Hotel expense categories as specified in MS Expense
HOTEL_CATEGORIES = [
    {"title": "Daily Room Rate", "value": "Daily Room Rate"},
    {"title": "Hotel Deposit", "value": "Hotel Deposit"}, 
    {"title": "Hotel Tax", "value": "Hotel Tax"},
    {"title": "Hotel Telephone", "value": "Hotel Telephone"},
    {"title": "Incidentals", "value": "Incidentals"},
    {"title": "Laundry", "value": "Laundry"},
    {"title": "Room Service & Meals etc", "value": "Room Service & Meals etc"},
    {"title": "Ignore", "value": "Ignore"}
]

# Categories that are charged daily (need quantity calculation)
DAILY_RATE_CATEGORIES = {
    "Daily Room Rate"
}

# Categories that are one-time charges
ONE_TIME_CATEGORIES = {
    "Hotel Deposit", 
    "Hotel Tax",
    "Hotel Telephone",
    "Incidentals",
    "Laundry",
    "Room Service & Meals etc"
}

# AI prompt for invoice extraction
HOTEL_EXTRACTION_PROMPT = """
You are an expert at extracting information from hotel invoices and receipts.

Please extract the following information from the provided hotel invoice:

1. **Basic Information:**
   - Hotel name
   - Guest name
   - Confirmation/reservation number
   - Check-in date (format: YYYY-MM-DD)
   - Check-out date (format: YYYY-MM-DD)
   - Total amount

2. **Line Items:** For each charge on the invoice, extract:
   - Description of the charge
   - Amount (as decimal number)
   - Date of service (format: YYYY-MM-DD)
   - Suggested category from these options:
     * Daily Room Rate
     * Hotel Deposit
     * Hotel Tax
     * Hotel Telephone
     * Incidentals
     * Laundry
     * Room Service & Meals etc
     * Ignore

**Important Guidelines:**
- For room charges, use "Daily Room Rate" category
- For taxes (city tax, occupancy tax, VAT, etc.), use "Hotel Tax"
- For deposits, use "Hotel Deposit"
- For telephone calls, use "Hotel Telephone"
- For laundry services, use "Laundry"
- For room service, minibar, restaurant charges, use "Room Service & Meals etc"
- For other hotel services (spa, parking, etc.), use "Incidentals"
- For unclear or irrelevant charges, use "Ignore"

Return the information in valid JSON format with the exact structure expected.
"""

# AI prompt for category validation and suggestions
HOTEL_CATEGORIZATION_PROMPT = """
You are an expert at categorizing hotel expenses for business expense reporting.

Given this hotel line item, please:
1. Validate if the suggested category is appropriate
2. Provide the best category if the suggestion is incorrect
3. Indicate if this should be a daily charge or one-time charge

Line item: {description} - ${amount}
Current suggested category: {suggested_category}

Available categories:
- Daily Room Rate (daily charge)
- Hotel Deposit (one-time)
- Hotel Tax (one-time) 
- Hotel Telephone (one-time)
- Incidentals (one-time)
- Laundry (one-time)
- Room Service & Meals etc (one-time)
- Ignore (exclude from expenses)

Please respond with:
1. Is the suggested category correct? (Yes/No)
2. If no, what is the best category?
3. Is this a daily or one-time charge?
4. Brief explanation of your reasoning
"""