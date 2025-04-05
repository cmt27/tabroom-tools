# app/scraping/scraper_manager.py
import logging
import time
import pandas as pd
import os
import re
from app.auth.session_manager import TabroomSession
from app.scraping.judge_search import JudgeSearchScraper
from app.scraping.tournament_scraper import TournamentScraper
from app import config

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
        self.tournament_scraper = None
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
            try:
                self.judge_search_scraper = JudgeSearchScraper(self.session)
                self.tournament_scraper = TournamentScraper(self.session)
                self._initialized_scrapers = True
                logger.debug("All scrapers initialized with authenticated driver")
            except Exception as e:
                logger.error(f"Error initializing scrapers: {e}")
                # Try to initialize each scraper separately
                try:
                    self.judge_search_scraper = JudgeSearchScraper(self.session)
                    logger.debug("Judge search scraper initialized")
                except Exception as e1:
                    logger.error(f"Error initializing judge search scraper: {e1}")
                    
                try:
                    self.tournament_scraper = TournamentScraper(self.session)
                    logger.debug("Tournament scraper initialized")
                except Exception as e2:
                    logger.error(f"Error initializing tournament scraper: {e2}")
        else:
            logger.error("Cannot initialize scrapers: No authenticated driver available")
            
        # Safety check - create scrapers even if driver is not available
        if self.judge_search_scraper is None:
            self.judge_search_scraper = JudgeSearchScraper(self.session)
            
        if self.tournament_scraper is None:
            self.tournament_scraper = TournamentScraper(self.session)
            
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
    
    def scrape_tournament(self, tournament_url, max_judges=None, save_results=True):
        """
        Scrape all judges from a tournament's judge list
        
        Args:
            tournament_url: URL of the tournament judge list page
            max_judges: Maximum number of judges to scrape (None for all)
            save_results: Whether to save results to CSV file
            
        Returns:
            pandas.DataFrame: Combined DataFrame with all judge records
        """
        start_time = time.time()
        logger.info(f"Initiating tournament scraping for: {tournament_url}")
        
        # Ensure we're logged in before scraping
        if not self.session.ensure_login():
            logger.error("Failed to ensure login before tournament scraping")
            return pd.DataFrame()
        
        # Get a shared authenticated driver to ensure initialization
        driver = self._get_authenticated_driver()
        if not driver:
            logger.error("Failed to get authenticated driver for tournament scraping")
            return pd.DataFrame()
        
        # Initialize scrapers if not done already
        if not self._initialized_scrapers:
            self._initialize_scrapers()
            
        # Verify scraper initialization 
        if self.tournament_scraper is None:
            logger.error("Tournament scraper is not initialized")
            self.tournament_scraper = TournamentScraper(self.session)
            
        # Perform the scraping
        results = self.tournament_scraper.scrape_tournament(tournament_url, max_judges)
        
        # Save results if requested
        if save_results and not results.empty:
            self._save_tournament_results(results, tournament_url)
        
        # Log performance metrics
        duration = time.time() - start_time
        record_count = len(results) if not results.empty else 0
        judge_count = len(results['JudgeID'].unique()) if not results.empty else 0
        logger.info(f"Tournament scraping completed in {duration:.2f} seconds, "
                   f"found {record_count} records from {judge_count} judges")
        
        return results
    
    def _save_tournament_results(self, results, tournament_url):
        """
        Save tournament results to a CSV file
        
        Args:
            results: DataFrame with tournament results
            tournament_url: URL of the tournament judge list page
        """
        try:
            # Create a filename based on tournament and date
            if 'TournamentName' in results.columns and not results['TournamentName'].empty:
                tournament_name = results['TournamentName'].iloc[0]
            else:
                # Extract tournament ID from URL
                match = re.search(r'tourn_id=(\d+)', tournament_url)
                tournament_id = match.group(1) if match else "unknown"
                tournament_name = f"tournament_{tournament_id}"
            
            # Clean up the name for use as a filename
            safe_name = re.sub(r'[^\w\s-]', '', tournament_name).strip().replace(' ', '_')
            
            # Add timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # Create filename
            filename = f"{safe_name}_{timestamp}.csv"
            filepath = os.path.join(config.DATA_DIR, filename)
            
            # Save to CSV
            results.to_csv(filepath, index=False)
            logger.info(f"Saved tournament results to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving tournament results: {e}")
    
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
        self.tournament_scraper = None
        
        # Release any other drivers in the pool
        self.session.driver_pool.cleanup_all()
        logger.info("Scraper manager closed and resources released")