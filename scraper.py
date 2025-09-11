# scraper.py
import asyncio
import os
from typing import List, Dict
from playwright.async_api import async_playwright
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, ENABLE_SCREENSHOTS
from logger import logger, log_detection, log_detection_sync
import database

async def handle_cookie_consent(page):
    """Handle cookie consent popup by clicking 'Allow All'"""
    try:
        # Wait for cookie dialog to appear
        await page.wait_for_timeout(2000)
        
        # Try multiple selectors for the "Allow All" button
        allow_selectors = [
            'button:has-text("Godkänn alla")',
            'button:has-text("Accept all")', 
            'button:has-text("Allow all")',
            'button[data-testid*="accept"]',
            'button[class*="accept"]',
            'button[class*="consent"]',
            '#acceptAllButton',
            '.accept-all',
            '[aria-label*="Godkänn alla"]',
            '[aria-label*="Accept all"]'
        ]
        
        for selector in allow_selectors:
            try:
                allow_button = await page.wait_for_selector(selector, timeout=5000)
                if allow_button:
                    await allow_button.click()
                    logger.info("✅ Clicked 'Allow All' on cookie consent")
                    await page.wait_for_timeout(1000)  # Wait for dialog to close
                    return True
            except Exception:
                continue
        
        # If no button found, check if dialog exists but we couldn't click it
        dialog_selectors = [
            '[id*="cookie"]',
            '[class*="cookie"]',
            '[data-testid*="cookie"]',
            '#cookieBanner',
            '.cookie-consent'
        ]
        
        for selector in dialog_selectors:
            try:
                dialog = await page.query_selector(selector)
                if dialog:
                    logger.warning("Cookie dialog found but couldn't find accept button")
                    # Try to close with Escape key as fallback
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue
                
        logger.info("No cookie consent dialog found")
        return False
        
    except Exception as e:
        logger.warning(f"Error handling cookie consent: {e}")
        return False

async def scrape_blocket_fast(search_url: str, search_name: str) -> List[Dict]:
    """Fast scraping using Playwright with pagination"""
    all_listings = []
    browser = None
    
    try:
        browser = await async_playwright().start()
        # Launch browser with stealth options
        browser_instance = await browser.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-web-security',
            ]
        )
        
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale='sv-SE',
            timezone_id='Europe/Stockholm',
        )
        
        # Stealth evasions
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        
        for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
            # Build URL with pagination
            if "?" in search_url:
                paginated_url = f"{search_url}&page={page_num}"
            else:
                paginated_url = f"{search_url}?page={page_num}"
            
            logger.info(f"📄 Page {page_num}: {paginated_url}")
            
            try:
                # Navigate with realistic timing
                await page.goto(paginated_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                
                # Handle cookie consent before checking for bot detection
                await handle_cookie_consent(page)
                
                # Check page content for bot detection (after handling cookies)
                page_text = await page.evaluate('''() => document.body.textContent''')
                
                detection_keywords = ['captcha', 'robot', 'bot', 'cloudflare', 'access denied', 'blocked']
                is_detected = any(keyword in page_text.lower() for keyword in detection_keywords)
                
                if is_detected:
                    await log_detection(page, f"Detection on page {page_num}", search_url)
                    break
                
                # Try scraping
                listings = await try_scraping_approaches(page)
                logger.info(f"Found {len(listings)} articles on page {page_num}")
                
                if not listings:
                    if "inga annonser" in page_text.lower() or "no results" in page_text.lower():
                        logger.info("Genuine no results page")
                    else:
                        logger.warning("No listings found but page doesn't indicate 'no results'")
                        # Take screenshot for debugging
                        if ENABLE_SCREENSHOTS:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_path = os.path.join("screenshots", f"debug_{timestamp}.png")
                            await page.screenshot(path=screenshot_path, full_page=True)
                            logger.info(f"Debug screenshot saved: {screenshot_path}")
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
            await browser.stop()
    
    return all_listings

async def try_scraping_approaches(page):
    """Try different approaches to scrape listings"""
    approaches = [scrape_modern_blocket, scrape_article_based, scrape_fallback]
    
    for approach in approaches:
        try:
            listings = await approach(page)
            if listings:
                return listings
        except Exception as e:
            logger.debug(f"Approach failed: {e}")
    
    return []

async def scrape_modern_blocket(page):
    """Modern Blocket with data-testid attributes"""
    return await page.evaluate('''() => {
        const items = [];
        const listings = document.querySelectorAll('[data-testid*="listing"], [data-testid*="ad"]');
        
        for (const listing of listings) {
            try {
                const titleElem = listing.querySelector('[data-testid*="title"], h2, h3');
                const priceElem = listing.querySelector('[data-testid*="price"]');
                const linkElem = listing.querySelector('a[href*="/annons/"]');
                
                if (titleElem && priceElem && linkElem) {
                    const title = titleElem.textContent?.trim() || '';
                    const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                    const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                    const url = linkElem.href;
                    
                    if (title && price > 0) {
                        items.push({
                            id: url.split('/').pop().split('?')[0],
                            title: title,
                            price: price,
                            url: url,
                            source: 'blocket'
                        });
                    }
                }
            } catch (e) {}
        }
        return items;
    }''')

async def scrape_article_based(page):
    """Traditional article-based scraping"""
    return await page.evaluate('''() => {
        const items = [];
        const articles = document.querySelectorAll('article');
        
        for (const article of articles) {
            try {
                const titleElem = article.querySelector('h2, h3, .title');
                const priceElem = article.querySelector('.price, [class*="price"]');
                const linkElem = article.querySelector('a[href*="/annons/"]');
                
                if (titleElem && priceElem && linkElem) {
                    const title = titleElem.textContent?.trim() || '';
                    const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                    const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                    const url = linkElem.href;
                    
                    if (title && price > 0) {
                        items.push({
                            id: url.split('/').pop().split('?')[0],
                            title: title,
                            price: price,
                            url: url,
                            source: 'blocket'
                        });
                    }
                }
            } catch (e) {}
        }
        return items;
    }''')

async def scrape_fallback(page):
    """Fallback approach using broader selectors"""
    return await page.evaluate('''() => {
        const items = [];
        const links = document.querySelectorAll('a[href*="/annons/"]');
        
        for (const link of links) {
            try {
                const container = link.closest('div, article, li');
                if (!container) continue;
                
                const titleElem = container.querySelector('h2, h3, .title') || link;
                const priceElem = container.querySelector('.price, [class*="price"]');
                
                if (titleElem && priceElem) {
                    const title = titleElem.textContent?.trim() || '';
                    const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                    const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                    const url = link.href;
                    
                    if (title && price > 0) {
                        items.push({
                            id: url.split('/').pop().split('?')[0],
                            title: title,
                            price: price,
                            url: url,
                            source: 'blocket'
                        });
                    }
                }
            } catch (e) {}
        }
        return items;
    }''')

def is_profitable(listing: Dict, search_name: str) -> bool:
    """Determine if a listing is profitable"""
    from config import PRICE_THRESHOLDS, KEYWORDS
    
    title_lower = listing['title'].lower()
    price = listing['price']
    
    if price <= 0 or price > 50000:
        return False
    
    if "rtx 3080" in search_name.lower():
        return (price <= PRICE_THRESHOLDS["rtx_3080"] and 
                any(keyword in title_lower for keyword in KEYWORDS["rtx_3080"]))
    
    elif "xeon" in search_name.lower():
        return (price <= PRICE_THRESHOLDS["xeon_workstation"] and 
                any(keyword in title_lower for keyword in KEYWORDS["xeon_workstation"]))
    
    else:
        return (price <= PRICE_THRESHOLDS["stationary_computers"] and 
                any(keyword in title_lower for keyword in KEYWORDS["stationary_computers"]))

async def scrape_blocket_search(search_url: str, search_name: str) -> List[Dict]:
    """Main scraping function with deduplication"""
    logger.info(f"🚀 Fast scraping: {search_url}")
    
    all_listings = await scrape_blocket_fast(search_url, search_name)
    
    if not all_listings:
        logger.info("No listings found at all")
        return []
    
    logger.info(f"⚡ Scanned {len(all_listings)} articles total across {MAX_PAGES_TO_SCRAPE} pages")
    
    valid_listings = []
    seen_ids = set()
    
    for listing in all_listings:
        if listing['id'] in seen_ids:
            continue
        seen_ids.add(listing['id'])
        
        if database.is_listing_seen(listing['id']):
            continue
            
        if is_profitable(listing, search_name):
            valid_listings.append(listing)
            database.mark_listing_seen(listing['id'], listing['title'], listing['price'], listing['url'])
    
    logger.info(f"🎯 Total valid listings found: {len(valid_listings)}")
    return valid_listings
