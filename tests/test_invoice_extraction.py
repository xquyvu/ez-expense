#!/usr/bin/env python3
"""
Test script for invoice extraction functionality.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from invoice_extractor import extract_invoice_details


@pytest.mark.asyncio
async def test_extract_invoice_details():
    """Test the invoice extraction with different scenarios."""

    print("Testing invoice extraction functionality...")

    # Test 1: No file path provided (should return mock data)
    print("\n1. Testing with no file path (mock data):")
    result = await extract_invoice_details()
    print(f"Result: {result}")

    # Test 2: Non-existent file path
    print("\n2. Testing with non-existent file:")
    result = await extract_invoice_details("non_existent_file.pdf")
    print(f"Result: {result}")

    # Test 3: Check if we have any actual receipt files to test with
    receipts_dir = Path("input_data/receipts")
    if receipts_dir.exists():
        receipt_files = (
            list(receipts_dir.glob("*.pdf"))
            + list(receipts_dir.glob("*.jpg"))
            + list(receipts_dir.glob("*.png"))
        )

        if receipt_files:
            print(f"\n3. Testing with actual receipt file: {receipt_files[0]}")
            result = await extract_invoice_details(str(receipt_files[0]))
            if result == {}:
                print(
                    "Result: {} (empty - either Azure OpenAI not configured or extraction failed)"
                )
            else:
                print(f"Result: {result}")
        else:
            print("\n3. No receipt files found in input_data/receipts/")
    else:
        print("\n3. input_data/receipts/ directory not found")

    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(test_extract_invoice_details())
