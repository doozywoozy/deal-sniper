# discord_webhook.py - REPLACES discord_bot.py
import aiohttp
import json
from config import DISCORD_WEBHOOK_URL

async def send_deal_alert(listing, ai_verdict, deal_type):
    """Sends deal alerts using Discord webhooks instead of bot."""
    try:
        # Different colors for different deal types
        color = 0x00FF00 if deal_type == "HOT" else 0x0099FF  # Green for HOT, Blue for GOOD
        emoji = "🔥" if deal_type == "HOT" else "✅"
        
        # Create embed message
        embed = {
            "title": f"{emoji} {deal_type} DEAL ALERT! {emoji}",
            "description": f"[{listing['title']}]({listing['url']})",
            "color": color,
            "fields": [
                {"name": "💰 Purchase Price", "value": f"{listing['price']} SEK", "inline": True},
                {"name": "🌐 Site", "value": listing['site'].capitalize(), "inline": True},
                {"name": "📈 Estimated Profit", "value": f"{ai_verdict['estimated_profit']} SEK ({ai_verdict['profit_percentage']}%)", "inline": True},
                {"name": "🔍 Query", "value": listing['query'], "inline": True},
                {"name": "🤖 AI Analysis", "value": ai_verdict['reason'], "inline": False},
                {"name": "📈 Market Value", "value": f"{ai_verdict['estimated_market_value']} SEK", "inline": True},
                {"name": "💰 Potential Profit", "value": f"{ai_verdict['estimated_profit']} SEK ({ai_verdict['profit_percentage']}%)", "inline": True},
                {"name": "🔍 Comparisons", "value": f"Based on {ai_verdict['comparison_count']} similar listings", "inline": True}
            ],
            "footer": {"text": "DealSniper AI • Flip wisely!"},
            "timestamp": None
        }

        async with aiohttp.ClientSession() as session:
            payload = {"embeds": [embed]}
            async with session.post(DISCORD_WEBHOOK_URL, json=payload) as response:
                if response.status == 204:
                    print(f"✅ {deal_type} deal alert sent via webhook!")
                    return True
                else:
                    print(f"❌ Webhook failed: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed to send webhook alert: {e}")
        return False

async def send_startup_message():
    """Send a startup message to Discord."""
    try:
        embed = {
            "title": "🚀 Deal Sniper Started",
            "description": "AI deal finder is now running and scanning for deals!",
            "color": 0x7289DA,  # Discord blue
            "footer": {"text": "DealSniper AI • Monitoring for profitable deals"}
        }

        async with aiohttp.ClientSession() as session:
            payload = {"embeds": [embed]}
            async with session.post(DISCORD_WEBHOOK_URL, json=payload) as response:
                if response.status == 204:
                    print("✅ Startup message sent via webhook!")
                    return True
                else:
                    print(f"❌ Startup webhook failed: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed to send startup alert: {e}")
        return False

async def send_summary_message(total_listings, hot_deals, good_deals):
    """Send a summary message to Discord."""
    try:
        if hot_deals > 0 or good_deals > 0:
            description = f"Found {hot_deals} 🔥 HOT deals and {good_deals} ✅ GOOD deals out of {total_listings} listings"
            color = 0x00FF00  # Green
        else:
            description = "No profitable deals found this time. Better luck next run!"
            color = 0xFF0000  # Red

        embed = {
            "title": "📊 Scan Complete",
            "description": description,
            "color": color,
            "footer": {"text": "DealSniper AI • Scan completed"}
        }

        async with aiohttp.ClientSession() as session:
            payload = {"embeds": [embed]}
            async with session.post(DISCORD_WEBHOOK_URL, json=payload) as response:
                if response.status == 204:
                    print("✅ Summary message sent via webhook!")
                    return True
                else:
                    print(f"❌ Summary webhook failed: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed to send summary alert: {e}")
        return False
