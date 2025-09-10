# database.py
import sqlite_utils

# Database configuration
DATABASE_PATH = "listings.db"

# Initialize database
db = sqlite_utils.Database(DATABASE_PATH)

def init_db():
    """Initialize the database with required tables."""
    # Table for seen listings to avoid duplicates
    if "seen_listings" not in db.table_names():
        db["seen_listings"].create({
            "id": str,
            "site": str,
            "title": str,
            "price": float,
            "url": str,
            "created": str,
        }, pk="id")
        print("✅ Database table 'seen_listings' created")
    else:
        print("✅ Database table 'seen_listings' already exists")
    
    # Table for historical sales data
    if "historical_sales" not in db.table_names():
        db["historical_sales"].create({
            "id": str,
            "site": str,
            "title": str,
            "price": float,
            "url": str,
            "date_sold": str,
            "specs": str
        }, pk="id")
        print("✅ Database table 'historical_sales' created")

def is_listing_seen(listing_id):
    """Check if a listing ID exists in the database without raising errors."""
    try:
        return db["seen_listings"].get(listing_id) is not None
    except:
        return False

def add_listing(listing_data):
    """Add a listing to the seen_listings database."""
    try:
        db["seen_listings"].insert(listing_data)
        return True
    except Exception as e:
        print(f"❌ Error adding listing to database: {e}")
        return False

# Initialize the database when this module is imported
init_db()