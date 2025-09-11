# scraper.py
import asyncio
import os
from typing import List, Dict
from playwright.async_api import async_playwright
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, ENABLE_SCREENSHOTS
from logger import logger, log_detection
import database

async def scrape_blocket_fast(search_url: str, search_name: str) -> List[Dict]:
    """Fast scraping using Playwright with pagination"""
    all_listings = []
    
    async with async_playwright() as p:
        # Launch browser with stealth options
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--no-zygote',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale='sv-SE',
            timezone_id='Europe/Stockholm',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'sv-SE,sv;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        # Stealth evasions
        await context.add_init_script("""
            // Overwrite the `languages` property to use a custom getter.
            Object.defineProperty(navigator, 'languages', {
                get: function () {
                    return ['sv-SE', 'sv', 'en-US', 'en'];
                },
            });
            
            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'plugins', {
                get: function () {
                    return [1, 2, 3, 4, 5];
                },
            });
            
            // Pass the Webdriver test
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Pass the Chrome test.
            window.chrome = {
                runtime: {},
            };
            
            // Pass the Permissions test.
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        page = await context.new_page()
        
        try:
            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                # Build URL with pagination
                if "?" in search_url:
                    paginated_url = f"{search_url}&page={page_num}"
                else:
                    paginated_url = f"{search_url}?page={page_num}"
                
                logger.info(f"📄 Page {page_num}: {paginated_url}")
                
                # Navigate with realistic timing
                await page.goto(paginated_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)  # Human-like delay
                
                # Check page content for bot detection
                page_content = await page.content()
                page_text = await page.evaluate('''() => document.body.textContent''')
                
                detection_keywords = ['captcha', 'robot', 'bot', 'cloudflare', 'access denied', 'blocked']
                is_detected = any(keyword in page_text.lower() for keyword in detection_keywords)
                
                if is_detected and ENABLE_SCREENSHOTS:
                    await log_detection(page, f"Detection on page {page_num}", search_url)
                    break
                
                # Try multiple scraping approaches
                listings = await try_scraping_approaches(page)
                
                logger.info(f"Found {len(listings)} articles on page {page_num}")
                
                if not listings:
                    # Check if it's a genuine "no results" page
                    if "inga annonser" in page_text.lower() or "no results" in page_text.lower():
                        logger.info("Genuine no results page")
                    else:
                        logger.warning("No listings found but page doesn't indicate 'no results'")
                    break
                
                all_listings.extend(listings)
                
                # Add delay between pages
                if page_num < MAX_PAGES_TO_SCRAPE:
                    await asyncio.sleep(REQUEST_DELAY)
                    
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            if ENABLE_SCREENSHOTS:
                await log_detection(page, f"Error: {str(e)}", search_url)
        finally:
            await browser.close()
    
    return all_listings

async def try_scraping_approaches(page):
    """Try different approaches to scrape listings"""
    approaches = [
        scrape_modern_blocket,
        scrape_article_based,
        scrape_fallback
    ]
    
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
        const listings = document.querySelectorAll('[data-testid*="listing-container"], [data-testid*="ad-item"]');
        
        for (const listing of listings) {
            try {
                const titleElem = listing.querySelector('[data-testid*="title"], [data-testid*="heading"]');
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
            } catch (e) {
                console.error('Error parsing listing:', e);
            }
        }
        return items;
    }''')

async def scrape_article_based(page):
    """Traditional article-based scraping"""
    return await page.evaluate('''() => {
        const items = [];
        const articles = document.querySelectorAll('article, .listing-item, .ad-item');
        
        for (const article of articles) {
            try {
                const titleElem = article.querySelector('h2, h3, .title, [class*="title"]');
                const priceElem = article.querySelector('.price, [class*="price"], .amount');
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
            } catch (e) {
                console.error('Error parsing article:', e);
            }
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
                // Look for title and price in parent elements
                const container = link.closest('div, article, li');
                if (!container) continue;
                
                const titleElem = container.querySelector('h2, h3, h4, .title, [class*="title"]') || link;
                const priceElem = container.querySelector('.price, [class*="price"], .amount, [class*="cost"]');
                
                if (titleElem && priceElem) {
                    const title = titleElem.textContent?.trim() || '';
                    const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                    const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                    const url = link.href;
                    
                    if (title && price > 0 && title.length > 5) {
                        items.push({
                            id: url.split('/').pop().split('?')[0],
                            title: title,
                            price: price,
                            url: url,
                            source: 'blocket'
                        });
                    }
                }
            } catch (e) {
                console.error('Error parsing fallback:', e);
            }
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
