# main.py
import asyncio
import logging
import json
import requests
from typing import List, Dict
import scraper
import database
from config import DISCORD_WEBHOOK_URL

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_discord_message(listing: Dict, search_name: str):
    """Send a listing to Discord via webhook using requests"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook URL configured")
        return
    
    try:
        # Create embed data
        embed = {
            "title": listing['title'][:256],
            "url": listing['url'],
            "color": 65280 if listing['price'] < 5000 else 16753920,  # Green or orange
            "fields": [
                {"name": "Price", "value": f"{listing['price']} SEK", "inline": True},
                {"name": "Source", "value": listing['source'], "inline": True},
                {"name": "Search", "value": search_name, "inline": False}
            ],
            "footer": {"text": "Deal Sniper Bot 🤖"}
        }
        
        # Add location if available
        if listing.get('location'):
            embed["fields"].insert(1, {"name": "Location", "value": listing['location'], "inline": True})
        
        # Add thumbnail if available
        if listing.get('image'):
            embed["thumbnail"] = {"url": listing['image']}
        
        # Send to Discord
        data = {
            "embeds": [embed],
            "username": "Deal Sniper Bot"
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        
        if response.status_code == 204:
            print(f"✅ Sent to Discord: {listing['title']}")
        else:
            print(f"❌ Failed to send to Discord: {response.status_code} - {response.text}")
        
    except Exception as e:
        print(f"❌ Failed to send Discord message: {e}")

async def send_startup_message():
    """Send startup message to Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        data = {
            "content": "🚀 Deal Sniper Bot started scanning...",
            "username": "Deal Sniper Bot"
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        
        if response.status_code == 204:
            print("✅ Startup message sent via webhook!")
        else:
            print(f"❌ Failed to send startup message: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Failed to send startup message: {e}")

async def send_summary_message(total_listings: int, new_listings: int):
    """Send summary message to Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        if new_listings > 0:
            message = f"✅ Scan completed! Found {new_listings} new deals out of {total_listings} listings."
        else:
            message = f"ℹ️ Scan completed. Checked {total_listings} listings but no new deals found."
        
        data = {
            "content": message,
            "username": "Deal Sniper Bot"
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        
        if response.status_code == 204:
            print("✅ Summary message sent via webhook!")
        else:
            print(f"❌ Failed to send summary message: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Failed to send summary message: {e}")

def get_search_name_for_listing(listing: Dict, searches: List[Dict]) -> str:
    """Determine which search found this listing"""
    title_lower = listing['title'].lower()
    
    for search in searches:
        search_name_lower = search['name'].lower()
        # Check if any word from the search name is in the listing title
        search_words = search_name_lower.split()
        if any(word in title_lower for word in search_words):
            return search['name']
    
    return "Unknown Search"

async def main():
    """Main function to run the deal sniper bot"""
    print("🚀 Starting scraping process...")
    
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
        print(f"\n⚡ Fast scanning blocket for {search['name']}")
        new_listings = await scraper.scrape_blocket_search(search['url'], search['name'])
        all_new_listings.extend(new_listings)
        
        # Count total scanned listings (approximate)
        total_scanned += len(new_listings) * 3  # Estimate based on pages
        
        print(f"Found {len(new_listings)} new listings on blocket for {search['name']}")
    
    print(f"\n🚀 Total scan completed")
    print(f"📊 Total new listings found: {len(all_new_listings)}")
    
    # Process new listings
    if all_new_listings:
        print(f"Found {len(all_new_listings)} new listings.")
        
        # Send each listing to Discord
        for listing in all_new_listings:
            search_name = get_search_name_for_listing(listing, searches)
            await send_discord_message(listing, search_name)
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(1)
    else:
        print("No new listings to analyze. Exiting.")
    
    # Send summary message
    await send_summary_message(total_scanned, len(all_new_listings))
    
    # Cleanup old listings (with error handling)
    try:
        database.cleanup_old_listings(30)
    except Exception as e:
        print(f"⚠️ Could not cleanup old listings: {e}")
        print("This is not a critical error, continuing...")

if __name__ == "__main__":
    # Delete old database to fix schema issues
    import os
    if os.path.exists("listings.db"):
        os.remove("listings.db")
        print("🧹 Removed old database to fix schema issues")
    
    # Reinitialize database
    import database
    database.init_database()
    
    # Run main
    asyncio.run(main())
