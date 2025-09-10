# discord_bot.py
import discord
from discord.ext import commands
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
import threading

# Set up bot with proper intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Discord bot logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

async def send_deal_alert(listing, ai_verdict):
    """Sends a rich embed message to Discord for a good deal."""
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            print(f"❌ Could not find Discord channel with ID {DISCORD_CHANNEL_ID}")
            return False
        
        # Create a nice-looking embed message
        embed = discord.Embed(
            title="🚨 HOT DEAL ALERT! 🚨",
            description=f"**{listing['title']}**",
            color=discord.Color.green(),
            url=listing['url']
        )
        
        embed.add_field(name="💰 Price", value=f"{listing['price']} SEK", inline=True)
        embed.add_field(name="🌐 Site", value=listing['site'].capitalize(), inline=True)
        embed.add_field(name="🔍 Query", value=listing['query'], inline=True)
        embed.add_field(name="🤖 AI Analysis", value=ai_verdict['reason'], inline=False)
        
        embed.set_footer(text="DealSniper AI • Good luck with the purchase!")
        
        await channel.send(embed=embed)
        print(f"✅ Discord alert sent for: {listing['title'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")
        return False

def start_bot():
    """Starts the Discord bot in a background thread"""
    def run_bot():
        try:
            bot.run(DISCORD_BOT_TOKEN)
        except Exception as e:
            print(f"❌ Discord bot failed to start: {e}")
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Discord bot starting in background...")
    return bot_thread