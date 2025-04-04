# app/scraping/scraper_manager.py
import logging
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
        self.judge_search_scraper = JudgeSearchScraper(self.session)
        
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
        logger.info(f"Initiating judge search for: {judge_name}")
        
        # Ensure we're logged in before searching
        if not self.session.ensure_login():
            logger.error("Failed to ensure login before judge search")
            return pd.DataFrame()
        
        # Perform the search
        return self.judge_search_scraper.search_judge(judge_name)
    
    def close(self):
        """
        Clean up resources and close the session
        """
        # Any cleanup needed for the scrapers
        
        # Release any drivers in the pool
        self.session.driver_pool.cleanup_all()
        logger.info("Scraper manager closed and resources released")