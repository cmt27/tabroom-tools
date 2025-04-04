# app/auth/cookie_manager.py
import os
import pickle
import logging
from selenium.common.exceptions import WebDriverException
from app import config

logger = logging.getLogger(__name__)

class CookieManager:
    """Manages browser cookies for persistent sessions"""
    
    def __init__(self, storage_dir=None):
        """
        Initialize the cookie manager
        
        Args:
            storage_dir: Directory to store cookies
        """
        self.storage_dir = storage_dir or config.COOKIE_DIR
        
        # Ensure the storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Define file path for storing cookies
        self.cookie_file = os.path.join(self.storage_dir, "tabroom_cookies.pkl")
    
    def save_cookies(self, driver):
        """
        Save cookies from a WebDriver session
        
        Args:
            driver: WebDriver instance with active session
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not driver:
            logger.error("No driver provided to save cookies")
            return False
            
        try:
            cookies = driver.get_cookies()
            if not cookies:
                logger.warning("No cookies found to save")
                return False
                
            with open(self.cookie_file, "wb") as f:
                pickle.dump(cookies, f)
                
            logger.info(f"Saved {len(cookies)} cookies successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False
    
    def load_cookies(self, driver, domain=None):
        """
        Load cookies into a WebDriver session
        
        Args:
            driver: WebDriver instance to load cookies into
            domain: Domain to navigate to before loading cookies
                    (required as cookies can only be loaded when on the right domain)
                    
        Returns:
            bool: True if successful, False otherwise
        """
        if not driver:
            logger.error("No driver provided to load cookies")
            return False
            
        if not os.path.exists(self.cookie_file):
            logger.info("No cookie file found")
            return False
            
        # Default to tabroom.com domain if none provided
        domain = domain or config.TABROOM_URL
            
        try:
            # First navigate to the domain (required before adding cookies)
            current_url = driver.current_url
            if not current_url.startswith(domain):
                logger.info(f"Navigating to {domain} before loading cookies")
                driver.get(domain)
                
            # Load cookies from file
            with open(self.cookie_file, "rb") as f:
                cookies = pickle.load(f)
                
            cookie_count = 0
            for cookie in cookies:
                try:
                    # Remove problematic keys that might cause issues
                    if 'expiry' in cookie:
                        del cookie['expiry']
                        
                    driver.add_cookie(cookie)
                    cookie_count += 1
                except Exception as e:
                    logger.warning(f"Error adding cookie: {e}")
                    
            # Refresh to apply cookies
            driver.refresh()
            
            logger.info(f"Loaded {cookie_count}/{len(cookies)} cookies successfully")
            return cookie_count > 0
            
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False
    
    def clear_cookies(self):
        """
        Delete stored cookies
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(self.cookie_file):
            return True
            
        try:
            os.remove(self.cookie_file)
            logger.info("Cookies deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting cookies: {e}")
            return False