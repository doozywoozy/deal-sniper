# config.py
import os

# Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# AI Settings
OLLAMA_BASE_URL = "http://localhost:11434"
AI_MODEL = "mistral:7b"

# Scraping settings
MAX_PAGES_TO_SCRAPE = 5  # Number of pages to scrape per search
REQUEST_DELAY = 1  # Delay between requests in seconds

# Profitability thresholds (in SEK)
PRICE_THRESHOLDS = {
    "rtx_3080": 8000,
    "stationary_computers": 20000,
    "xeon_workstation": 5000
}

# Keywords for filtering
KEYWORDS = {
    "rtx_3080": ["rtx 3080", "3080", "gaming", "dator", "computer"],
    "stationary_computers": ["dator", "computer", "pc", "stationär"],
    "xeon_workstation": ["xeon", "workstation", "server", "workstation"]
}

# Database path
DATABASE_PATH = "listings.db"
