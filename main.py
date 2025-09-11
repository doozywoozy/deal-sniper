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
            embed["fields"].insert(1, {"name": "Location", "value": listing['location'], "inline': True})
        
        if listing.get('image'):
            embed["thumbnail"] = {"url": listing['image']}
        
        data = {"embeds": [embed], "username": "Deal Sniper Bot"}
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        
        if response.status_code == 204:
            logger.info(f"✅ Sent to Discord: {listing['title']}")
        else:
            logger.error(f"❌ Failed to send to Discord: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Failed to send Discord message: {e}")

async def send_startup_message():
    """Send startup message to Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        data = {"content": "🚀 Deal Sniper Bot started scanning...", "username": "Deal Sniper Bot"}
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        
        if response.status_code == 204:
            logger.info("✅ Startup message sent via webhook!")
        else:
            logger.error(f"❌ Failed to send startup message: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Failed to send startup message: {e}")

async def send_summary_message(total_listings: int, new_listings: int):
    """Send summary message to Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        if new_listings > 0:
            message = f"✅ Scan completed! Found {new_listings} new deals out of {total_listings} listings."
        else:
            message = f"ℹ️ Scan completed. Checked {total_listings} listings but no new deals found."
        
        data = {"content": message, "username": "Deal Sniper Bot"}
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        
        if response.status_code == 204:
            logger.info("✅ Summary message sent via webhook!")
        else:
            logger.error(f"❌ Failed to send summary message: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Failed to send summary message: {e}")

def get_search_name_for_listing(listing: Dict, searches: List[Dict]) -> str:
    """Determine which search found this listing"""
    title_lower = listing['title'].lower()
    
    for search in searches:
        search_name_lower = search['name'].lower()
        search_words = search_name_lower.split()
        if any(word in title_lower for word in search_words):
            return search['name']
    
    return "Unknown Search"

async def main():
    """Main function to run the deal sniper bot"""
    logger.info("🚀 Starting scraping process...")
    
    # Send startup message
    await send_startup_message()
    
    # Your search configurations
    searches = [
        {
            "name": "Gaming PC RTX 3080",
            "url": "https://www.blocket.se/annonser/hela_sverige?q=rtx+3080&price_end=8000"
        },
        {
            "name": "All Stationary Computers", 
            "url": "https://www.blocket.se/annonser/hela_sverige/elektronik/datorer_tv_spel/stationara_datorer?cg=5021"
        },
        {
            "name": "Workstation Xeon",
            "url": "https://www.blocket.se/annonser/hela_sverige?q=xeon+workstation&price_end=5000"
        }
    ]
    
    all_new_listings = []
    total_scanned = 0
    
    for search in searches:
        logger.info(f"\n⚡ Fast scanning blocket for {search['name']}")
        new_listings = await scraper.scrape_blocket_fast(search['url'], search['name'])
        all_new_listings.extend(new_listings)
        
        # Count total scanned listings
        total_scanned += len(new_listings) * 3
        
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
    
    # Send summary message
    await send_summary_message(total_scanned, len(all_new_listings))
    
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
    
    # Reinitialize database
    import database
    database.init_database()
    
    # Create screenshots directory
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    # Run main
    asyncio.run(main())
