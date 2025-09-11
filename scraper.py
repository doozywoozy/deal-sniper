# scraper.py
import asyncio
import os
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, ENABLE_SCREENSHOTS, SCRAPE_TIMEOUT
from logger import logger, log_detection, log_detection_sync
import database

async def handle_cookie_consent(page):
    """Handle cookie consent popup by clicking 'Allow All' with better detection"""
    try:
        logger.info("Checking for cookie consent dialog...")
        
        # New, more reliable method using get_by_role and text
        allow_button = page.get_by_role("button", name="Godkänn alla", exact=True)
        
        # Wait specifically for the button to appear and be visible
        if await allow_button.is_visible(timeout=5000):
            logger.info("Found 'Godkänn alla' button with get_by_role. Clicking...")
            await allow_button.click()
            logger.info("✅ Cookie consent handled successfully!")
            return True
        else:
            logger.info("Did not find 'Godkänn alla' button, trying other selectors.")
            
        # Fallback to the previous, less specific selectors
        allow_selectors = [
            'button:has-text("Acceptera alla")',
            'button:has-text("Tillåt alla")',
            'button:has-text("Accept all")', 
            'button:has-text("Allow all")',
            'button[data-testid*="accept"]',
            'button[class*="accept"]',
            'button[class*="consent"]',
            '#acceptAllButton',
            '.accept-all',
            '[aria-label*="Godkänn alla"]',
            '[aria-label*="Acceptera alla"]',
            '[aria-label*="Accept all"]',
            'button[onclick*="cookie"]',
            'button[onclick*="accept"]',
            'button >> text=Godkänn',
            'button >> text=Acceptera',
            'button >> text=Tillåt'
        ]
        
        for selector in allow_selectors:
            try:
                # Check if the button is visible and click it
                button = page.locator(selector).first
                if await button.is_visible(timeout=5000):
                    logger.info(f"Found cookie button with selector: {selector}. Clicking...")
                    await button.click()
                    logger.info("✅ Cookie consent handled successfully!")
                    # Wait for the dialog to disappear
                    await page.wait_for_selector(selector, state="hidden", timeout=5000)
                    return True
            except TimeoutError:
                # Ignore TimeoutError and try next selector
                continue
            except Exception as e:
                logger.error(f"❌ Error clicking cookie button with selector {selector}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Error during cookie handling: {e}")
        
    logger.info("No cookie dialog found with standard selectors")
    return False

def extract_listing_data(html: str, search_name: str) -> List[Dict]:
    """Extract listings from the raw HTML content using BeautifulSoup."""
    soup = BeautifulSoup(html, 'html.parser')
    listings = []
    
    # Selectors for Blocket listings
    listing_elements = soup.find_all('article', class_='jHwEw _3xR6n _3B7oP')
    
    for element in listing_elements:
        try:
            url_element = element.find('a', class_='c7f-j')
            url = f"https://www.blocket.se{url_element['href']}" if url_element and 'href' in url_element.attrs else None
            
            # Skip if URL is a Blocket Pro ad
            if url and 'blocket.se/foretag/' in url:
                continue

            # Generate a unique ID from the URL
            if url:
                listing_id_match = re.search(r'/(?:vi|id)/(\d+)', url)
                listing_id = listing_id_match.group(1) if listing_id_match else None
                if not listing_id:
                    continue
            else:
                continue
            
            # Check if listing is already seen
            if database.is_listing_seen(listing_id):
                continue
                
            title_element = element.find('h2', class_='_3J23- _1gS_A')
            title = title_element.text.strip() if title_element else 'No Title'
            
            price_element = element.find('p', class_='_1g50y')
            price_text = price_element.text.strip() if price_element else '0 kr'
            price = int(''.join(filter(str.isdigit, price_text))) if price_text != 'Gratis' else 0
            
            location_element = element.find('p', class_='_1-w_s _1YvB8')
            location = location_element.text.strip() if location_element else 'Unknown Location'
            
            # Extract image URL from the img tag's src or data-src
            image_element = element.find('img')
            image_url = None
            if image_element:
                image_url = image_element.get('src') or image_element.get('data-src')

            # Build the listing dictionary
            listing = {
                'id': listing_id,
                'title': title,
                'price': price,
                'url': url,
                'location': location,
                'image': image_url,
                'source': 'Blocket',
                'query': search_name,
            }
            
            listings.append(listing)
            database.mark_listing_seen(listing_id, title, price, url, 'Blocket')
            
        except Exception as e:
            logger.error(f"Error parsing a listing: {e}")
            continue
            
    return listings

async def scrape_blocket_fast(search_url: str, search_name: str) -> List[Dict]:
    """Scrape listings from Blocket without using advanced bot detection bypass"""
    browser = None
    all_listings = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()

            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                url_to_scrape = f"{search_url}&page={page_num}"
                logger.info(f"📄 Page {page_num}: {url_to_scrape}")

                try:
                    await page.goto(url_to_scrape, timeout=SCRAPE_TIMEOUT)
                    
                    # Handle cookie consent first
                    await handle_cookie_consent(page)
                    
                    # Wait for a known element to indicate the page is loaded
                    await page.wait_for_selector('article.jHwEw', timeout=SCRAPE_TIMEOUT)
                    
                    # Get the page content after handling cookies
                    html_content = await page.content()
                    
                    listings = extract_listing_data(html_content, search_name)
                    
                    if not listings:
                        logger.warning(f"No listings found on page {page_num}")
                        page_text = await page.inner_text('body')
                        if "inga träffar" in page_text.lower() or "no listings" in page_text.lower():
                            logger.info("Genuine no results page")
                        else:
                            logger.warning("No listings found - taking debug screenshot")
                            if ENABLE_SCREENSHOTS:
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                screenshot_path = os.path.join("screenshots", f"no_listings_{timestamp}.png")
                                await page.screenshot(path=screenshot_path, full_page=True)
                                logger.info(f"No listings screenshot saved: {screenshot_path}")
                        break
                    
                    all_listings.extend(listings)
                    
                    # Add delay between pages
                    if page_num < MAX_PAGES_TO_SCRAPE:
                        await asyncio.sleep(REQUEST_DELAY)
                        
                except Exception as e:
                    logger.error(f"Error on page {page_num}: {e}")
                    await log_detection(page, f"Error: {str(e)}", search_url)
                    break
                    
    except Exception as e:
        logger.error(f"Error during browser setup: {e}")
        log_detection_sync(f"Browser error: {str(e)}", search_url)
    finally:
        if browser:
            await browser.close()
    
    return all_listings
