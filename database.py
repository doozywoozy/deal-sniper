# database.py
import sqlite3
from config import DATABASE_PATH

def init_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create table for seen listings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seen_listings (
        id TEXT PRIMARY KEY,
        title TEXT,
        price INTEGER,
        url TEXT,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database table 'seen_listings' ready")

def is_listing_seen(listing_id: str) -> bool:
    """Check if a listing has already been processed"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM seen_listings WHERE id = ?", (listing_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None

def mark_listing_seen(listing_id: str, title: str = "", price: int = 0, url: str = "", source: str = "blocket"):
    """Mark a listing as seen/processed"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT OR IGNORE INTO seen_listings (id, title, price, url, source)
        VALUES (?, ?, ?, ?, ?)
        ''', (listing_id, title, price, url, source))
        
        conn.commit()
    except Exception as e:
        print(f"Error marking listing as seen: {e}")
    finally:
        conn.close()

def cleanup_old_listings(days: int = 30):
    """Remove old listings from the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM seen_listings WHERE created_at < datetime('now', ?)", (f'-{days} days',))
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"🧹 Cleaned up {deleted_count} old listings")
    return deleted_count

# Initialize database when module is imported
init_database()
