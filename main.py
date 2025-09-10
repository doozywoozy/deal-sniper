# main.py
import asyncio
import discord
from discord.ext import commands
import database
from scraper import main_scraper
from ai_judge import analyze_listing
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from datetime import datetime

# Set up Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Discord bot logged in as {bot.user}')

async def send_deal_alert(listing, ai_verdict, deal_type):
    """Sends a rich embed message to Discord for good deals."""
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            print(f"❌ Could not find Discord channel with ID {DISCORD_CHANNEL_ID}")
            return False
        
        # Different colors for different deal types
        color = discord.Color.green() if deal_type == "HOT" else discord.Color.blue()
        emoji = "🔥" if deal_type == "HOT" else "✅"
        
        # Create embed message
        embed = discord.Embed(
            title=f"{emoji} {deal_type} DEAL ALERT! {emoji}",
            description=f"**{listing['title']}**",
            color=color,
            url=listing['url']
        )
        
        embed.add_field(name="💰 Purchase Price", value=f"{listing['price']} SEK", inline=True)
        embed.add_field(name="🌐 Site", value=listing['site'].capitalize(), inline=True)
        embed.add_field(name="📈 Estimated Profit", value=f"{ai_verdict['estimated_profit']} SEK ({ai_verdict['profit_percentage']}%)", inline=True)
        embed.add_field(name="🔍 Query", value=listing['query'], inline=True)
        embed.add_field(name="🤖 AI Analysis", value=ai_verdict['reason'], inline=False)
        embed.add_field(name="📈 Market Value", value=f"{ai_verdict['estimated_market_value']} SEK", inline=True)
        embed.add_field(name="💰 Potential Profit", value=f"{ai_verdict['estimated_profit']} SEK ({ai_verdict['profit_percentage']}%)", inline=True)
        embed.add_field(name="🔍 Comparisons", value=f"Based on {ai_verdict['comparison_count']} similar listings", inline=True)
        
        embed.set_footer(text="DealSniper AI • Flip wisely!")
        
        await channel.send(embed=embed)
        print(f"✅ {deal_type} deal alert sent for: {listing['title'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")
        return False

async def main_scraping_logic():
    """Main scraping and analysis logic"""
    print("🚀 Starting scraping process...")
    new_listings = await main_scraper()
    print(f"Found {len(new_listings)} new listings.")
    
    if not new_listings:
        print("No new listings to analyze. Exiting.")
        return
    
    # Send a startup message to Discord
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(f"🔍 Starting analysis of {len(new_listings)} new listings...")
    
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
        
        # Store in database (commented out for testing)
        # database.db["seen_listings"].insert({
        #     "id": listing['id'],
        #     "site": listing['site'],
        #     "title": listing['title'],
        #     "price": listing['price'],
        #     "url": listing['url'],
        #     "created": datetime.now().isoformat()
        # })

    # Send summary message
    if channel:
        if hot_deals > 0 or good_deals > 0:
            summary = f"📊 **Scan Complete:** Found {hot_deals} 🔥 HOT deals and {good_deals} ✅ GOOD deals out of {len(new_listings)} listings"
            await channel.send(summary)
        else:
            await channel.send("❌ No profitable deals found this time. Better luck next run!")
    
    print(f"Deal sniper run completed! Found {hot_deals} hot deals and {good_deals} good deals.")

async def run_bot():
    """Run the Discord bot"""
    try:
        await bot.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"❌ Discord bot error: {e}")

async def main():
    """Main function that runs both bot and scraper"""
    # Create tasks for both bot and scraper
    bot_task = asyncio.create_task(run_bot())
    
    # Wait a moment for bot to connect
    await asyncio.sleep(3)
    
    # Run the scraping logic
    await main_scraping_logic()
    
    # Keep the bot running for a bit to ensure messages are sent
    await asyncio.sleep(5)
    
    # Close the bot gracefully
    await bot.close()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())