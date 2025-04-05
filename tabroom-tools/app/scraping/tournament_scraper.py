# app/scraping/tournament_scraper.py
import os
import re
import time
import logging
import traceback
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app import config
from app.scraping.judge_search import JudgeSearchScraper
from app.auth.session_manager import TabroomSession

logger = logging.getLogger(__name__)

class TournamentScraper:
    """
    Scraper for extracting judge data from tournament judge lists on tabroom.com.
    
    This scraper implements the "Tournament Mode" which allows scraping all judges
    from a tournament's judge list page.
    """
    
    def __init__(self, session_manager):
        """
        Initialize the scraper with a session manager
        
        Args:
            session_manager: TabroomSession instance for authentication and browser management
        """
        self.session_manager = session_manager
        self.judge_scraper = JudgeSearchScraper(session_manager)
        
    def scrape_tournament(self, tournament_url, max_judges=None, skip_existing=True):
        """
        Scrape all judges from a tournament judge list
        
        Args:
            tournament_url: URL of the tournament judge list page
            max_judges: Maximum number of judges to scrape (None for all)
            skip_existing: Whether to skip judges already in storage
            
        Returns:
            pandas.DataFrame: Combined DataFrame with all judge records
        """
        driver = None
        try:
            # Get an authenticated driver
            driver = self.session_manager.get_driver()
            
            if not driver:
                logger.error("Failed to get authenticated driver")
                return pd.DataFrame()
            
            # Navigate to the tournament judge list page
            logger.info(f"Navigating to tournament judge list: {tournament_url}")
            driver.get(tournament_url)
            time.sleep(3)
            
            # Extract tournament information
            tournament_info = self._extract_tournament_info(driver)
            logger.info(f"Scraping tournament: {tournament_info['name']}")
            
            # Extract judge links
            judge_links = self._extract_judge_links(driver)
            
            # Apply max_judges limit if specified
            if max_judges is not None and max_judges > 0:
                judge_links = judge_links[:max_judges]
                
            logger.info(f"Found {len(judge_links)} judges to process")
            
            # Process each judge
            all_judge_data = []
            for idx, judge_link in enumerate(judge_links, 1):
                logger.info(f"Processing judge {idx}/{len(judge_links)}: {judge_link['name']}")
                
                try:
                    # Skip existing judges if requested
                    if skip_existing and self._judge_exists(judge_link['id']):
                        logger.info(f"Skipping existing judge: {judge_link['name']} (ID: {judge_link['id']})")
                        continue
                    
                    # Process the judge
                    judge_data = self._process_judge(judge_link['url'])
                    
                    # If data was found, append to results
                    if not judge_data.empty:
                        all_judge_data.append(judge_data)
                        
                        # Save each judge's data to a temporary file for backup
                        self._save_temp_judge_data(judge_link['id'], judge_link['name'], judge_data)
                    else:
                        logger.warning(f"No data found for judge: {judge_link['name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing judge {judge_link['name']}: {e}")
                    # Continue with next judge on error
                    continue
            
            # Combine all judge data
            if all_judge_data:
                result = pd.concat(all_judge_data, ignore_index=True)
                logger.info(f"Successfully scraped {len(result)} records from {len(all_judge_data)} judges")
                
                # Add tournament info to the records
                result['TournamentName'] = tournament_info['name']
                result['TournamentDate'] = tournament_info['date']
                
                return result
            else:
                logger.warning("No judge data was successfully scraped")
                return pd.DataFrame()
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error during tournament scraping: {e}\n{error_trace}")
            return pd.DataFrame()
        finally:
            # Release the driver back to the pool
            if driver:
                self.session_manager.release_driver(driver)
    
    def _extract_tournament_info(self, driver):
        """
        Extract tournament name and date from the page
        
        Args:
            driver: WebDriver instance
            
        Returns:
            dict: Dictionary with tournament information
        """
        info = {
            'name': '',
            'date': '',
            'location': ''
        }
        
        try:
            # Extract tournament name
            name_element = driver.find_element(By.CSS_SELECTOR, "h2.centeralign.marno")
            info['name'] = name_element.text.strip()
            
            # Extract date and location
            details_element = driver.find_element(By.CSS_SELECTOR, "h5.full.centeralign.marno")
            details_text = details_element.text.strip()
            
            # Parse details text (format: "2025 — Atlanta, GA/US")
            match = re.search(r'(\d{4})\s*—\s*(.*)', details_text)
            if match:
                info['date'] = match.group(1)
                info['location'] = match.group(2)
            
            logger.info(f"Extracted tournament info: {info['name']} ({info['date']}, {info['location']})")
            
        except Exception as e:
            logger.error(f"Error extracting tournament info: {e}")
        
        return info
    
    def _extract_judge_links(self, driver):
        """
        Extract all judge links from the judge list table
        
        Args:
            driver: WebDriver instance
            
        Returns:
            list: List of dictionaries with judge info (id, name, url)
        """
        judge_links = []
        
        try:
            # Wait for the judge list table to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "judgelist"))
            )
            
            # Find all rows in the table
            rows = driver.find_elements(By.CSS_SELECTOR, "#judgelist tbody tr")
            
            # Process each row
            for row in rows:
                try:
                    # Extract judge information
                    first_td = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)")
                    last_td = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)")
                    
                    first_link = first_td.find_element(By.TAG_NAME, "a")
                    last_link = last_td.find_element(By.TAG_NAME, "a")
                    
                    judge_first = first_link.text.strip()
                    judge_last = last_link.text.strip()
                    judge_name = f"{judge_first} {judge_last}"
                    
                    judge_url = first_link.get_attribute("href")
                    
                    # Extract judge ID from URL
                    match = re.search(r'judge_person_id=(\d+)', judge_url)
                    judge_id = match.group(1) if match else ""
                    
                    if judge_id and judge_url:
                        judge_links.append({
                            'id': judge_id,
                            'name': judge_name,
                            'url': judge_url
                        })
                    
                except Exception as e:
                    logger.debug(f"Error extracting judge link from row: {e}")
                    continue
            
            logger.info(f"Extracted {len(judge_links)} judge links")
            
        except Exception as e:
            logger.error(f"Error extracting judge links: {e}")
        
        return judge_links
    
    def _process_judge(self, judge_url):
        """
        Process a single judge using the JudgeSearchScraper
        
        Args:
            judge_url: URL of the judge's page
            
        Returns:
            pandas.DataFrame: DataFrame with the judge's record
        """
        # The JudgeSearchScraper class already has the logic to scrape a judge page
        # We can use that directly by calling the _scrape_judge_page method
        
        driver = None
        try:
            # Get a driver
            driver = self.session_manager.get_driver()
            
            if not driver:
                logger.error("Failed to get driver for processing judge")
                return pd.DataFrame()
            
            # Navigate to the judge page
            driver.get(judge_url)
            time.sleep(2)
            
            # Extract judge ID from URL
            judge_id_match = re.search(r"judge_person_id=(\d+)", judge_url)
            judge_id = judge_id_match.group(1) if judge_id_match else ""
            
            # Extract judge name from h3 element
            try:
                judge_name = driver.find_element(By.TAG_NAME, "h3").text.strip()
                logger.info(f"Processing judge: {judge_name} (ID: {judge_id})")
            except NoSuchElementException:
                judge_name = ""
                logger.warning(f"Could not find judge name for ID: {judge_id}")
            
            # Use the JudgeSearchScraper's _scrape_judge_page method
            # This is a bit of a hack, but it avoids duplicating code
            result = self.judge_scraper._scrape_judge_page(driver, judge_url, reload=False)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing judge: {e}")
            return pd.DataFrame()
        finally:
            if driver:
                self.session_manager.release_driver(driver)
    
    def _judge_exists(self, judge_id):
        """
        Check if a judge already exists in storage
        
        Args:
            judge_id: ID of the judge to check
            
        Returns:
            bool: True if judge exists, False otherwise
        """
        # This is a placeholder for now
        # In a future implementation, this could check a database or file
        return False
    
    def _save_temp_judge_data(self, judge_id, judge_name, judge_data):
        """
        Save judge data to a temporary file for backup
        
        Args:
            judge_id: ID of the judge
            judge_name: Name of the judge
            judge_data: DataFrame with judge data
        """
        try:
            # Create a temporary directory if it doesn't exist
            temp_dir = os.path.join(config.DATA_DIR, "temp_judges")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Create a safe filename from judge name
            safe_name = re.sub(r'[^\w\s-]', '', judge_name).strip().replace(' ', '_')
            filename = f"judge_{judge_id}_{safe_name}.csv"
            filepath = os.path.join(temp_dir, filename)
            
            # Save the data to CSV
            judge_data.to_csv(filepath, index=False)
            logger.debug(f"Saved temporary judge data to {filepath}")
        except Exception as e:
            logger.warning(f"Error saving temporary judge data: {e}")