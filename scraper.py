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
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        page = await context.new_page()
        
        try:
            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                # Build URL with pagination
                if "?" in search_url:
                    paginated_url = f"{search_url}&page={page_num}"
                else:
                    paginated_url = f"{search_url}?page={page_num}"
                
                print(f"📄 Page {page_num}: {paginated_url}")
                
                await page.goto(paginated_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)  # Wait longer for content to load
                
                # Try multiple selectors for Blocket's structure
                listings = await page.evaluate('''() => {
                    const items = [];
                    
                    // Try multiple selectors for listings
                    const selectors = [
                        'article[data-testid*="listing"]',
                        'article[data-testid*="ad"]',
                        '[data-testid*="listing"]',
                        '[data-testid*="ad"]',
                        '.listing',
                        '.ad',
                        'article'
                    ];
                    
                    let articles = [];
                    for (const selector of selectors) {
                        articles = document.querySelectorAll(selector);
                        if (articles.length > 0) break;
                    }
                    
                    console.log('Found', articles.length, 'articles using selector');
                    
                    articles.forEach(article => {
                        try {
                            // Try multiple title selectors
                            const titleSelectors = [
                                '[data-testid="listing-title"]',
                                'h2', 'h3', '.title', '[class*="title"]',
                                'a[data-testid*="title"]'
                            ];
                            
                            let titleElem = null;
                            for (const selector of titleSelectors) {
                                titleElem = article.querySelector(selector);
                                if (titleElem) break;
                            }
                            
                            // Try multiple price selectors
                            const priceSelectors = [
                                '[data-testid="listing-price"]',
                                '.price', '[class*="price"]',
                                '[data-testid*="price"]'
                            ];
                            
                            let priceElem = null;
                            for (const selector of priceSelectors) {
                                priceElem = article.querySelector(selector);
                                if (priceElem) break;
                            }
                            
                            // Try multiple link selectors
                            const linkSelectors = [
                                'a[href*="/annons/"]',
                                'a[href*="/ad/"]',
                                'a[data-testid*="link"]'
                            ];
                            
                            let linkElem = null;
                            for (const selector of linkSelectors) {
                                linkElem = article.querySelector(selector);
                                if (linkElem) break;
                            }
                            
                            if (titleElem && priceElem && linkElem) {
                                const title = titleElem.textContent?.trim() || '';
                                const priceText = priceElem.textContent?.trim().replace(/\\s+/g, '') || '';
                                const price = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                                const url = linkElem.href;
                                
                                // Get image
                                const imageSelectors = ['img', '[data-testid*="image"]'];
                                let imageElem = null;
                                for (const selector of imageSelectors) {
                                    imageElem = article.querySelector(selector);
                                    if (imageElem) break;
                                }
                                const image = imageElem?.src || '';
                                
                                // Get location
                                const locationSelectors = [
                                    '[data-testid="listing-location"]',
                                    '.location', '[class*="location"]'
                                ];
                                let locationElem = null;
                                for (const selector of locationSelectors) {
                                    locationElem = article.querySelector(selector);
                                    if (locationElem) break;
                                }
                                const location = locationElem?.textContent?.trim() || '';
                                
                                // Generate ID from URL
                                const id = url.split('/').filter(Boolean).pop().split('?')[0];
                                
                                if (title && price > 0) {
                                    items.push({
                                        id: id,
                                        title: title,
                                        price: price,
                                        url: url,
                                        image: image,
                                        location: location,
                                        source: 'blocket'
                                    });
                                }
                            }
                        } catch (e) {
                            console.log('Error parsing article:', e);
                        }
                    });
                    
                    return items;
                }''')
                
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
        # For RTX 3080 search
        if price > PRICE_THRESHOLDS["rtx_3080"]:
            return False
        
        # Must contain relevant keywords
        has_keywords = any(keyword in title_lower for keyword in KEYWORDS["rtx_3080"])
        has_gpu = any(gpu_keyword in title_lower for gpu_keyword in ["rtx 3080", "3080", "geforce", "nvidia"])
        
        return has_keywords and has_gpu and price <= PRICE_THRESHOLDS["rtx_3080"]
    
    elif "xeon" in search_name.lower():
        # For Xeon workstation search
        if price > PRICE_THRESHOLDS["xeon_workstation"]:
            return False
        
        # Must contain relevant keywords
        has_keywords = any(keyword in title_lower for keyword in KEYWORDS["xeon_workstation"])
        has_cpu = any(cpu_keyword in title_lower for cpu_keyword in ["xeon", "xeon", "xeon"])
        
        return has_keywords and has_cpu and price <= PRICE_THRESHOLDS["xeon_workstation"]
    
    else:
        # For general computer search
        if price > PRICE_THRESHOLDS["stationary_computers"]:
            return False
        
        # Must contain relevant keywords
        has_keywords = any(keyword in title_lower for keyword in KEYWORDS["stationary_computers"])
        
        return has_keywords and price <= PRICE_THRESHOLDS["stationary_computers"]

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
