# config.py
# SEARCH CONFIGURATION
# config.py
# SEARCH CONFIGURATION
# In config.py, update the max prices:
SEARCH_QUERIES = [
    {
        "name": "Gaming PC RTX 3080",
        "sites": ["blocket"],
        "query": "rtx 3080",
        "max_price": 8000,  # Increased from 6000
        "condition": "used"
    },
    {
        "name": "All Stationary Computers", 
        "sites": ["blocket"],
        "query": "",
        "max_price": 15000,  # Increased from 10000
        "condition": "used"
    },
    {
        "name": "Workstation Xeon",
        "sites": ["blocket"], 
        "query": "xeon workstation",
        "max_price": 5000,  # Increased from 4000
        "condition": "used"
    }
]

# ... rest of your config ...

# AI CONFIGURATION
OLLAMA_MODEL = "mistral"  # Or "mistral", "codellama", etc. Use a model good at reasoning.
OLLAMA_BASE_URL = "http://localhost:11434"

# DISCORD CONFIGURATION
DISCORD_BOT_TOKEN = "MTQxNTAzNDU0ODg3Nzc4NzEzNg.GzsCng.yGPmN18xP-oDtkmo9_wTxQKAQmvZU3Tja1Mcss"
DISCORD_CHANNEL_ID = 1055040464316809266 # Your Discord Channel ID
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1415061850240061618/mMqXX1NORtqhl_3WeLhhcj52i2M46vSOd0tO2Y9s0xkkSRMQVVQK-LfuL58TeoIv5f_n"

# DATABASE CONFIG
DATABASE_PATH = "listings.db"