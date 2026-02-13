#!/usr/bin/env python3
"""Quick script to test local OCR + LLM extraction on real receipts."""

import asyncio
import json
import time

import local_model_manager
from invoice_extractor import (
    _build_extraction_prompt,
    _extract_with_local,
    _ocr_image,
    _parse_local_llm_response,
    pdf_to_images,
)
from PIL import Image

RECEIPT_FILES = [
    "/Users/quyvu/Desktop/receipts/amazon_invoice.pdf",
    "/Users/quyvu/Desktop/receipts/Medium_invoice.pdf",
    "/Users/quyvu/Desktop/receipts/WOB_invoice.png",
]


def get_ocr_text(file_path):
    if file_path.endswith(".pdf"):
        images = pdf_to_images(file_path)
    else:
        images = [Image.open(file_path)]
    texts = [_ocr_image(img) for img in images]
    return "\n\n".join(t for t in texts if t)


def test_raw_llm(file_path):
    """Show raw OCR -> prompt -> LLM output for debugging."""
    print(f"\n{'='*60}")
    print(f"FILE: {file_path}")
    print(f"{'='*60}")

    ocr_text = get_ocr_text(file_path)
    print(f"OCR text: {len(ocr_text)} chars")
    print(ocr_text[:300])
    print("...")

    prompt = _build_extraction_prompt(ocr_text)
    print(f"\nPrompt: {len(prompt)} chars")

    print("\n--- RAW LLM OUTPUT ---")
    start = time.time()
    raw = local_model_manager.generate(prompt)
    elapsed = time.time() - start
    print(f"({elapsed:.1f}s)")
    print(raw)
    print("--- END RAW ---")

    # Try parsing
    try:
        parsed = _parse_local_llm_response(raw)
        print("\nParsed OK:")
        print(json.dumps(parsed, indent=2))
    except Exception as e:
        print(f"\nParse FAILED: {e}")

    return raw


async def test_full_extraction(file_path):
    """Run the full _extract_with_local pipeline."""
    print(f"\n{'='*60}")
    print(f"FULL EXTRACTION: {file_path}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = await _extract_with_local(file_path)
        elapsed = time.time() - start
        print(f"\nResult ({elapsed:.1f}s):")
        print(json.dumps(result, indent=2))
    except Exception as e:
        elapsed = time.time() - start
        print(f"\nFAILED ({elapsed:.1f}s): {e}")


async def main():
    # Step 1: Raw LLM output for debugging
    print("#" * 60)
    print("# RAW LLM OUTPUTS (for prompt tuning)")
    print("#" * 60)
    for f in RECEIPT_FILES:
        test_raw_llm(f)

    # Step 2: Full extraction
    print("\n" + "#" * 60)
    print("# FULL EXTRACTION")
    print("#" * 60)
    for f in RECEIPT_FILES:
        await test_full_extraction(f)


if __name__ == "__main__":
    asyncio.run(main())
