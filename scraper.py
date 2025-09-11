# scraper.py
import asyncio
import os
import re
import random
from typing import Dict, List

from playwright.async_api import TimeoutError, async_playwright
from playwright_stealth import stealth_async  # Ensure this is installed via requirements.txt

import database
from config import (
    ENABLE_SCREENSHOTS,
    MAX_PAGES_TO_SCRAPE,
    REQUEST_DELAY,
    SCRAPE_TIMEOUT,
)
from logger import log_detection, log_detection_sync, logger


async def handle_cookie_consent(page):
    """Handle cookie consent popup by clicking 'Godkänn alla'."""
    try:
        logger.info("Looking for cookie consent dialog...")

        # More robust selector using has-text for visible text matching
        accept_button = page.locator('button:has-text("Godkänn alla")')

        # Increased timeout to 60s for slow loads
        await accept_button.wait_for(state="visible", timeout=60000)
        await accept_button.click()

        logger.info("✅ Successfully clicked 'Godkänn alla' button!")

        # Wait for the dialog to disappear
        await page.wait_for_timeout(2000)

    except TimeoutError as te:
        logger.warning(f"Cookie button not found after timeout: {te}. Proceeding without click—popup may not be present.")
    except Exception as e:
        logger.warning(f"Could not find or click cookie button, hopefully it's not needed. Error: {e}")


async def scrape_blocket(search: Dict) -> List[Dict]:
    """Scrape listings from Blocket based on a search query."""
    all_listings = []
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                screen={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                bypass_csp=True,
                locale="sv-SE",  # Swedish locale
            )
            page = await context.new_page()
            await stealth_async(page)  # Apply stealth

            # Set default timeout
            page.set_default_timeout(SCRAPE_TIMEOUT)

            logger.info(f"\n⚡ Fast scanning blocket for {search['name']}")

            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                search_url = f"https://www.blocket.se/annonser/hela_sverige?q={search['query']}&price_end={search['price_end']}&page={page_num}"
                logger.info(f"📄 Page {page_num}: {search_url}")

                try:
                    # Navigate
                    await page.goto(search_url, wait_until="domcontentloaded")

                    # Handle cookie on first page
                    if page_num == 1:
                        await handle_cookie_consent(page)

                    # Simulate human behavior: random wait and mouse move
                    await page.wait_for_timeout(random.randint(2000, 5000))
                    await page.mouse.move(random.randint(0, 1920), random.randint(0, 1080))

                    # Wait for listings container to confirm load (more reliable than search input)
                    await page.wait_for_selector('div[data-testid="result-list"]', timeout=SCRAPE_TIMEOUT)

                    # Extract listings
                    listings = await extract_listings(page, search)
                    all_listings.extend(listings)

                    # Check for "no results"
                    page_text = await page.content()
                    if (
                        "inga resultat" in page_text.lower()
                        or "inga annonser hittades" in page_text.lower()
                    ):
                        logger.info("Genuine no results page")
                        break
                    else:
                        if not listings and page_num == 1:
                            logger.warning(
                                "No listings found on the first page - taking debug screenshot"
                            )
                            if ENABLE_SCREENSHOTS:
                                from datetime import datetime

                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                screenshot_path = os.path.join(
                                    "screenshots", f"no_listings_{timestamp}.png"
                                )
                                await page.screenshot(
                                    path=screenshot_path, full_page=True
                                )
                                logger.info(
                                    f"No listings screenshot saved: {screenshot_path}"
                                )
                                # Break if no listings on first page
                                break

                except TimeoutError as te:
                    logger.error(f"Error on page {page_num}: Timeout {te}")
                    await log_detection(page, f"Error: {str(te)}", search_url)
                    break
                except Exception as e:
                    logger.error(f"Error on page {page_num}: {e}")
                    await log_detection(page, f"Error: {str(e)}", search_url)
                    break

                # Delay between pages
                if page_num < MAX_PAGES_TO_SCRAPE:
                    await asyncio.sleep(REQUEST_DELAY)

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
    listing_elements = await page.locator('div[data-testid="result-list"] article').all()

    if not listing_elements:
        logger.warning("No listings found with data-testid selector. Trying a different one.")
        listing_elements = await page.locator(
            ".styled__StyledArticle-sc-1l2koxx-0"
        ).all()

    for listing_element in listing_elements:
        try:
            # Extract basic info
            title_element = listing_element.locator("h3").first
            title = await title_element.inner_text() if title_element else "No title"

            url_element = listing_element.locator("a").first
            url = (
                f"https://www.blocket.se{await url_element.get_attribute('href')}"
                if url_element
                else "No URL"
            )

            price_element = listing_element.locator('span:text-is("SEK")').first
            price_text = await price_element.inner_text() if price_element else "0"
            price = int(re.sub(r"[^\d]", "", price_text))

            location_element = listing_element.locator('span:has-text("Kommun")').first
            location = (
                await location_element.inner_text() if location_element else "No location"
            )
            # Clean up the location text
            location = location.replace("Kommun", "").strip()

            # Create a unique ID for the listing
            listing_id_match = re.search(r"annons/(\d+)", url)
            listing_id = listing_id_match.group(1) if listing_id_match else None

            if listing_id and not database.is_listing_seen(listing_id):
                listing = {
                    "id": listing_id,
                    "title": title,
                    "price": price,
                    "url": url,
                    "location": location,
                    "source": "blocket",
                    "query": search["name"],
                }
                listings.append(listing)
                database.mark_listing_seen(
                    listing["id"],
                    listing["title"],
                    listing["price"],
                    listing["url"],
                    listing["source"],
                )

        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            continue

    return listings
