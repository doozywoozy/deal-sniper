# scraper.py
import asyncio
import os
from typing import List, Dict
from playwright.async_api import async_playwright
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, ENABLE_SCREENSHOTS, SCRAPE_TIMEOUT
from logger import logger, log_detection, log_detection_sync
import database
import re

async def handle_cookie_consent(page):
    """Handle cookie consent popup by clicking 'Godkänn alla'."""
    try:
        # Check for the cookie banner's presence first to avoid unnecessary waiting
        cookie_banner_locator = page.locator('div:has-text("Vi använder cookies")')
        if not await cookie_banner_locator.is_visible():
            logger.info("No cookie consent dialog detected.")
            return

        logger.info("Checking for cookie consent dialog...")
        
        # Use a more robust selector that finds the button by its text content
        # This is more reliable than class names or other attributes that might change
        accept_button = page.locator('button:text-is("Godkänn alla")')

        # Wait for the button to appear and click it
        await accept_button.wait_for(timeout=5000)
        await accept_button.click()
        logger.info("✅ Successfully clicked 'Godkänn alla' button!")
        
        # Add a short delay to allow the cookie banner to disappear
        await page.wait_for_timeout(2000)

    except Exception as e:
        logger.warning(f"Did not find 'Godkänn alla' button, trying a more general selector...")
        
        try:
            # Fallback to a partial text match
            accept_button_partial = page.locator('button:has-text("Godkänn")')
            await accept_button_partial.wait_for(timeout=5000)
            await accept_button_partial.click()
            logger.info("✅ Successfully clicked fallback 'Godkänn' button!")
            await page.wait_for_timeout(2000)
        except Exception as e_fallback:
            logger.warning(f"No cookie dialog found with standard selectors. Error: {e_fallback}")
            await log_detection(page, f"No cookie dialog found: {str(e_fallback)}", page.url)
            # Continue execution, the scraper might still work or will fail on the next step

async def scrape_blocket(search: Dict) -> List[Dict]:
    """Scrape listings from Blocket based on a search query."""
    all_listings = []
    browser = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # Set a default timeout for all operations on the page
            page.set_default_timeout(SCRAPE_TIMEOUT)
            
            logger.info(f"\n⚡ Fast scanning blocket for {search['name']}")
            
            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                try:
                    search_url = f"https://www.blocket.se/annonser/hela_sverige?q={search['query']}&price_end={search['price_end']}&page={page_num}"
                    logger.info(f"📄 Page {page_num}: {search_url}")
                    
                    # Navigate to the search URL
                    await page.goto(search_url, wait_until="domcontentloaded")
                    
                    # Handle cookie consent on the first page
                    if page_num == 1:
                        await handle_cookie_consent(page)

                    # Extract listings
                    listings = await extract_listings(page, search)
                    all_listings.extend(listings)
                    
                    # Check for "no results"
                    page_text = await page.content()
                    if "inga resultat" in page_text.lower() or "inga annonser hittades" in page_text.lower():
                        logger.info("Genuine no results page")
                        break
                    else:
                        if not listings:
                            logger.warning("No listings found - taking debug screenshot")
                            if ENABLE_SCREENSHOTS:
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                screenshot_path = os.path.join("screenshots", f"no_listings_{timestamp}.png")
                                await page.screenshot(path=screenshot_path, full_page=True)
                                logger.info(f"No listings screenshot saved: {screenshot_path}")
                                
                    # Add delay between pages
                    if page_num < MAX_PAGES_TO_SCRAPE:
                        await asyncio.sleep(REQUEST_DELAY)
                    
                except Exception as e:
                    logger.error(f"Error on page {page_num}: {e}")
                    await log_detection(page, f"Error: {str(e)}", search_url)
                    break
                
    except Exception as e:
        logger.error(f"Error during browser setup: {e}")
        log_detection_sync(f"Browser error: {str(e)}", "N/A")
    finally:
        if browser:
            await browser.close()
    
    return all_listings

async def extract_listings(page, search: Dict) -> List[Dict]:
    """Extract listing data from the current page."""
    listings = []
    
    # Use a broader locator for the list items
    listing_elements = await page.locator('article[data-testid*="listing-card"]').all()
    
    if not listing_elements:
        logger.warning("No listings found with data-testid selector. Trying a different one.")
        listing_elements = await page.locator('.styled__StyledArticle-sc-1l2koxx-0').all()

    for listing_element in listing_elements:
        try:
            # Extract basic info
            title_element = listing_element.locator('h3').first
            title = await title_element.inner_text() if title_element else "No title"

            url_element = listing_element.locator('a').first
            url = f"https://www.blocket.se{await url_element.get_attribute('href')}" if url_element else "No URL"

            price_element = listing_element.locator('span:text-is("SEK")').first
            price_text = await price_element.inner_text() if price_element else "0"
            price = int(re.sub(r'[^\d]', '', price_text))

            location_element = listing_element.locator('span:has-text("Kommun")').first
            location = await location_element.inner_text() if location_element else "No location"
            # Clean up the location text
            location = location.replace('Kommun', '').strip()

            # Create a unique ID for the listing
            listing_id_match = re.search(r'annons/(\d+)', url)
            listing_id = listing_id_match.group(1) if listing_id_match else None
            
            if listing_id and not database.is_listing_seen(listing_id):
                listing = {
                    "id": listing_id,
                    "title": title,
                    "price": price,
                    "url": url,
                    "location": location,
                    "source": "blocket",
                    "query": search['name'],
                }
                listings.append(listing)
                database.mark_listing_seen(listing['id'], listing['title'], listing['price'], listing['url'], listing['source'])
                
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            continue

    return listings
