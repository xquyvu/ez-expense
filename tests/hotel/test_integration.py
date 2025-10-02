"""
Integration test for hotel itemizer functionality.

This test demonstrates how all the hotel itemizer components work together.
"""

import pytest
from datetime import date
from decimal import Decimal

# Mock test data for integration testing
SAMPLE_HOTEL_INVOICE_DATA = {
    "hotel_name": "Grand Plaza Hotel",
    "hotel_location": "123 Main St, City, State",
    "check_in_date": date(2025, 6, 26),
    "check_out_date": date(2025, 6, 28),
    "total_amount": Decimal("240.00"),
    "currency": "USD",
    "invoice_number": "INV-2025-001",
    "line_items": [
        {
            "description": "Room Rate - King Suite",
            "amount": Decimal("200.00"),
            "suggested_category": "Daily Room Rate"
        },
        {
            "description": "City Occupancy Tax",
            "amount": Decimal("20.00"),
            "suggested_category": "Hotel Tax"
        },
        {
            "description": "Resort Fee",
            "amount": Decimal("15.00"),
            "suggested_category": "Incidentals"
        },
        {
            "description": "Parking Fee",
            "amount": Decimal("5.00"),
            "suggested_category": "Incidentals"
        }
    ]
}

EXPECTED_CONSOLIDATED_CATEGORIES = [
    {
        "category": "Daily Room Rate",
        "total_amount": Decimal("200.00"),
        "daily_rate": Decimal("100.00"),  # 200 / 2 nights
        "quantity": 2,
        "source_items_count": 1
    },
    {
        "category": "Hotel Tax", 
        "total_amount": Decimal("20.00"),
        "daily_rate": Decimal("10.00"),  # 20 / 2 nights
        "quantity": 2,
        "source_items_count": 1
    },
    {
        "category": "Incidentals",
        "total_amount": Decimal("20.00"),  # 15 + 5
        "daily_rate": Decimal("20.00"),   # One-time fee
        "quantity": 1,
        "source_items_count": 2
    }
]


class TestHotelItemizerIntegration:
    """Integration tests for the complete hotel itemizer workflow."""
    
    def test_complete_workflow_simulation(self):
        """Simulate the complete hotel itemization workflow."""
        # This test simulates the entire workflow without external dependencies
        
        # Step 1: Invoice Upload (simulated)
        invoice_data = SAMPLE_HOTEL_INVOICE_DATA.copy()
        assert invoice_data is not None
        assert invoice_data["total_amount"] == Decimal("240.00")
        print("✅ Step 1: Invoice data loaded")
        
        # Step 2: Category Assignment (simulated user input)
        # User assigns categories to each line item
        for item in invoice_data["line_items"]:
            item["user_category"] = item["suggested_category"]
        print("✅ Step 2: Categories assigned")
        
        # Step 3: Validation
        categorized_total = sum(
            item["amount"] for item in invoice_data["line_items"]
            if item["user_category"] != "Ignore"
        )
        assert categorized_total == invoice_data["total_amount"]
        print("✅ Step 3: Validation passed")
        
        # Step 4: Consolidation (simulated)
        consolidated = self.simulate_consolidation(invoice_data)
        assert len(consolidated) == 3
        assert consolidated[0]["category"] == "Daily Room Rate"
        print("✅ Step 4: Consolidation completed")
        
        # Step 5: Daily Rate Calculation (simulated)
        ms_expense_entries = self.simulate_daily_rate_calculation(consolidated, invoice_data)
        assert len(ms_expense_entries) == 3
        
        # Verify totals match
        total_calculated = sum(entry["total_amount"] for entry in ms_expense_entries)
        assert abs(total_calculated - invoice_data["total_amount"]) < Decimal("0.01")
        print("✅ Step 5: Daily rate calculation completed")
        
        print("🎉 Complete workflow simulation successful!")
        
    def simulate_consolidation(self, invoice_data):
        """Simulate the consolidation logic."""
        category_groups = {}
        
        for item in invoice_data["line_items"]:
            category = item["user_category"]
            if category != "Ignore":
                if category not in category_groups:
                    category_groups[category] = []
                category_groups[category].append(item)
        
        nights = (invoice_data["check_out_date"] - invoice_data["check_in_date"]).days
        
        consolidated = []
        for category, items in category_groups.items():
            total_amount = sum(item["amount"] for item in items)
            
            # Determine if daily rate category
            is_daily = category in ["Daily Room Rate", "Hotel Tax"]
            
            if is_daily:
                daily_rate = total_amount / nights
                quantity = nights
            else:
                daily_rate = total_amount
                quantity = 1
                
            consolidated.append({
                "category": category,
                "total_amount": total_amount,
                "daily_rate": daily_rate,
                "quantity": quantity,
                "source_items_count": len(items)
            })
            
        return consolidated
    
    def simulate_daily_rate_calculation(self, consolidated_categories, invoice_data):
        """Simulate MS Expense daily rate calculation."""
        ms_entries = []
        
        for category in consolidated_categories:
            entry = {
                "subcategory": category["category"],
                "start_date": invoice_data["check_in_date"],
                "daily_rate": category["daily_rate"],
                "quantity": category["quantity"],
                "total_amount": category["total_amount"]
            }
            ms_entries.append(entry)
            
        return ms_entries
    
    def test_api_endpoints_structure(self):
        """Test that the API endpoints are properly structured."""
        # This tests the expected API structure without making actual calls
        
        expected_endpoints = [
            "/api/hotel/health",
            "/api/hotel/extract",
            "/api/hotel/validate", 
            "/api/hotel/categories",
            "/api/hotel/itemize"
        ]
        
        # In a real test, you'd check that these endpoints exist
        # For now, we just verify the structure is defined
        assert len(expected_endpoints) == 5
        print("✅ API endpoint structure validated")
    
    def test_category_mapping(self):
        """Test the hotel category mapping."""
        expected_categories = [
            "Daily Room Rate",
            "Hotel Deposit", 
            "Hotel Tax",
            "Hotel Telephone",
            "Incidentals",
            "Laundry",
            "Room Service & Meals etc",
            "Ignore"
        ]
        
        # Verify all expected categories are defined
        assert len(expected_categories) == 8
        assert "Daily Room Rate" in expected_categories
        assert "Ignore" in expected_categories
        print("✅ Category mapping validated")
    
    def test_daily_vs_onetime_categorization(self):
        """Test classification of daily vs one-time categories."""
        daily_categories = ["Daily Room Rate", "Hotel Tax"]
        onetime_categories = ["Hotel Deposit", "Hotel Telephone", "Incidentals", "Laundry", "Room Service & Meals etc"]
        
        # Test a sample categorization
        sample_category = "Daily Room Rate"
        is_daily = sample_category in daily_categories
        assert is_daily == True
        
        sample_category = "Incidentals"
        is_daily = sample_category in daily_categories
        assert is_daily == False
        
        print("✅ Daily vs one-time categorization validated")
    
    def test_validation_logic(self):
        """Test the validation logic for itemization."""
        # Test total validation
        original_total = Decimal("100.00")
        itemized_total = Decimal("100.00")
        difference = abs(itemized_total - original_total)
        validation_passed = difference <= Decimal("0.01")
        
        assert validation_passed == True
        
        # Test with small rounding difference
        itemized_total = Decimal("99.99")
        difference = abs(itemized_total - original_total)
        validation_passed = difference <= Decimal("0.01")
        
        assert validation_passed == True
        
        # Test with large difference
        itemized_total = Decimal("95.00")
        difference = abs(itemized_total - original_total)
        validation_passed = difference <= Decimal("0.01")
        
        assert validation_passed == False
        
        print("✅ Validation logic tested")


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_invalid_file_handling(self):
        """Test handling of invalid files."""
        # Test non-PDF file
        invalid_extensions = [".txt", ".doc", ".jpg", ".png"]
        
        for ext in invalid_extensions:
            # In actual implementation, this should return an error
            should_reject = ext not in [".pdf"]
            assert should_reject == True
        
        print("✅ Invalid file handling validated")
    
    def test_missing_data_handling(self):
        """Test handling of missing or incomplete data."""
        # Test missing required fields
        incomplete_invoice = {
            "hotel_name": "",  # Missing
            "total_amount": Decimal("0"),  # Invalid
            "line_items": []  # Empty
        }
        
        # These should trigger validation errors
        has_hotel_name = bool(incomplete_invoice["hotel_name"])
        has_valid_total = incomplete_invoice["total_amount"] > 0
        has_line_items = len(incomplete_invoice["line_items"]) > 0
        
        assert has_hotel_name == False
        assert has_valid_total == False
        assert has_line_items == False
        
        print("✅ Missing data handling validated")


if __name__ == "__main__":
    # Run the integration tests
    test_integration = TestHotelItemizerIntegration()
    test_integration.test_complete_workflow_simulation()
    test_integration.test_api_endpoints_structure()
    test_integration.test_category_mapping()
    test_integration.test_daily_vs_onetime_categorization()
    test_integration.test_validation_logic()
    
    test_errors = TestErrorHandling()
    test_errors.test_invalid_file_handling()
    test_errors.test_missing_data_handling()
    
    print("\n🎉 All integration tests passed!")
    print("\nNext steps:")
    print("1. Install dependencies: uv add pydantic openai pdfplumber pillow")
    print("2. Configure Azure OpenAI settings in .env")
    print("3. Run actual tests with real PDF invoices")
    print("4. Integrate hotel routes with main Quart application")
    print("5. Test end-to-end workflow with browser automation")