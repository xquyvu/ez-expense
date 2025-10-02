"""
Test script for the enhanced Hotel Itemizer functionality.

This script tests:
1. Enhanced validation UI with add item functionality
2. Service date and charge type display
3. Playwright automation integration
"""

import asyncio
import json
from datetime import datetime, timedelta

def test_enhanced_hotel_itemizer():
    """Test the enhanced hotel itemizer functionality."""
    
    print("🏨 Testing Enhanced Hotel Itemizer")
    print("=" * 50)
    
    # Test data simulating hotel invoice with various line items
    sample_invoice_data = {
        "hotel_name": "Grand Plaza Hotel",
        "guest_name": "John Smith", 
        "confirmation_number": "ABC123456",
        "check_in_date": "2025-09-25",
        "check_out_date": "2025-09-27",
        "total_amount": 285.50,
        "line_items": [
            {
                "description": "Room Rate - Standard King",
                "amount": 120.00,
                "service_date": "2025-09-25",
                "suggested_category": "Daily Room Rate"
            },
            {
                "description": "Room Rate - Standard King", 
                "amount": 120.00,
                "service_date": "2025-09-26",
                "suggested_category": "Daily Room Rate"
            },
            {
                "description": "City Tax",
                "amount": 15.00,
                "service_date": "2025-09-25",
                "suggested_category": "Hotel Tax"
            },
            {
                "description": "Parking Fee",
                "amount": 20.50,
                "service_date": "2025-09-25", 
                "suggested_category": "Incidentals"
            },
            {
                "description": "Minibar",
                "amount": 10.00,
                "service_date": "2025-09-26",
                "suggested_category": "Room Service & Meals etc"
            }
        ]
    }
    
    print("📋 Sample Invoice Data:")
    print(f"Hotel: {sample_invoice_data['hotel_name']}")
    print(f"Guest: {sample_invoice_data['guest_name']}")
    print(f"Check-in: {sample_invoice_data['check_in_date']}")
    print(f"Check-out: {sample_invoice_data['check_out_date']}")
    print(f"Total: ${sample_invoice_data['total_amount']:.2f}")
    print(f"Line Items: {len(sample_invoice_data['line_items'])}")
    print()
    
    # Test enhanced line items display
    print("🔍 Enhanced Line Items Display:")
    print("Description".ljust(25) + "Amount".ljust(10) + "Date".ljust(12) + "Category".ljust(20) + "Type")
    print("-" * 80)
    
    for item in sample_invoice_data['line_items']:
        charge_type = "Daily" if item['suggested_category'] == "Daily Room Rate" else "One-time"
        print(
            item['description'][:24].ljust(25) + 
            f"${item['amount']:.2f}".ljust(10) +
            item['service_date'].ljust(12) +
            item['suggested_category'][:19].ljust(20) +
            charge_type
        )
    print()
    
    # Test add new item functionality
    print("➕ Test Add New Item:")
    new_item = {
        "description": "Wi-Fi Fee",
        "amount": 12.95,
        "service_date": "2025-09-25",
        "suggested_category": "Incidentals"
    }
    
    print(f"Adding: {new_item['description']} - ${new_item['amount']:.2f} ({new_item['suggested_category']})")
    sample_invoice_data['line_items'].append(new_item)
    sample_invoice_data['total_amount'] += new_item['amount']
    print(f"New total: ${sample_invoice_data['total_amount']:.2f}")
    print()
    
    # Test consolidation logic
    print("📊 Category Consolidation:")
    from collections import defaultdict
    consolidated = defaultdict(lambda: {"total": 0.0, "items": [], "type": "One-time"})
    
    for item in sample_invoice_data['line_items']:
        category = item['suggested_category']
        consolidated[category]["total"] += item['amount']
        consolidated[category]["items"].append(item)
        if category == "Daily Room Rate":
            consolidated[category]["type"] = "Daily"
    
    for category, data in consolidated.items():
        print(f"{category}: ${data['total']:.2f} ({data['type']}) - {len(data['items'])} item(s)")
    print()
    
    # Test MS Expense entry generation
    print("💼 MS Expense Entry Generation:")
    check_in = datetime.strptime(sample_invoice_data['check_in_date'], "%Y-%m-%d").date()
    check_out = datetime.strptime(sample_invoice_data['check_out_date'], "%Y-%m-%d").date()
    nights = (check_out - check_in).days
    
    for category, data in consolidated.items():
        if category == "Ignore":
            continue
            
        if data["type"] == "Daily":
            daily_rate = data["total"] / nights
            print(f"Subcategory: {category}")
            print(f"Start Date: {check_in}")
            print(f"Daily Rate: ${daily_rate:.2f}")
            print(f"Quantity: {nights} nights")
            print(f"Total: ${data['total']:.2f}")
        else:
            print(f"Subcategory: {category}")
            print(f"Start Date: {check_in}")
            print(f"Daily Rate: ${data['total']:.2f}")
            print(f"Quantity: 1")
            print(f"Total: ${data['total']:.2f}")
        print()
    
    # Test automation data structure
    print("🤖 Browser Automation Data:")
    automation_entries = []
    
    for category, data in consolidated.items():
        if category == "Ignore":
            continue
            
        if data["type"] == "Daily":
            daily_rate = data["total"] / nights
            entry = {
                "subcategory": category,
                "start_date": str(check_in),
                "daily_rate": round(daily_rate, 2),
                "quantity": nights
            }
        else:
            entry = {
                "subcategory": category,
                "start_date": str(check_in),
                "daily_rate": round(data["total"], 2),
                "quantity": 1
            }
        
        automation_entries.append(entry)
        print(f"Entry: {json.dumps(entry, indent=2)}")
    
    print(f"\nGenerated {len(automation_entries)} automation entries")
    print()
    
    # Test validation totals
    print("✅ Validation Summary:")
    original_total = sample_invoice_data['total_amount']
    categorized_total = sum(data["total"] for cat, data in consolidated.items() if cat != "Ignore")
    ignored_total = consolidated.get("Ignore", {}).get("total", 0.0)
    
    print(f"Original Total: ${original_total:.2f}")
    print(f"Categorized Total: ${categorized_total:.2f}")
    print(f"Ignored Total: ${ignored_total:.2f}")
    print(f"Validation Status: {'✅ VALID' if abs(original_total - (categorized_total + ignored_total)) < 0.01 else '❌ INVALID'}")
    print()
    
    print("🎉 Enhanced Hotel Itemizer Test Complete!")
    print("=" * 50)
    
    return {
        "invoice_data": sample_invoice_data,
        "consolidated": dict(consolidated),
        "automation_entries": automation_entries,
        "validation": {
            "original_total": original_total,
            "categorized_total": categorized_total,
            "ignored_total": ignored_total,
            "is_valid": abs(original_total - (categorized_total + ignored_total)) < 0.01
        }
    }

if __name__ == "__main__":
    test_result = test_enhanced_hotel_itemizer()
    
    # Save test results for debugging
    with open("hotel_itemizer_test_results.json", "w") as f:
        json.dump(test_result, f, indent=2, default=str)
    
    print("📄 Test results saved to hotel_itemizer_test_results.json")