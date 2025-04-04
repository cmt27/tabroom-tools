# app/auth/browser_manager.py
import os
import platform
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.safari.service import Service as SafariService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType
from app import config

logger = logging.getLogger(__name__)

class BrowserManager:
    """Manages browser driver creation with fallback options"""
    
    @staticmethod
    def create_driver(browser_type=None, headless=None):
        """
        Create and configure a WebDriver instance with fallback strategy
        
        Args:
            browser_type: Preferred browser type ('chrome', 'chromium', 'safari')
                          If None, will try in order: chromium, chrome, safari
            headless: Override headless setting from config
            
        Returns:
            WebDriver instance or None if all browser attempts fail
        """
        headless = config.HEADLESS if headless is None else headless
        system = platform.system()
        
        # Determine browser order based on input and platform
        browser_order = []
        
        if browser_type:
            browser_order.append(browser_type.lower())
        else:
            if system == "Darwin":  # macOS
                browser_order = ["chromium", "chrome", "safari"]
            else:
                browser_order = ["chromium", "chrome"]
        
        # Try browsers in order until one works
        last_error = None
        for browser in browser_order:
            try:
                logger.info(f"Attempting to create {browser} driver")
                
                if browser == "chromium":
                    driver = BrowserManager._create_chromium_driver(headless)
                elif browser == "chrome":
                    driver = BrowserManager._create_chrome_driver(headless)
                elif browser == "safari":
                    driver = BrowserManager._create_safari_driver(headless)
                else:
                    continue
                    
                # Test the driver with a simple operation
                driver.get("about:blank")
                
                logger.info(f"Successfully created {browser} driver")
                return driver
                
            except Exception as e:
                error_info = traceback.format_exc()
                logger.warning(f"Failed to create {browser} driver: {str(e)}\n{error_info}")
                last_error = e
                continue
        
        # If we get here, all browsers failed
        logger.error(f"Failed to create any browser driver. Last error: {str(last_error)}")
        return None
        
    @staticmethod
    def _create_chrome_driver(headless):
        """Create a Chrome WebDriver instance"""
        options = ChromeOptions()
        
        if headless:
            options.add_argument("--headless=new")
        
        # Common Chrome/Chromium options
        BrowserManager._add_chrome_options(options)
        
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    
    @staticmethod
    def _create_chromium_driver(headless):
        """Create a Chromium WebDriver instance"""
        options = ChromeOptions()
        
        if headless:
            options.add_argument("--headless=new")
        
        # Common Chrome/Chromium options
        BrowserManager._add_chrome_options(options)
        
        # Use chromium-specific ChromeDriverManager
        service = ChromeService(
            ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
        )
        return webdriver.Chrome(service=service, options=options)
    
    @staticmethod
    def _create_safari_driver(headless):
        """Create a Safari WebDriver instance"""
        if platform.system() != "Darwin":  # Only available on macOS
            raise EnvironmentError("Safari WebDriver is only available on macOS")
            
        # In macOS, safaridriver must be enabled first
        # Enable with: safaridriver --enable
        try:
            import subprocess
            logger.info("Checking if Safari WebDriver is enabled...")
            result = subprocess.run(["safaridriver", "--enable"], 
                                     capture_output=True, text=True)
            logger.info(f"Safari WebDriver enable result: {result.stdout}")
        except Exception as e:
            logger.warning(f"Could not enable Safari WebDriver: {e}")
            
        options = SafariOptions()
        service = SafariService()
        
        # Note: Safari doesn't support headless mode, but we'll try to make it less visible
        driver = webdriver.Safari(service=service, options=options)
        
        # If headless requested, minimize window as a poor substitute
        if headless:
            driver.set_window_position(0, 0)
            driver.set_window_size(1, 1)
            logger.warning("Safari doesn't support true headless mode. Window minimized instead.")
            
        return driver
    
    @staticmethod
    def _add_chrome_options(options):
        """Add common Chrome/Chromium options"""
        # Required options for containerized environments
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Stability improvements
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent to avoid detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")