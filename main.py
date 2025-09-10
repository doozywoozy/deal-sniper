# main.py
import asyncio
import logging
from typing import List, Dict
from discord_webhook import DiscordWebhook, DiscordEmbed
import scraper
import database
from config import DISCORD_WEBHOOK_URL

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_discord_message(listing: Dict, search_name: str):
    """Send a listing to Discord via webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook URL configured")
        return
    
    try:
        # Create webhook
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)
        
        # Create embed
        embed = DiscordEmbed(
            title=listing['title'][:256],
            url=listing['url'],
            color="00ff00" if listing['price'] < 5000 else "ff9900"
        )
        
        embed.add_embed_field(name="Price", value=f"{listing['price']} SEK", inline=True)
        if listing.get('location'):
            embed.add_embed_field(name="Location", value=listing['location'], inline=True)
        embed.add_embed_field(name="Source", value=listing['source'], inline=True)
        embed.add_embed_field(name="Search", value=search_name, inline=False)
        
        if listing.get('image'):
            embed.set_image(url=listing['image'])
        
        embed.set_footer(text="Deal Sniper Bot 🤖")
        
        webhook.add_embed(embed)
        webhook.execute()
        print(f"✅ Sent to Discord: {listing['title']}")
        
    except Exception as e:
        print(f"❌ Failed to send Discord message: {e}")

async def send_startup_message():
    """Send startup message to Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content="🚀 Deal Sniper Bot started scanning...")
        webhook.execute()
        print("✅ Startup message sent via webhook!")
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
        
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=message)
        webhook.execute()
        print("✅ Summary message sent via webhook!")
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
    
    # Cleanup old listings
    database.cleanup_old_listings(30)

if __name__ == "__main__":
    asyncio.run(main())
