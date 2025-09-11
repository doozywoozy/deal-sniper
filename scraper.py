# scraper.py
import asyncio
import os
from typing import List, Dict
from playwright.async_api import async_playwright
from config import MAX_PAGES_TO_SCRAPE, REQUEST_DELAY, ENABLE_SCREENSHOTS
from logger import logger, log_detection, log_detection_sync
import database

async def handle_cookie_consent(page):
    """Handle cookie consent popup by clicking 'Allow All' with better detection"""
    try:
        # Wait a bit longer for the cookie dialog to load
        await page.wait_for_timeout(3000)
        
        # More comprehensive selectors for Swedish cookie buttons
        allow_selectors = [
            'button:has-text("Godkänn alla")',
            'button:has-text("Acceptera alla")',
            'button:has-text("Tillåt alla")',
            'button:has-text("Accept all")', 
            'button:has-text("Allow all")',
            'button[data-testid*="accept"]',
            'button[class*="accept"]',
            'button[class*="consent"]',
            '#acceptAllButton',
            '.accept-all',
            '[aria-label*="Godkänn alla"]',
            '[aria-label*="Acceptera alla"]',
            '[aria-label*="Accept all"]',
            'button[onclick*="cookie"]',
            'button[onclick*="accept"]',
            'button >> text=Godkänn',
            'button >> text=Acceptera',
            'button >> text=Accept'
        ]
        
        # First check if any cookie dialog is visible
        dialog_selectors = [
            '[id*="cookie"]',
            '[class*="cookie"]',
            '[data-testid*="cookie"]',
            '#cookieBanner',
            '.cookie-consent',
            '.cookie-banner',
            '#cookieModal',
            '.cookie-modal',
            '#consentBanner',
            '.consent-banner',
            '#cybotcookie',
            '.cc-banner'
        ]
        
        cookie_dialog_found = False
        for selector in dialog_selectors:
            try:
                dialog = await page.query_selector(selector)
                if dialog:
                    cookie_dialog_found = True
                    logger.info(f"Found cookie dialog with selector: {selector}")
                    break
            except Exception:
                continue
        
        if not cookie_dialog_found:
            logger.info("No cookie dialog found with standard selectors")
            # Try a more aggressive search for any overlay/banner
            try:
                overlays = await page.query_selector_all('div[class*="banner"], div[class*="modal"], div[class*="overlay"]')
                for overlay in overlays:
                    overlay_text = await overlay.text_content()
                    if overlay_text and any(word in overlay_text.lower() for word in ['cookie', 'kakor', 'godkänn', 'acceptera']):
                        cookie_dialog_found = True
                        logger.info("Found potential cookie dialog in generic overlay")
                        break
            except Exception:
                pass
        
        # Try to click accept buttons
        accept_clicked = False
        for selector in allow_selectors:
            try:
                # Wait a bit for the button to be clickable
                allow_button = await page.wait_for_selector(selector, timeout=2000, state='visible')
                if allow_button:
                    # Scroll into view if needed
                    await allow_button.scroll_into_view_if_needed()
                    await allow_button.click()
                    logger.info(f"✅ Clicked 'Allow All' with selector: {selector}")
                    await page.wait_for_timeout(1500)  # Wait for dialog to close
                    accept_clicked = True
                    break
            except Exception as e:
                continue
        
        if not accept_clicked and cookie_dialog_found:
            logger.warning("Cookie dialog found but couldn't click accept button")
            # Try to find and click using JavaScript as fallback
            try:
                accept_result = await page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const acceptButton = buttons.find(btn => 
                        btn.textContent && (
                            btn.textContent.includes('Godkänn') || 
                            btn.textContent.includes('Acceptera') ||
                            btn.textContent.includes('Accept') ||
                            btn.textContent.includes('Allow')
                        ) && !btn.textContent.includes('Hantera')
                    );
                    
                    if (acceptButton) {
                        acceptButton.click();
                        return true;
                    }
                    return false;
                }''')
                
                if accept_result:
                    logger.info("✅ Clicked accept button via JavaScript")
                    await page.wait_for_timeout(1500)
                    accept_clicked = True
            except Exception as e:
                logger.warning(f"JavaScript click failed: {e}")
        
        # Final fallback: press Escape to close any modal
        if not accept_clicked and cookie_dialog_found:
            try:
                await page.keyboard.press('Escape')
                logger.info("Pressed Escape to close dialog")
                await page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning(f"Escape press failed: {e}")
        
        return accept_clicked or not cookie_dialog_found
        
    except Exception as e:
        logger.warning(f"Error handling cookie consent: {e}")
        return False

async def scrape_blocket_fast(search_url: str, search_name: str) -> List[Dict]:
    """Fast scraping using Playwright with pagination"""
    all_listings = []
    browser = None
    
    try:
        browser = await async_playwright().start()
        # Launch browser with more natural settings
        browser_instance = await browser.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale='sv-SE',
            timezone_id='Europe/Stockholm',
        )
        
        # Less aggressive stealth to avoid detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
            # Build URL with pagination
            if "?" in search_url:
                paginated_url = f"{search_url}&page={page_num}"
            else:
                paginated_url = f"{search_url}?page={page_num}"
            
            logger.info(f"📄 Page {page_num}: {paginated_url}")
            
            try:
                # Navigate with more natural timing
                await page.goto(paginated_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                
                # Handle cookie consent with multiple attempts
                cookie_handled = False
                for attempt in range(2):  # Try twice
                    cookie_handled = await handle_cookie_consent(page)
                    if cookie_handled:
                        break
                    await asyncio.sleep(1)
                
                if not cookie_handled:
                    logger.warning("Cookie consent not handled, taking screenshot for debugging")
                    if ENABLE_SCREENSHOTS:
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        screenshot_path = os.path.join("screenshots", f"cookie_issue_{timestamp}.png")
                        await page.screenshot(path=screenshot_path, full_page=True)
                        logger.info(f"Cookie issue screenshot saved: {screenshot_path}")
                
                # Check page content
                page_text = await page.evaluate('''() => document.body.textContent''')
                
                # Try scraping
                listings = await try_scraping_approaches(page)
                logger.info(f"Found {len(listings)} articles on page {page_num}")
                
                if not listings:
                    if "inga annonser" in page_text.lower() or "no results" in page_text.lower():
                        logger.info("Genuine no results page")
                    else:
                        logger.warning("No listings found - taking debug screenshot")
                        if ENABLE_SCREENSHOTS:
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_path = os.path.join("screenshots", f"no_listings_{timestamp}.png")
                            await page.screenshot(path=screenshot_path, full_page=True)
                            logger.info(f"No listings screenshot saved: {screenshot_path}")
                    break
                
                all_listings.extend(listings)
                
                # Add delay between pages
                if page_num < MAX_PAGES_TO_SCRAPE:
                    await asyncio.sleep(REQUEST_DELAY)
                    
            except Exception as e:
                logger.error(f"Error on page {page_num}: {e}")
                await log_detection(page, f"Error: {str(e)}", search_url)
                break
                
    except Exception as e:
        logger.error(f"Error during browser setup: {e}")
        log_detection_sync(f"Browser error: {str(e)}", search_url)
    finally:
        if browser:
            await browser.stop()
    
    return all_listings

# ... (rest of the file remains the same as previous version) ...
