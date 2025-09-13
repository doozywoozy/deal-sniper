# main.py
import asyncio
import os
import json
import aiohttp
from typing import List, Dict
from logger import logger, setup_logger, log_github_actions_info
import scraper
import database
from config import DISCORD_WEBHOOK_URL, SCREENSHOT_DIR

# Setup logger
setup_logger()
log_github_actions_info()

async def send_discord_message(listing: Dict, search_name: str, deal_type: str, profit_sek: float, profit_pct: float):
    """Send a listing to Discord via webhook with deal type and profit info"""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("No Discord webhook URL configured")
        return
    
    try:
        embed = {
            "title": listing['title'][:256],
            "url": listing['url'],
            "color": 65280 if deal_type == "Hot Deal" else 16776960 if deal_type == "Good Deal" else 16753920,
            "fields": [
                {"name": "Price", "value": f"{listing['price']} SEK", "inline": True},
                {"name": "Source", "value": listing['source'], "inline": True},
                {"name": "Search", "value": search_name, "inline": False},
                {"name": "Deal Type", "value": deal_type, "inline": True},
                {"name": "Profit SEK", "value": f"{profit_sek:.2f} SEK", "inline": True},
                {"name": "Profit %", "value": f"{profit_pct:.2f}%", "inline": True}
            ],
            "footer": {"text": "Deal Sniper Bot 🤖"}
        }
        
        if listing.get('location'):
            embed["fields"].insert(1, {"name": "Location", "value": listing['location'], "inline": True})
        
        if listing.get('image'):
            embed["image"] = {"url": listing['image']}
            
        payload = {"embeds": [embed]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=payload) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limited (429). Waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    async with session.post(DISCORD_WEBHOOK_URL, json=payload) as retry_response:
                        if retry_response.status != 200:
                            logger.error(f"Failed to send message after retry: {retry_response.status}")
                        else:
                            logger.info("✅ Discord message sent after retry!")
                elif response.status == 204:
                    logger.warning("Received 204 No Content from Discord. Payload might be empty or malformed.")
                elif response.status != 200:
                    logger.error(f"Failed to send message: {response.status}")
                else:
                    logger.info("✅ Discord message sent!")
            
    except aiohttp.ClientError as err:
        logger.error(f"Network error occurred: {err}")
    except Exception as err:
        logger.error(f"Unexpected error: {err}")

def get_search_name_for_listing(listing: Dict, searches: List[Dict]) -> str:
    """Find the search name for a given listing based on its query."""
    for search in searches:
        if listing['query'] == search['name']:
            return search['name']
    return "Unknown Search"

def evaluate_deal(listing: Dict, base_cost: float) -> tuple:
    """Evaluate if a listing is a good or hot deal and calculate profit."""
    if not base_cost or base_cost <= 0:
        logger.warning(f"Invalid base cost for listing {listing['title']}. Using price as fallback.")
        base_cost = listing['price'] * 0.5  # Fallback to 50% of price if no better data
    
    profit_sek = listing['price'] - base_cost
    profit_pct = (profit_sek / base_cost) * 100 if base_cost > 0 else 0
    
    if profit_sek <= 0:
        return "Bad Deal", profit_sek, profit_pct
    elif profit_pct >= 50:
        return "Hot Deal", profit_sek, profit_pct
    elif profit_pct >= 20:
        return "Good Deal", profit_sek, profit_pct
    return "Bad Deal", profit_sek, profit_pct

async def main():
    """Main function to run the scraping and analysis process."""
    logger.info("🚀 Starting scraping process...")
    
    # Example searches with base costs (customize these based on your data)
    searches = [
        {"name": "Gaming PC RTX 3080", "query": "rtx 3080", "price_end": 8000, "base_cost": 4000},
        {"name": "All Stationary Computers", "query": "stationär dator", "price_end": 10000, "base_cost": 5000},
        {"name": "Workstation Xeon", "query": "xeon workstation", "price_end": 5000, "base_cost": 2500}
    ]
    
    # Initialize database
    database.init_database()
    
    all_new_listings = []
    
    # Process each search
    for search in searches:
        # Pass the full search dictionary to the scraper function
        new_listings = await scraper.scrape_blocket(search)
        
        if new_listings:
            all_new_listings.extend(new_listings)
            
        logger.info(f"Found {len(new_listings)} new listings on blocket for {search['name']}")
    
    logger.info(f"\n🚀 Total scan completed")
    logger.info(f"📊 Total new listings found: {len(all_new_listings)}")
    
    # Process new listings
    if all_new_listings:
        logger.info(f"Found {len(all_new_listings)} new listings.")
        
        # Filter and evaluate deals using search-specific base costs
        for listing in all_new_listings:
            search_name = get_search_name_for_listing(listing, searches)
            search = next((s for s in searches if s['name'] == search_name), searches[0])  # Default to first search if not found
            base_cost = search.get('base_cost', listing['price'] * 0.5)  # Use search base_cost or fallback
            deal_type, profit_sek, profit_pct = evaluate_deal(listing, base_cost)
            
            # Only send if it's a Good or Hot deal
            if deal_type in ["Good Deal", "Hot Deal"]:
                await send_discord_message(listing, search_name, deal_type, profit_sek, profit_pct)
                await asyncio.sleep(2)  # Increased delay to avoid rate limiting
    else:
        logger.info("No new listings to analyze. Exiting.")
    
    # Cleanup old listings
    try:
        database.cleanup_old_listings(30)
    except Exception as e:
        logger.warning(f"⚠️ Could not cleanup old listings: {e}")

if __name__ == "__main__":
    # Delete old database to fix schema issues
    import os
    if os.path.exists("listings.db"):
        os.remove("listings.db")
        logger.info("🧹 Removed old database to fix schema issues")
    
    asyncio.run(main())
