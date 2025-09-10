# main.py - UPDATED FOR WEBHOOK
import asyncio
import database
from scraper import main_scraper
from ai_judge import analyze_listing
from discord_webhook import send_deal_alert, send_startup_message, send_summary_message
from datetime import datetime

async def main_scraping_logic():
    """Main scraping and analysis logic"""
    print("🚀 Starting scraping process...")
    
    # Send startup message to Discord
    await send_startup_message()
    
    new_listings = await main_scraper()
    print(f"Found {len(new_listings)} new listings.")
    
    if not new_listings:
        print("No new listings to analyze. Exiting.")
        await send_summary_message(0, 0, 0)
        return
    
    # Analyze each listing with AI
    hot_deals = 0
    good_deals = 0
    
    for listing in new_listings:
        print(f"🤖 Analyzing: {listing['title'][:50]}...")
        verdict = await analyze_listing(listing)
        print(f"   AI Verdict: {verdict['verdict']} - {verdict['reason']}")
        
        # Handle different verdict levels
        if verdict["verdict"].upper() == "HOT":
            print(f"!!! 🔥 HOT DEAL FOUND: {listing['title']}")
            await send_deal_alert(listing, verdict, "HOT")
            hot_deals += 1
        elif verdict["verdict"].upper() == "GOOD":
            print(f"!!! ✅ GOOD DEAL FOUND: {listing['title']}")
            await send_deal_alert(listing, verdict, "GOOD")
            good_deals += 1
        
        # Store in database
        database.db["seen_listings"].insert({
            "id": listing['id'],
            "site": listing['site'],
            "title": listing['title'],
            "price": listing['price'],
            "url": listing['url'],
            "created": datetime.now().isoformat()
        })

    # Send summary message
    await send_summary_message(len(new_listings), hot_deals, good_deals)
    
    print(f"Deal sniper run completed! Found {hot_deals} hot deals and {good_deals} good deals.")

async def main():
    """Main function that runs the scraper"""
    # Run the scraping logic
    await main_scraping_logic()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
