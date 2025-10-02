"""
Hotel Itemizer Playwright automation for MS Expense.

This module handles the browser automation to populate
hotel expense itemization in MS Expense interface.
"""

import asyncio
import logging
from typing import Dict, List, Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from hotel_itemizer.models import MSExpenseItemEntry
from playwright_manager import get_current_page, get_browser_connection, connect_to_browser

logger = logging.getLogger(__name__)


class HotelMSExpenseAutomator:
    """Handles MS Expense automation for hotel itemization."""
    
    def __init__(self):
        self.page = None
        
    async def ensure_page_connection(self) -> Page:
        """Ensure we have a valid page connection to MS Expense."""
        try:
            # Try to get existing page first
            page = get_current_page()
            
            if page is None:
                logger.info("No existing page found, connecting to browser...")
                browser = get_browser_connection()
                
                if browser is None:
                    logger.info("No browser connection, connecting...")
                    browser = await connect_to_browser()
                
                # Get the first page (should be MS Expense)
                pages = browser.pages
                if pages:
                    page = pages[0]
                    logger.info(f"Using existing browser page: {page.url}")
                else:
                    # Create new page if none exists
                    page = await browser.new_page()
                    logger.info("Created new browser page")
            
            self.page = page
            return page
            
        except Exception as e:
            logger.error(f"Failed to establish page connection: {e}")
            raise RuntimeError(f"Could not connect to MS Expense page: {e}")
    
    async def navigate_to_itemization_view(self) -> bool:
        """Navigate to the expense itemization view in MS Expense."""
        try:
            page = await self.ensure_page_connection()
            
            # Wait for the page to be loaded
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            logger.info(f"Current URL: {page.url}")
            
            # Look for itemization button or link
            # This selector may need to be updated based on actual MS Expense interface
            itemization_selectors = [
                'button[aria-label*="itemiz"]',
                'button:has-text("Itemize")',
                'a:has-text("Itemize")',
                '.itemization-button',
                '[data-automation-id*="itemiz"]'
            ]
            
            for selector in itemization_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        logger.info(f"Found itemization element with selector: {selector}")
                        await element.click()
                        await page.wait_for_load_state('networkidle', timeout=5000)
                        return True
                except PlaywrightTimeout:
                    continue
            
            # If no itemization button found, check if we're already in itemization view
            itemization_indicators = [
                'text=Subcategory',
                'text=Daily Rate', 
                'text=Start Date',
                '.itemization-form',
                '[data-automation-id*="subcategory"]'
            ]
            
            for indicator in itemization_indicators:
                try:
                    element = await page.wait_for_selector(indicator, timeout=2000)
                    if element:
                        logger.info(f"Already in itemization view (found: {indicator})")
                        return True
                except PlaywrightTimeout:
                    continue
            
            logger.warning("Could not find itemization view or navigate to it")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to itemization view: {e}")
            return False
    
    async def populate_hotel_itemization(self, ms_expense_entries: List[MSExpenseItemEntry]) -> Dict[str, Any]:
        """
        Populate hotel itemization entries in MS Expense.
        
        Args:
            ms_expense_entries: List of MS Expense itemization entries
            
        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"Starting hotel itemization for {len(ms_expense_entries)} entries")
            
            # Ensure we're connected and in the right view
            if not await self.navigate_to_itemization_view():
                return {
                    "success": False,
                    "error": "Could not navigate to itemization view"
                }
            
            page = self.page
            populated_entries = []
            
            for i, entry in enumerate(ms_expense_entries):
                logger.info(f"Processing entry {i+1}/{len(ms_expense_entries)}: {entry.subcategory}")
                
                try:
                    # Add new itemization row if needed (except for first entry)
                    if i > 0:
                        await self._add_new_itemization_row(page)
                    
                    # Populate the entry
                    success = await self._populate_single_entry(page, entry, i)
                    
                    if success:
                        populated_entries.append({
                            "index": i,
                            "subcategory": entry.subcategory,
                            "daily_rate": entry.daily_rate,
                            "quantity": entry.quantity,
                            "status": "success"
                        })
                        logger.info(f"Successfully populated entry {i+1}")
                    else:
                        populated_entries.append({
                            "index": i,
                            "subcategory": entry.subcategory,
                            "status": "failed"
                        })
                        logger.warning(f"Failed to populate entry {i+1}")
                    
                    # Small delay between entries
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error processing entry {i+1}: {e}")
                    populated_entries.append({
                        "index": i,
                        "subcategory": entry.subcategory,
                        "status": "error",
                        "error": str(e)
                    })
            
            success_count = len([e for e in populated_entries if e["status"] == "success"])
            
            return {
                "success": True,
                "populated_count": success_count,
                "total_count": len(ms_expense_entries),
                "entries": populated_entries,
                "message": f"Successfully populated {success_count}/{len(ms_expense_entries)} hotel itemization entries"
            }
            
        except Exception as e:
            logger.error(f"Error in populate_hotel_itemization: {e}")
            return {
                "success": False,
                "error": f"Hotel itemization failed: {str(e)}"
            }
    
    async def _add_new_itemization_row(self, page: Page) -> bool:
        """Add a new itemization row in MS Expense."""
        try:
            # Look for add row button
            add_button_selectors = [
                'button[aria-label*="Add"]',
                'button:has-text("Add")',
                '.add-row-button',
                '[data-automation-id*="add"]',
                'button[title*="Add"]'
            ]
            
            for selector in add_button_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.click()
                        await asyncio.sleep(0.3)  # Wait for new row to appear
                        logger.debug(f"Added new row using selector: {selector}")
                        return True
                except PlaywrightTimeout:
                    continue
            
            logger.warning("Could not find add row button")
            return False
            
        except Exception as e:
            logger.error(f"Error adding new itemization row: {e}")
            return False
    
    async def _populate_single_entry(self, page: Page, entry: MSExpenseItemEntry, row_index: int) -> bool:
        """Populate a single itemization entry."""
        try:
            # Base selectors for the current row
            row_selectors = {
                "subcategory": [
                    f'select[data-automation-id*="subcategory"]:nth-of-type({row_index + 1})',
                    f'.itemization-row:nth-child({row_index + 1}) select',
                    f'tr:nth-child({row_index + 1}) select[aria-label*="subcategory"]',
                    f'select[name*="subcategory"]:nth-of-type({row_index + 1})'
                ],
                "start_date": [
                    f'input[data-automation-id*="startdate"]:nth-of-type({row_index + 1})',
                    f'.itemization-row:nth-child({row_index + 1}) input[type="date"]',
                    f'tr:nth-child({row_index + 1}) input[aria-label*="start"]',
                    f'input[name*="startdate"]:nth-of-type({row_index + 1})'
                ],
                "daily_rate": [
                    f'input[data-automation-id*="dailyrate"]:nth-of-type({row_index + 1})',
                    f'.itemization-row:nth-child({row_index + 1}) input[type="number"]',
                    f'tr:nth-child({row_index + 1}) input[aria-label*="rate"]',
                    f'input[name*="dailyrate"]:nth-of-type({row_index + 1})'
                ],
                "quantity": [
                    f'input[data-automation-id*="quantity"]:nth-of-type({row_index + 1})',
                    f'.itemization-row:nth-child({row_index + 1}) input[aria-label*="quantity"]',
                    f'tr:nth-child({row_index + 1}) input[aria-label*="quantity"]',
                    f'input[name*="quantity"]:nth-of-type({row_index + 1})'
                ]
            }
            
            # Populate subcategory (dropdown)
            if entry.subcategory:
                success = await self._populate_field(page, row_selectors["subcategory"], entry.subcategory, field_type="select")
                if not success:
                    logger.warning(f"Failed to populate subcategory: {entry.subcategory}")
            
            # Populate start date
            if entry.start_date:
                success = await self._populate_field(page, row_selectors["start_date"], entry.start_date, field_type="input")
                if not success:
                    logger.warning(f"Failed to populate start date: {entry.start_date}")
            
            # Populate daily rate
            if entry.daily_rate:
                success = await self._populate_field(page, row_selectors["daily_rate"], str(entry.daily_rate), field_type="input")
                if not success:
                    logger.warning(f"Failed to populate daily rate: {entry.daily_rate}")
            
            # Populate quantity
            if entry.quantity:
                success = await self._populate_field(page, row_selectors["quantity"], str(entry.quantity), field_type="input")
                if not success:
                    logger.warning(f"Failed to populate quantity: {entry.quantity}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error populating single entry: {e}")
            return False
    
    async def _populate_field(self, page: Page, selectors: List[str], value: str, field_type: str = "input") -> bool:
        """Populate a single field with multiple selector attempts."""
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element:
                    if field_type == "select":
                        await element.select_option(value=value)
                    else:
                        await element.clear()
                        await element.fill(value)
                    
                    logger.debug(f"Populated field using selector {selector} with value: {value}")
                    return True
                    
            except PlaywrightTimeout:
                continue
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        logger.warning(f"Could not populate field with value: {value}")
        return False


# Global instance for hotel automation
_hotel_automator = None


def get_hotel_automator() -> HotelMSExpenseAutomator:
    """Get the global hotel automator instance."""
    global _hotel_automator
    if _hotel_automator is None:
        _hotel_automator = HotelMSExpenseAutomator()
    return _hotel_automator


async def populate_hotel_expenses_in_ms_expense(ms_expense_entries: List[MSExpenseItemEntry]) -> Dict[str, Any]:
    """
    Convenience function to populate hotel expenses in MS Expense.
    
    Args:
        ms_expense_entries: List of MS Expense itemization entries
        
    Returns:
        Dict with success status and details
    """
    automator = get_hotel_automator()
    return await automator.populate_hotel_itemization(ms_expense_entries)