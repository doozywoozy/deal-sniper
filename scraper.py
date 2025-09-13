# scraper.py
import asyncio
import os
import re
import random
from typing import Dict, List

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async  # Ensure installed via requirements.txt
from bs4 import BeautifulSoup

import database
from config import (
    ENABLE_SCREENSHOTS,
    MAX_PAGES_TO_SCRAPE,
    REQUEST_DELAY,
    SCRAPE_TIMEOUT,
)
from logger import log_detection, log_detection_sync, logger


async def handle_cookie_consent(page):
    """Robustly handle cookie consent: try click, then force remove via JS if needed."""
    try:
        logger.info("Handling cookie consent...")

        # Wait for page stabilization
        await page.wait_for_timeout(5000)

        # Try to click the button using robust selector
        try:
            accept_button = page.locator('button:has-text("Godkänn alla")')
            await accept_button.wait_for(state="visible", timeout=10000)
            await accept_button.click()
            logger.info("✅ Clicked 'Godkänn alla' button!")
            await page.wait_for_timeout(3000)
            return
        except Exception:
            logger.warning("Standard click failed. Trying JS injection.")

        # Fallback: JS to find and click
        clicked = await page.evaluate('''() => {
            let clicked = false;
            document.querySelectorAll('button').forEach(button => {
                if (button.innerText.trim() === 'Godkänn alla') {
                    button.click();
                    clicked = true;
                }
            });
            return clicked;
        }''')

        if clicked:
            logger.info("✅ JS clicked 'Godkänn alla'!")
            await page.wait_for_timeout(3000)
            return

        # Ultimate fallback: Remove popup element via JS
        removed = await page.evaluate('''() => {
            const popup = document.querySelector('[role="dialog"]') || document.querySelector('.cookie-consent') || document.querySelector('div[id*="cookie"]') || document.querySelector('div[class*="cookie"]');
            if (popup) {
                popup.remove();
                return true;
            }
            return false;
        }''')

        if removed:
            logger.info("✅ Removed cookie popup via JS!")
        else:
            logger.warning("Could not find/remove popup. Proceeding anyway.")

    except Exception as e:
        logger.error(f"Cookie handling error: {e}. Continuing.")


async def scrape_blocket(search: Dict) -> List[Dict]:
    """Scrape listings with no strict timeouts and robust popup handling."""
    all_listings = []
    browser = None
    proxy = os.getenv('PROXY_URL')

    try:
        async with async_playwright() as p:
            launch_args = {}
            if proxy:
                launch_args['proxy'] = {'server': proxy}
            browser = await p.chromium.launch(headless=True, **launch_args)
            context = await browser.new_context(
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                ]),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                bypass_csp=True,
                locale="sv-SE",
            )
            page = await context.new_page()
            await stealth_async(page)

            # Remove strict timeouts: set to 0 (infinite)
            page.set_default_timeout(0)

            logger.info(f"\n⚡ Scanning blocket for {search['name']} (proxy: {bool(proxy)})")

            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                search_url = f"https://www.blocket.se/annonser/hela_sverige?q={search['query']}&price_end={search['price_end']}&page={page_num}"
                logger.info(f"📄 Page {page_num}: {search_url}")

                try:
                    await page.goto(search_url, wait_until="networkidle")

                    if page_num == 1:
                        await handle_cookie_consent(page)

                    await page.wait_for_timeout(random.randint(3000, 6000))
                    await page.mouse.move(random.randint(0, 1920), random.randint(0, 1080))

                    # Attempt to detect listings; no timeout
                    await page.wait_for_selector('div[data-testid="result-list"]', timeout=30000)  # Soft timeout for logging
                    logger.info("Listings container detected.")

                    listings = await extract_listings(page, search)
                    if not listings:
                        logger.warning("No listings from Playwright. Using BS4 fallback.")
                        content = await page.content()
                        listings = fallback_extract_listings(content, search)
                    all_listings.extend(listings)

                    page_text = await page.content()
                    if "inga resultat" in page_text.lower() or "inga annonser hittades" in page_text.lower():
                        logger.info("No results detected.")
                        break
                    if not listings and page_num == 1:
                        logger.warning("No listings. Capturing screenshot.")
                        if ENABLE_SCREENSHOTS:
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_path = os.path.join("screenshots", f"debug_{timestamp}.png")
                            await page.screenshot(path=screenshot_path, full_page=True)
                            logger.info(f"Screenshot: {screenshot_path}")
                        break

                except Exception as e:
                    logger.error(f"Page {page_num} error: {e}")
                    await log_detection(page, str(e), search_url)
                    break

                if page_num < MAX_PAGES_TO_SCRAPE:
                    await asyncio.sleep(REQUEST_DELAY)

    except Exception as e:
        logger.error(f"Browser error: {e}")
        log_detection_sync(str(e), "N/A")
    finally:
        if browser:
            await browser.close()

    return all_listings


async def extract_listings(page, search: Dict) -> List[Dict]:
    """Extract using Playwright."""
    listings = []
    try:
        elements = await page.locator('div[data-testid="result-list"] article').all() or await page.locator('.styled__StyledArticle-sc-1l2koxx-0').all()

        for elem in elements:
            try:
                title = await elem.locator("h3").inner_text() or "No title"
                url = f"https://www.blocket.se{await elem.locator('a').get_attribute('href')}" or "No URL"
                price_text = await elem.locator('span:text-is("SEK")').inner_text() or "0"
                price = int(re.sub(r"[^\d]", "", price_text))
                location = (await elem.locator('span:has-text("Kommun")').inner_text() or "No location").replace("Kommun", "").strip()

                listing_id = re.search(r"annons/(\d+)", url).group(1) if re.search(r"annons/(\d+)", url) else None

                if listing_id and not database.is_listing_seen(listing_id):
                    listing = {"id": listing_id, "title": title, "price": price, "url": url, "location": location, "source": "blocket", "query": search["name"]}
                    listings.append(listing)
                    database.mark_listing_seen(listing_id, title, price, url, "blocket")

            except Exception as e:
                logger.error(f"Extraction error: {e}")

    except Exception as e:
        logger.error(f"Playwright failed: {e}")

    return listings


def fallback_extract_listings(content: str, search: Dict) -> List[Dict]:
    """BS4 fallback."""
    listings = []
    try:
        soup = BeautifulSoup(content, 'html.parser')
        articles = soup.select('div[data-testid="result-list"] article') or soup.select('.styled__StyledArticle-sc-1l2koxx-0')

        for article in articles:
            try:
                title = article.find('h3').get_text(strip=True) if article.find('h3') else "No title"
                a_tag = article.find('a')
                url = f"https://www.blocket.se{a_tag['href']}" if a_tag else "No URL"
                price_span = article.find('span', string=re.compile(r'SEK'))
                price_text = price_span.get_text() if price_span else "0"
                price = int(re.sub(r"[^\d]", "", price_text))
                location_span = article.find('span', string=re.compile(r'Kommun'))
                location = location_span.get_text().replace("Kommun", "").strip() if location_span else "No location"

                listing_id = re.search(r"annons/(\d+)", url).group(1) if re.search(r"annons/(\d+)", url) else None

                if listing_id and not database.is_listing_seen(listing_id):
                    listing = {"id": listing_id, "title": title, "price": price, "url": url, "location": location, "source": "blocket", "query": search["name"]}
                    listings.append(listing)
                    database.mark_listing_seen(listing_id, title, price, url, "blocket")

            except Exception as e:
                logger.error(f"Fallback error: {e}")

    except Exception as e:
        logger.error(f"Fallback failed: {e}")

    return listings
