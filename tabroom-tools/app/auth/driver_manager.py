# app/auth/driver_manager.py
import os
import re
import logging
import subprocess
import threading
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
    
    def _find_chromium_executable(self):
        """
        Find Chromium executable on the system
        
        Returns:
            str: Path to Chromium executable or None
        """
        # Check configured binary path first
        if config.CHROMIUM_BINARY_PATH and os.path.exists(config.CHROMIUM_BINARY_PATH):
            return config.CHROMIUM_BINARY_PATH
        
        # Potential Chromium executable paths
        chromium_paths = [
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/usr/local/bin/chromium',
            '/usr/bin/chromium',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'  # Fallback to Chrome
        ]
        
        for path in chromium_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        return None
    
    def _create_driver(self):
        """
        Create and configure a new Chromium WebDriver instance
        
        Returns:
            WebDriver: Configured WebDriver instance
        """
        try:
            # Configure Chromium options
            chrome_options = Options()
            
            # Headless mode if configured
            if config.HEADLESS:
                chrome_options.add_argument("--headless=new")
            
            # Standard browser options for stability
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Additional stability improvements
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set specific browser binary if found
            chromium_path = self._find_chromium_executable()
            if chromium_path:
                chrome_options.binary_location = chromium_path
            
            # Create WebDriver service with automatic driver management
            try:
                service = Service(ChromeDriverManager().install())
            except Exception as e:
                logging.warning(f"Automatic driver download failed: {e}")
                # Fallback to system ChromeDriver paths
                fallback_paths = [
                    '/usr/local/bin/chromedriver',
                    '/usr/bin/chromedriver',
                    '/opt/homebrew/bin/chromedriver'
                ]
                
                for path in fallback_paths:
                    if os.path.exists(path):
                        service = Service(path)
                        break
                else:
                    raise RuntimeError(
                        "No ChromeDriver found. "
                        "Please install ChromeDriver (e.g., 'brew install chromedriver')"
                    )
            
            # Create WebDriver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Configure timeouts
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(5)
            
            return driver
        
        except Exception as e:
            logging.error(f"Failed to create Chromium WebDriver: {e}")
            logging.error(f"Error Type: {type(e)}")
            logging.error("Full Traceback:", exc_info=True)
            raise
    
    def get_driver(self, thread_id=None):
        """
        Get or create a WebDriver instance for the specified thread
        
        Args:
            thread_id: Optional thread identifier (defaults to current thread)
        
        Returns:
            WebDriver: A configured WebDriver instance
        """
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
    
    def release_driver(self, thread_id=None):
        """
        Release a driver back to the pool
        
        Args:
            thread_id: Optional thread identifier (defaults to current thread)
        """
        if thread_id is None:
            thread_id = threading.get_ident()
            
        with self.driver_lock:
            self._quit_driver(thread_id)
    
    def _quit_driver(self, thread_id):
        """
        Quit a driver and remove it from the pool
        
        Args:
            thread_id: Thread identifier of the driver to quit
        """
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