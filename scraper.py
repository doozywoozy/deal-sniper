# scraper.py
import asyncio
from typing import List, Dict
from playwright.async_api import async_playwright
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, PRICE_THRESHOLDS, KEYWORDS
import database

async def scrape_blocket_fast(search_url: str, search_name: str) -> List[Dict]:
    """Fast scraping using Playwright with pagination"""
    all_listings = []
    
    async with async_playwright() as p:
        # Launch browser with more stealth options
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='sv-SE',
            timezone_id='Europe/Stockholm',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'sv-SE,sv;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
        )
        
        # Add stealth evasions
        await context.add_init_script("""
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        page = await context.new_page()
        
        try:
            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                # Build URL with pagination
                if "?" in search_url:
                    paginated_url = f"{search_url}&page={page_num}"
                else:
                    paginated_url = f"{search_url}?page={page_num}"
                
                print(f"📄 Page {page_num}: {paginated_url}")
                
                # Navigate with realistic timing
                await page.goto(paginated_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)  # Wait for content to load
                
                # Check if we got blocked
                page_content = await page.content()
                if "captcha" in page_content.lower() or "robot" in page_content.lower():
                    print("⚠️ Possible bot detection detected!")
                    break
                
                # Try multiple approaches to find listings
                listings = []
                
                # Approach 1: Try data-testid attributes (modern Blocket)
                try:
                    listings = await page.evaluate('''() => {
                        const items = [];
                        // Look for listing containers
                        const listingContainers = document.querySelectorAll('[data-testid*="listing"], [data-testid*="ad"]');
                        
                        for (const container of listingContainers) {
                            try {
                                const titleElem = container.querySelector('[data-testid*="title"], h2, h3');
                                const priceElem = container.querySelector('[data-testid*="price"], [class*="price"]');
                                const linkElem = container.querySelector('a[href*="/annons/"], a[href*="/ad/"]');
                                
                                if (titleElem && priceElem && linkElem) {
                                    const title = titleElem.textContent?.trim() || '';
                                    const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                                    const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                                    const url = linkElem.href;
                                    
                                    // Generate ID from URL
                                    const id = url.split('/').filter(Boolean).pop().split('?')[0];
                                    
                                    if (title && price > 0) {
                                        items.push({
                                            id: id,
                                            title: title,
                                            price: price,
                                            url: url,
                                            source: 'blocket'
                                        });
                                    }
                                }
                            } catch (e) {
                                console.log('Error parsing container:', e);
                            }
                        }
                        return items;
                    }''')
                except Exception as e:
                    print(f"Error with data-testid approach: {e}")
                
                # Approach 2: If no listings found, try article tags
                if not listings:
                    try:
                        listings = await page.evaluate('''() => {
                            const items = [];
                            const articles = document.querySelectorAll('article');
                            
                            for (const article of articles) {
                                try {
                                    const titleElem = article.querySelector('h2, h3, [class*="title"]');
                                    const priceElem = article.querySelector('[class*="price"]');
                                    const linkElem = article.querySelector('a');
                                    
                                    if (titleElem && priceElem && linkElem && linkElem.href.includes('/annons/')) {
                                        const title = titleElem.textContent?.trim() || '';
                                        const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                                        const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                                        const url = linkElem.href;
                                        
                                        const id = url.split('/').filter(Boolean).pop().split('?')[0];
                                        
                                        if (title && price > 0) {
                                            items.push({
                                                id: id,
                                                title: title,
                                                price: price,
                                                url: url,
                                                source: 'blocket'
                                            });
                                        }
                                    }
                                } catch (e) {
                                    console.log('Error parsing article:', e);
                                }
                            }
                            return items;
                        }''')
                    except Exception as e:
                        print(f"Error with article approach: {e}")
                
                # Approach 3: Debug - print page content to understand structure
                if not listings:
                    print("⚠️ No listings found with standard selectors")
                    # Let's see what's actually on the page
                    page_text = await page.evaluate('''() => {
                        return document.body.textContent;
                    }''')
                    if "inga annonser" in page_text.lower() or "no hits" in page_text.lower():
                        print("ℹ️ Page indicates no listings found")
                    else:
                        print("🔍 Page content sample:", page_text[:200] + "...")
                
                print(f"Found {len(listings)} articles on page {page_num}")
                
                if not listings:
                    print("No more listings found, stopping pagination.")
                    break
                
                all_listings.extend(listings)
                
                # Add delay between pages to be respectful
                if page_num < MAX_PAGES_TO_SCRAPE:
                    await asyncio.sleep(REQUEST_DELAY)
                    
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            await browser.close()
    
    return all_listings

def is_profitable(listing: Dict, search_name: str) -> bool:
    """Determine if a listing is profitable based on search type"""
    title_lower = listing['title'].lower()
    price = listing['price']
    
    # Skip listings with no price or unrealistic prices
    if price <= 0 or price > 50000:
        return False
    
    # Apply different filters based on search type
    if "rtx 3080" in search_name.lower():
        return (price <= PRICE_THRESHOLDS["rtx_3080"] and 
                any(keyword in title_lower for keyword in ["rtx 3080", "3080", "geforce"]))
    
    elif "xeon" in search_name.lower():
        return (price <= PRICE_THRESHOLDS["xeon_workstation"] and 
                any(keyword in title_lower for keyword in ["xeon", "workstation", "server"]))
    
    else:
        return (price <= PRICE_THRESHOLDS["stationary_computers"] and 
                any(keyword in title_lower for keyword in ["dator", "computer", "pc", "stationär"]))

async def scrape_blocket_search(search_url: str, search_name: str) -> List[Dict]:
    """Main scraping function with deduplication"""
    print(f"🚀 Fast scraping: {search_url}")
    
    # Scrape all pages
    all_listings = await scrape_blocket_fast(search_url, search_name)
    
    if not all_listings:
        print("No listings found at all")
        return []
    
    print(f"⚡ Scanned {len(all_listings)} articles total across {MAX_PAGES_TO_SCRAPE} pages")
    
    # Filter and deduplicate
    valid_listings = []
    seen_ids = set()
    
    for listing in all_listings:
        # Skip duplicates in this batch
        if listing['id'] in seen_ids:
            continue
        seen_ids.add(listing['id'])
        
        # Skip if already in database
        if database.is_listing_seen(listing['id']):
            continue
            
        # Check if profitable
        if is_profitable(listing, search_name):
            valid_listings.append(listing)
            database.mark_listing_seen(listing['id'], listing['title'], listing['price'], listing['url'])
    
    print(f"🎯 Total valid listings found: {len(valid_listings)}")
    return valid_listings
