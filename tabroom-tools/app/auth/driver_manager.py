# app/auth/driver_manager.py
import os
import threading
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from app import config

class WebDriverPool:
    """
    Singleton class that manages a pool of WebDriver instances with thread safety
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WebDriverPool, cls).__new__(cls)
                cls._instance.drivers = {}
                cls._instance.driver_lock = threading.Lock()
            return cls._instance
    
    def get_driver(self, thread_id=None):
        """Get or create a WebDriver instance for the specified thread"""
        if thread_id is None:
            thread_id = threading.get_ident()
            
        with self.driver_lock:
            if thread_id in self.drivers:
                try:
                    # Verify the driver is still valid
                    self.drivers[thread_id].current_url
                    return self.drivers[thread_id]
                except Exception as e:
                    logging.warning(f"Driver for thread {thread_id} is invalid: {e}. Creating a new one.")
                    self._quit_driver(thread_id)
            
            # Create new driver
            driver = self._create_driver()
            self.drivers[thread_id] = driver
            return driver
    
    def _create_driver(self):
        """Create and configure a new Chrome WebDriver instance"""
        chrome_options = Options()
        if config.HEADLESS:
            chrome_options.add_argument("--headless=new")
        
        # Add required Chrome options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Stability improvements
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        
        # Create and configure the driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Configure timeouts
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(5)  # Wait 5 seconds for elements to appear
        
        return driver
    
    def release_driver(self, thread_id=None):
        """Release a driver back to the pool"""
        if thread_id is None:
            thread_id = threading.get_ident()
            
        with self.driver_lock:
            self._quit_driver(thread_id)
    
    def _quit_driver(self, thread_id):
        """Quit a driver and remove it from the pool"""
        if thread_id in self.drivers:
            try:
                self.drivers[thread_id].quit()
            except Exception as e:
                logging.warning(f"Error quitting driver: {e}")
            finally:
                del self.drivers[thread_id]
    
    def cleanup_all(self):
        """Clean up all drivers in the pool"""
        with self.driver_lock:
            for thread_id in list(self.drivers.keys()):
                self._quit_driver(thread_id)