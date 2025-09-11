# main.py
import asyncio
import os
import json
import requests
from typing import List, Dict
from logger import logger, setup_logger, log_github_actions_info
import scraper
import database
from config import DISCORD_WEBHOOK_URL, SCREENSHOT_DIR

# Setup logger
setup_logger()
log_github_actions_info()

async def send_discord_message(listing: Dict, search_name: str):
    """Send a listing to Discord via webhook"""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("No Discord webhook URL configured")
        return
    
    try:
        embed = {
            "title": listing['title'][:256],
            "url": listing['url'],
            "color": 65280 if listing['price'] < 5000 else 16753920,
            "fields": [
                {"name": "Price", "value": f"{listing['price']} SEK", "inline": True},
                {"name": "Source", "value": listing['source'], "inline": True},
                {"name": "Search", "value": search_name, "inline": False}
            ],
            "footer": {"text": "Deal Sniper Bot 🤖"}
        }
        
        if listing.get('location'):
            embed["fields"].insert(1, {"name": "Location", "value": listing['location'], "inline": True})
        
        if listing.get('image'):
            embed["image"] = {"url": listing['image']}
            
        payload = {"embeds": [embed]}
        
        async with requests.Session() as session:
            response = await asyncio.to_thread(session.post, DISCORD_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logger.info("✅ Discord message sent!")
            
    except requests.exceptions.HTTPError as errh:
        logger.error(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        logger.error(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        logger.error(f"OOps: Something Else {err}")
        
def get_search_name_for_listing(listing: Dict, searches: List[Dict]) -> str:
    """Find the search name for a given listing based on its query."""
    for search in searches:
        if listing['query'] == search['name']:
            return search['name']
    return "Unknown Search"

async def main():
    """Main function to run the scraping and analysis process."""
    logger.info("🚀 Starting scraping process...")
    
    # Example searches (you can customize these)
    searches = [
        {"name": "Gaming PC RTX 3080", "query": "rtx 3080", "price_end": 8000},
        {"name": "All Stationary Computers", "query": "stationär dator", "price_end": 10000},
        {"name": "Workstation Xeon", "query": "xeon workstation", "price_end": 5000}
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
        
        # Send each listing to Discord
        for listing in all_new_listings:
            search_name = get_search_name_for_listing(listing, searches)
            await send_discord_message(listing, search_name)
            await asyncio.sleep(1)
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
