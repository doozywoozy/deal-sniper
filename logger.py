# logger.py
import logging
import os
from datetime import datetime
from config import LOG_FILE, LOG_LEVEL, SCREENSHOT_DIR

def setup_logger():
    """Setup logging configuration"""
    # Create directories if they don't exist
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('deal_sniper')
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Global logger instance
logger = setup_logger()

def log_detection(page, reason, search_url):
    """Log detection event and capture screenshot"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"detection_{timestamp}.png")
    
    try:
        if page:
            page.screenshot(path=screenshot_path, full_page=True)
            logger.warning(f"Bot detection: {reason}. Screenshot saved: {screenshot_path}")
        else:
            logger.warning(f"Bot detection: {reason}. URL: {search_url}")
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
