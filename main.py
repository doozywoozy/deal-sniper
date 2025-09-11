# main.py
import asyncio
import os
import json
import requests
from typing import List, Dict
from logger import logger, setup_logger
import scraper
import database
from config import DISCORD_WEBHOOK_URL, SCREENSHOT_DIR

# Setup logger
setup_logger()

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
        
        if response.status_code == 204
