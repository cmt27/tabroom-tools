# app/scraping/scraper_manager.py
import logging
import time
import pandas as pd
from app.auth.session_manager import TabroomSession
from app.scraping.judge_search import JudgeSearchScraper

logger = logging.getLogger(__name__)

class ScraperManager:
    """
    Manager class for coordinating different scraping modes and operations
    
    This class provides a unified interface for all scraping operations,
    handling authentication and session management automatically.
    """
    
    def __init__(self, storage_dir=None, encryption_key=None):
        """
        Initialize the scraper manager
        
        Args:
            storage_dir: Directory to store session data (cookies, credentials)
            encryption_key: Key for encrypting credentials
        """
        self.session = TabroomSession(storage_dir, encryption_key)
        self._driver = None
        self.judge_search_scraper = None
        self._initialized_scrapers = False
        
    def _get_authenticated_driver(self, force_new=False):
        """
        Get a single authenticated driver instance to be reused
        
        Args:
            force_new: Whether to force creation of a new driver
            
        Returns:
            WebDriver instance or None if creation failed
        """
        if not force_new and self._driver:
            try:
                # Check if driver is still valid
                self._driver.current_url
                logger.debug("Reusing existing authenticated driver")
                return self._driver
            except Exception as e:
                logger.warning(f"Existing driver is invalid: {e}. Creating a new one.")
                if self._driver:
                    self.session.release_driver(self._driver)
                self._driver = None
        
        # Create a new authenticated driver
        self._driver = self.session.get_driver()
        
        # Initialize scrapers with this driver if successful
        if self._driver and not self._initialized_scrapers:
            self._initialize_scrapers()
            
        return self._driver
    
    def _initialize_scrapers(self):
        """Initialize all scrapers with the current authenticated driver"""
        if self._driver:
            self.judge_search_scraper = JudgeSearchScraper(self.session, self._driver)
            self._initialized_scrapers = True
            logger.debug("All scrapers initialized with authenticated driver")
        else:
            logger.error("Cannot initialize scrapers: No authenticated driver available")
            
    def ensure_login(self, username=None, password=None):
        """
        Ensure we have an active authenticated session
        
        Args:
            username: Optional username to use if login is required
            password: Optional password to use if login is required
            
        Returns:
            bool: True if logged in, False otherwise
        """
        return self.session.ensure_login(username, password)
    
    def search_judge(self, judge_name):
        """
        Search for a judge by name using Judge Search Mode
        
        Args:
            judge_name: Name of the judge to search for
            
        Returns:
            pandas.DataFrame: DataFrame containing the judge's record
        """
        start_time = time.time()
        logger.info(f"Initiating judge search for: {judge_name}")
        
        # Ensure we're logged in before searching
        if not self.session.ensure_login():
            logger.error("Failed to ensure login before judge search")
            return pd.DataFrame()
        
        # Get a shared authenticated driver
        driver = self._get_authenticated_driver()
        if not driver:
            logger.error("Failed to get authenticated driver for judge search")
            return pd.DataFrame()
        
        # Initialize scrapers if not done already
        if not self._initialized_scrapers:
            self._initialize_scrapers()
            
        # Perform the search
        results = self.judge_search_scraper.search_judge(judge_name)
        
        # Log performance metrics
        duration = time.time() - start_time
        record_count = len(results) if not results.empty else 0
        logger.info(f"Judge search completed in {duration:.2f} seconds, found {record_count} records")
        
        return results
    
    def close(self):
        """
        Clean up resources and close the session
        """
        logger.info("Closing scraper manager and releasing resources")
        
        # Release the shared driver if it exists
        if self._driver:
            logger.debug("Releasing shared authenticated driver")
            self.session.release_driver(self._driver)
            self._driver = None
            
        # Reset scraper initialization flag
        self._initialized_scrapers = False
        self.judge_search_scraper = None
        
        # Release any other drivers in the pool
        self.session.driver_pool.cleanup_all()
        logger.info("Scraper manager closed and resources released")