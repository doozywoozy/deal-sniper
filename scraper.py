# scraper.py
import asyncio
from playwright.async_api import async_playwright
from config import SEARCH_QUERIES
import database
import re
import time

async def scrape_blocket_fast(query, max_price):
    """High-speed Blocket scraper with parallel processing."""
    listings = []
    async with async_playwright() as p:
        # Launch browser with performance optimizations
        browser = await p.chromium.launch(
            headless=True,  # Headless is much faster
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-software-rasterizer',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-zygote',
                '--single-process'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='sv-SE',
            # Disable images and styles for faster loading
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'sv-SE,sv;q=0.8,en-US;q=0.5,en;q=0.3',
            }
        )
        
        page = await context.new_page()
        
        # Build URL
        if query["query"].strip():
            search_query = query["query"].replace(" ", "+")
            base_url = f"https://www.blocket.se/annonser/hela_sverige?q={search_query}&price_end={max_price}"
        else:
            base_url = "https://www.blocket.se/annonser/hela_sverige/elektronik/datorer_tv_spel/stationara_datorer?cg=5021"
        
        print(f"🚀 Fast scraping: {base_url}")
        start_time = time.time()
        
        try:
            # Only scrape first page for speed (most new listings are here)
            url = base_url
            print(f"📄 Page 1: {url}")
            
            # Navigate with minimal waiting
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for articles to load with shorter timeout
            try:
                await page.wait_for_selector('article', timeout=10000)
            except:
                print("Articles not found, continuing anyway")
            
            # Get all article elements quickly
            articles = await page.query_selector_all('article')
            print(f"Found {len(articles)} articles")
            
            if not articles:
                print("No articles found")
                return []
            
            # Process articles in parallel for speed
            processing_tasks = []
            for i, article in enumerate(articles):
                processing_tasks.append(process_article(article, query, max_price, i))
            
            # Wait for all articles to process concurrently
            results = await asyncio.gather(*processing_tasks, return_exceptions=True)
            
            # Collect valid results
            for result in results:
                if isinstance(result, dict) and result.get('valid', False):
                    listings.append(result['listing'])
                    
        except Exception as e:
            print(f"Scraping failed: {e}")
        finally:
            await browser.close()
    
    scan_time = time.time() - start_time
    print(f"⚡ Scanned {len(articles)} articles in {scan_time:.2f} seconds")
    print(f"🎯 Total valid listings found: {len(listings)}")
    return listings

async def process_article(article, query, max_price, index):
    """Process a single article quickly and return result."""
    try:
        # Get text content quickly
        full_text = await article.text_content()
        
        # Quick filtering
        if len(full_text) < 30 or any(x in full_text for x in ['relevans', 'sortera', 'filter', 'kategori']):
            return {'valid': False}
        
        # Fast title extraction
        title_elem = await article.query_selector('h2')
        if not title_elem:
            return {'valid': False}
        
        title = await title_elem.text_content()
        title = title.strip()
        if len(title) < 5:
            return {'valid': False}
        
        # Fast price extraction
        price_match = re.search(r'(\d{1,3}(?:\s\d{3})*)\s*kr', full_text)
        if not price_match:
            return {'valid': False}
        
        price_text = price_match.group(1)
        clean_price = re.sub(r'[^\d]', '', price_text.replace('\xa0', '').replace(' ', ''))
        if not clean_price:
            return {'valid': False}
        
        price = float(clean_price)
        if price < 100 or price > max_price:
            return {'valid': False}
        
        # Fast URL extraction
        link_elem = await article.query_selector('a[href*="/annons/"]')
        if not link_elem:
            return {'valid': False}
        
        href = await link_elem.get_attribute('href')
        if not href:
            return {'valid': False}
        
        url_link = f"https://www.blocket.se{href}" if href.startswith("/") else href
        if "blocket.se" not in url_link:
            return {'valid': False}
        
        listing_id = f"blocket_{hash(url_link)}"
        
        # Quick database check
        try:
            if database.db["seen_listings"].get(listing_id):
                return {'valid': False}
        except:
            pass  # Item doesn't exist yet - this is good
        
        return {
            'valid': True,
            'listing': {
                "id": listing_id,
                "site": "blocket",
                "title": title,
                "price": price,
                "url": url_link,
                "query": query["name"]
            }
        }
        
    except Exception as e:
        # Silent fail for speed - we don't want errors slowing us down
        return {'valid': False}

async def scrape_facebook_simple(query, max_price):
    """Simplified Facebook scraper."""
    return []  # Skip for speed

async def scrape_ebay_simple(query, max_price):
    """Simplified eBay scraper."""
    return []  # Skip for speed

async def main_scraper():
    """Main scraping function optimized for speed."""
    all_listings = []
    total_start = time.time()
    
    for query in SEARCH_QUERIES:
        for site in query["sites"]:
            if site == "blocket":  # Focus only on Blocket for speed
                print(f"\n⚡ Fast scanning {site} for {query['name']}")
                try:
                    listings = await scrape_blocket_fast(query, query["max_price"])
                    all_listings.extend(listings)
                    print(f"Found {len(listings)} new listings on {site}")
                except Exception as e:
                    print(f"Error scraping {site}: {e}")
                    continue
    
    total_time = time.time() - total_start
    print(f"\n🚀 Total scan completed in {total_time:.2f} seconds")
    print(f"📊 Total new listings found: {len(all_listings)}")
    return all_listings