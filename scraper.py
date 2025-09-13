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
    """Scrape listings using BS4 on page content after handling popup."""
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

            # No strict timeouts
            page.set_default_timeout(0)

            logger.info(f"\n⚡ Scanning blocket for {search['name']} (proxy: {bool(proxy)})")

            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                search_url = f"https://www.blocket.se/annonser/hela_sverige?q={search['query']}&price_end={search['price_end']}&page={page_num}"
                logger.info(f"📄 Page {page_num}: {search_url}")

                try:
                    await page.goto(search_url, wait_until="networkidle")

                    if page_num == 1:
                        await handle_cookie_consent(page)

                    # Additional wait after popup handling
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(random.randint(5000, 10000))  # Longer wait for content to settle
                    await page.mouse.move(random.randint(0, 1920), random.randint(0, 1080))

                    # Get page content and parse with BS4
                    content = await page.content()
                    listings = fallback_extract_listings(content, search)
                    all_listings.extend(listings)

                    if "inga resultat" in content.lower() or "inga annonser hittades" in content.lower():
                        logger.info("No results detected.")
                        break
                    if not listings and page_num == 1:
                        logger.warning("No listings extracted. Capturing screenshot.")
                        if ENABLE_SCREENSHOTS:
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_path = os.path.join("screenshots", f"debug_{timestamp}.png")
                            await page.screenshot(path=screenshot_path, full_page=True)
                            logger.info(f"Screenshot: {screenshot_path}")
                        # Save content for debug
                        with open('debug_content.html', 'w', encoding='utf-8') as f:
                            f.write(content)
                        logger.info("Saved page content to debug_content.html")
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


def fallback_extract_listings(content: str, search: Dict) -> List[Dict]:
    """Extract listings using BeautifulSoup with broader selectors."""
    listings = []
    try:
        soup = BeautifulSoup(content, 'html.parser')

        # Broader selector: all article tags, or divs containing listings
        article_elements = soup.find_all('article') or soup.find_all('div', class_=re.compile(r'listing|article|item', re.I))

        for article in article_elements:
            try:
                # Title: find h3 or similar heading
                title_tag = article.find(['h3', 'h4', 'p', 'span'], string=re.compile(r'.{5,}', re.I))  # At least 5 chars
                title = title_tag.get_text(strip=True) if title_tag else "No title"

                # URL: find a tag with href containing 'annons'
                a_tag = article.find('a', href=re.compile(r'annons'))
                url = f"https://www.blocket.se{a_tag['href']}" if a_tag else "No URL"

                # Price: find span or p with 'kr'
                price_tag = article.find(string=re.compile(r'\d+\s*kr'))
                price_text = price_tag.strip() if price_tag else "0"
                price = int(re.sub(r"[^\d]", "", price_text))

                # Location: find span or p with location-like text (cities, ' - ', etc.)
                location_tag = article.find(string=re.compile(r'(Stockholm|Göteborg| Malmö| [A-Z][a-z]+)', re.I))
                location = location_tag.strip() if location_tag else "No location"

                # ID from URL
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
                logger.error(f"Listing extraction error: {e}")
                continue

        logger.info(f"Extracted {len(listings)} listings via BS4.")

    except Exception as e:
        logger.error(f"BS4 extraction failed: {e}")

    return listings
