# app/auth/driver_pool.py
import threading
import logging
import time
from selenium.common.exceptions import WebDriverException
from app.auth.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

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
                cls._instance.browser_preferences = {}  # Track which browser worked for each thread
                cls._instance.driver_usage_count = {}  # Track usage to identify potential leaks
            return cls._instance
    
    def get_driver(self, thread_id=None, browser_type=None, reuse=True):
        """
        Get or create a WebDriver instance for the specified thread
        
        Args:
            thread_id: Thread identifier (uses current thread ID if None)
            browser_type: Preferred browser type (uses last successful browser if None)
            reuse: Whether to attempt reusing an existing driver
            
        Returns:
            WebDriver instance or None if creation failed
        """
        if thread_id is None:
            thread_id = threading.get_ident()
            
        with self.driver_lock:
            # Check if we already have a driver for this thread
            if reuse and thread_id in self.drivers:
                try:
                    # Verify the driver is still valid with a simple operation
                    self.drivers[thread_id].current_url
                    logger.info(f"Reusing existing driver for thread {thread_id}")
                    self.driver_usage_count[thread_id] = self.driver_usage_count.get(thread_id, 0) + 1
                    return self.drivers[thread_id]
                except Exception as e:
                    logger.warning(f"Driver for thread {thread_id} is invalid: {e}. Creating a new one.")
                    self._quit_driver(thread_id)
            
            # Use the last successful browser type for this thread if available
            if browser_type is None and thread_id in self.browser_preferences:
                browser_type = self.browser_preferences[thread_id]
                
            # Create new driver
            max_attempts = 3
            for attempt in range(max_attempts):
                driver = BrowserManager.create_driver(browser_type)
                if driver:
                    # Store the driver and browser type that worked
                    self.drivers[thread_id] = driver
                    if browser_type:
                        self.browser_preferences[thread_id] = browser_type
                    
                    # Configure timeouts
                    driver.set_page_load_timeout(30)
                    driver.implicitly_wait(5)
                    
                    # Track usage count
                    self.driver_usage_count[thread_id] = 1
                    logger.info(f"Created new driver for thread {thread_id}")
                    return driver
                
                logger.warning(f"Driver creation failed (attempt {attempt+1}/{max_attempts}). Retrying...")
                time.sleep(1)  # Short delay before retry
                
            logger.error(f"Failed to create driver after {max_attempts} attempts")
            return None
    
    def release_driver(self, thread_id=None):
        """
        Release a driver back to the pool
        
        Args:
            thread_id: Thread identifier (uses current thread ID if None)
        """
        if thread_id is None:
            thread_id = threading.get_ident()
            
        with self.driver_lock:
            if thread_id in self.driver_usage_count:
                self.driver_usage_count[thread_id] -= 1
                logger.debug(f"Driver usage count for thread {thread_id}: {self.driver_usage_count[thread_id]}")
                
                # Only quit if usage count is 0 or negative (safety check)
                if self.driver_usage_count.get(thread_id, 0) <= 0:
                    self._quit_driver(thread_id)
                    if thread_id in self.driver_usage_count:
                        del self.driver_usage_count[thread_id]
            else:
                # If no usage count exists, just quit the driver
                self._quit_driver(thread_id)
    
    def _quit_driver(self, thread_id):
        """
        Quit a driver and remove it from the pool
        
        Args:
            thread_id: Thread identifier
        """
        if thread_id in self.drivers:
            try:
                logger.info(f"Quitting driver for thread {thread_id}")
                self.drivers[thread_id].quit()
            except Exception as e:
                logger.warning(f"Error quitting driver: {e}")
            finally:
                del self.drivers[thread_id]
    
    def cleanup_all(self):
        """Clean up all drivers in the pool"""
        with self.driver_lock:
            logger.info(f"Cleaning up all drivers in pool, count: {len(self.drivers)}")
            for thread_id in list(self.drivers.keys()):
                self._quit_driver(thread_id)
            self.driver_usage_count.clear()