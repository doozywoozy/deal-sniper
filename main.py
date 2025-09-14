# main.py
import asyncio
import os
import aiohttp
from typing import List, Dict
from logger import logger, setup_logger, log_github_actions_info
import scraper
import database
from config import DISCORD_WEBHOOK_URL, SCREENSHOT_DIR, PRICE_THRESHOLDS, KEYWORDS
try:
    from ai_judge import analyze_listing  # Explicitly import the function
except ImportError as e:
    logger.error(f"Failed to import analyze_listing from ai_judge: {e}")
    raise

# Setup logger
setup_logger()
log_github_actions_info()

async def send_discord_message(listing: Dict, search_name: str, ai_verdict: Dict):
    """Send a listing to Discord via webhook with AI verdict details"""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("No Discord webhook URL configured")
        return
    
    try:
        deal_type = ai_verdict.get('verdict', 'Unknown')
        profit_sek = ai_verdict.get('estimated_profit', 0.0)
        profit_pct = ai_verdict.get('profit_percentage', 0.0)
        reason = ai_verdict.get('reason', 'No reason provided')
        
        embed = {
            "title": listing['title'][:256],
            "url": listing['url'],
            "color": 65280 if deal_type == "HOT DEAL" else 16776960 if deal_type == "GOOD DEAL" else 16753920,
            "fields": [
                {"name": "Price", "value": f"{listing['price']} SEK", "inline": True},
                {"name": "Source", "value": listing.get('site', 'Unknown'), "inline": True},
                {"name": "Search", "value": search_name, "inline": False},
                {"name": "Deal Type", "value": deal_type, "inline": True},
                {"name": "Profit SEK", "value": f"{profit_sek:.2f} SEK", "inline": True},
                {"name": "Profit %", "value": f"{profit_pct:.2f}%", "inline": True},
                {"name": "AI Reasoning", "value": reason[:1024], "inline": False},
                {"name": "Comparisons", "value": str(ai_verdict.get('comparison_count', 0)), "inline": True}
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
                        if retry_response.status in [200, 204]:
                            logger.info("✅ Discord message sent after retry!")
                        else:
                            logger.error(f"Failed to send message after retry: {retry_response.status}")
                elif response.status in [200, 204]:
                    logger.info("✅ Discord message sent!")
                else:
                    response_text = await response.text()
                    logger.error(f"Failed to send message: {response.status} - Response: {response_text}")
            
    except aiohttp.ClientError as err:
        logger.error(f"Network error occurred: {err}")
    except Exception as err:
        logger.error(f"Unexpected error: {err}")

def get_search_name_for_listing(listing: Dict, searches: List[Dict]) -> str:
    """Find the search name for a given listing based on its query."""
    for search_name, keywords in KEYWORDS.items():
        if any(keyword in listing['title'].lower() or keyword in listing.get('query', '').lower() for keyword in keywords):
            return search_name.replace('_', ' ').title()
    return "Unknown Search"

async def main():
    """Main function to run the scraping and analysis process."""
    logger.info("🚀 Starting Deal Sniper Bot...")
    
    # Define searches based on config
    searches = [
        {"name": "Gaming PC RTX 3080", "query": "rtx 3080", "price_end": PRICE_THRESHOLDS["rtx_3080"]},
        {"name": "All Stationary Computers", "query": "stationär dator", "price_end": PRICE_THRESHOLDS["stationary_computers"]},
        {"name": "Workstation Xeon", "query": "xeon workstation", "price_end": PRICE_THRESHOLDS["xeon_workstation"]}
    ]
    
    # Initialize database
    database.init_database()
    
    all_new_listings = []
    
    # Process each search
    for search in searches:
        new_listings = await scraper.scrape_blocket(search)
        if new_listings:
            all_new_listings.extend(new_listings)
        logger.info(f"Found {len(new_listings)} new listings on blocket for {search['name']}")
    
    logger.info(f"\n🚀 Total scan completed")
    logger.info(f"📊 Total new listings found: {len(all_new_listings)}")
    
    # Process and evaluate all listings with AI
    if all_new_listings:
        logger.info(f"Evaluating {len(all_new_listings)} new listings with AI...")
        
        for listing in all_new_listings:
            try:
                # AI analyzes each listing using real-time data and component prices
                ai_verdict = await analyze_listing(listing)
                logger.info(f"AI Verdict for {listing['title']}: {ai_verdict['verdict']} | "
                           f"Profit SEK: {ai_verdict['estimated_profit']} | "
                           f"Profit %: {ai_verdict['profit_percentage']} | "
                           f"Reason: {ai_verdict['reason']} | Comparisons: {ai_verdict['comparison_count']}")
                
                # Only send GOOD DEAL or HOT DEAL to Discord
                if ai_verdict['verdict'] in ["GOOD DEAL", "HOT DEAL"]:
                    search_name = get_search_name_for_listing(listing, searches)
                    await send_discord_message(listing, search_name, ai_verdict)
                    await asyncio.sleep(2)  # Delay to avoid rate limiting
            except Exception as e:
                logger.error(f"Failed to analyze listing {listing['title']}: {e}")
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
