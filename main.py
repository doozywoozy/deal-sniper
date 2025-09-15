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

# Import the webhook functions
try:
    from discord_webhook import send_deal_alert, send_startup_message, send_summary_message
except ImportError:
    logger.warning("Discord webhook module not found, using fallback")
    # Fallback implementation if webhook module is not available
    async def send_deal_alert(listing, ai_verdict, deal_type):
        logger.info(f"Would send {deal_type} deal alert: {listing['title']}")
        return True
        
    async def send_startup_message():
        logger.info("Bot started up")
        return True
        
    async def send_summary_message(total_listings, hot_deals, good_deals):
        logger.info(f"Scan complete: {total_listings} listings, {hot_deals} hot deals, {good_deals} good deals")
        return True

# Setup logger
setup_logger()
log_github_actions_info()

async def main():
    """Main function to run the scraping and analysis process."""
    logger.info("🚀 Starting Deal Sniper Bot...")
    
    # Send startup message
    await send_startup_message()
    
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
    
    hot_deals_count = 0
    good_deals_count = 0
    
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
                if ai_verdict['verdict'] == "HOT DEAL":
                    hot_deals_count += 1
                    await send_deal_alert(listing, ai_verdict, "HOT")
                    await asyncio.sleep(2)  # Delay to avoid rate limiting
                elif ai_verdict['verdict'] == "GOOD DEAL":
                    good_deals_count += 1
                    await send_deal_alert(listing, ai_verdict, "GOOD")
                    await asyncio.sleep(2)  # Delay to avoid rate limiting
            except Exception as e:
                logger.error(f"Failed to analyze listing {listing['title']}: {e}")
    else:
        logger.info("No new listings to analyze. Exiting.")
    
    # Send summary message
    await send_summary_message(len(all_new_listings), hot_deals_count, good_deals_count)
    
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
