# config.py
import os

# Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# AI Settings
OLLAMA_BASE_URL = "http://localhost:11434"
AI_MODEL = "mistral:7b"

# Scraping settings
MAX_PAGES_TO_SCRAPE = 3
REQUEST_DELAY = 3  # Increased delay
SCRAPE_TIMEOUT = 30000
ENABLE_SCREENSHOTS = True  # Enable screenshot capture
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR

# Profitability thresholds (in SEK)
PRICE_THRESHOLDS = {
    "rtx_3080": 8000,
    "stationary_computers": 10000,
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
LOG_FILE = "scraper.log"
SCREENSHOT_DIR = "screenshots"
