# config.py - UPDATED FOR WEBHOOK
import os

# SEARCH CONFIGURATION
SEARCH_QUERIES = [
    {
        "name": "Gaming PC RTX 3080",
        "sites": ["blocket"],
        "query": "rtx 3080",
        "max_price": 8000,
        "max_pages": 2,
        "condition": "used"
    },
    {
        "name": "All Stationary Computers", 
        "sites": ["blocket"],
        "query": "",
        "max_price": 15000,
        "max_pages": 1,
        "condition": "used"
    },
    {
        "name": "Workstation Xeon",
        "sites": ["blocket"], 
        "query": "xeon workstation",
        "max_price": 5000,
        "max_pages": 2,
        "condition": "used"
    }
]

# Performance settings optimized for GitHub
SCRAPE_TIMEOUT = 20000  # 20 seconds
REQUEST_DELAY = 1.5     # 1.5 seconds between requests
MAX_CONCURRENT_REQUESTS = 4  # Higher concurrency

# AI Configuration - USE SMALLER MODEL FOR SPEED
OLLAMA_MODEL = "mistral:7b"  # Faster than full mistral
OLLAMA_BASE_URL = "http://localhost:11434"

# Discord Webhook Configuration
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/1415061850240061618/mMqXX1NORtqhl_3WeLhhcj52i2M46vSOd0tO2Y9s0xkkSRMQVVQK-LfuL58TeoIv5f_n')

# Database
DATABASE_PATH = "listings.db"
