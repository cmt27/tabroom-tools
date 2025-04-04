# app/scraping/judge_search.py
import time
import re
import logging
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app import config

logger = logging.getLogger(__name__)

class JudgeSearchScraper:
    """
    Scraper for finding and extracting judge information using Tabroom's search functionality.
    
    This scraper implements the "Judge Search Mode" which allows searching for judges by name
    and extracting their judging record.
    """
    
    def __init__(self, session_manager):
        """
        Initialize the scraper with a session manager
        
        Args:
            session_manager: TabroomSession instance for authentication and browser management
        """
        self.session_manager = session_manager
        self.search_url = f"{config.TABROOM_URL}/index/paradigm.mhtml"
    
    def search_judge(self, judge_name):
        """
        Search for a judge by name and return their judging record
        
        Args:
            judge_name: Name of the judge to search for (first and last name)
            
        Returns:
            pandas.DataFrame: DataFrame containing the judge's record, or empty DataFrame if not found
        """
        driver = None
        try:
            # Get an authenticated driver
            driver = self.session_manager.get_driver()
            if not driver:
                logger.error("Failed to get authenticated driver")
                return pd.DataFrame()
            
            # Navigate to the judge search page
            logger.info(f"Navigating to judge search page: {self.search_url}")
            driver.get(self.search_url)
            time.sleep(2)
            
            # Try to use separate first/last name fields if available
            try:
                first_input = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.NAME, "search_first"))
                )
                last_input = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.NAME, "search_last"))
                )
                logger.info("Found separate input fields for judge first and last names")
                
                # Split the name into first and last
                parts = judge_name.strip().split(None, 1)
                if len(parts) == 2:
                    first_name, last_name = parts[0], parts[1]
                else:
                    first_name, last_name = "", parts[0]
                
                # Fill in the fields and submit
                first_input.clear()
                first_input.send_keys(first_name)
                last_input.clear()
                last_input.send_keys(last_name)
                
                last_input.send_keys(Keys.ENTER)
                logger.info(f"Submitted judge search for first: '{first_name}' and last: '{last_name}'")
            except Exception as e:
                logger.debug(f"Separate first/last inputs not found or error occurred ({e}); falling back to single input")
                
                # Fall back to single search input
                search_input = WebDriverWait(driver, 30).until(
                    EC.visibility_of_element_located((By.ID, "searchtext"))
                )
                search_input.clear()
                search_input.send_keys(judge_name)
                search_input.send_keys(Keys.ENTER)
                logger.info(f"Submitted judge search using single input for: '{judge_name}'")
            
            # Wait for results to load
            time.sleep(8)
            
            # Check for direct match (h3 element with judge name)
            try:
                h3_element = driver.find_element(By.TAG_NAME, "h3")
                header_text = h3_element.text.strip()
                logger.info(f"Found header: '{header_text}'")
                
                if header_text.lower() == judge_name.strip().lower():
                    logger.info("Direct match found via <h3> element; scraping judge page from current DOM")
                    return self._scrape_judge_page(driver, driver.current_url, reload=False)
            except NoSuchElementException:
                logger.debug("No <h3> element found for direct match; proceeding to candidate links")
            
            # Find all candidate links
            all_links = driver.find_elements(By.CSS_SELECTOR, "a")
            candidate_links = [link for link in all_links 
                              if link.get_attribute("href") and 
                                 "judge_person_id=" in link.get_attribute("href")]
            
            logger.info(f"Found {len(candidate_links)} candidate judge result links based on href filtering")
            
            if not candidate_links:
                logger.error("No candidate judge links found in search results")
                page_source_snippet = driver.page_source[:1000]
                logger.debug(f"Page source snippet: {page_source_snippet}")
                return pd.DataFrame()
            
            # Filter out known sidebar options
            excluded_texts = {"view past ratings", "view upcoming ratings", "view judging record"}
            
            # Process each candidate link
            for link in candidate_links:
                try:
                    # Find the parent row and extract the name
                    tr = link.find_element(By.XPATH, "./ancestor::tr")
                    tds = tr.find_elements(By.TAG_NAME, "td")
                    
                    if len(tds) >= 2:
                        candidate_first = tds[0].text.strip()
                        candidate_last = tds[1].text.strip()
                        candidate_full = f"{candidate_first} {candidate_last}"
                        logger.debug(f"Candidate full name: '{candidate_full}'")
                        
                        # Skip excluded sidebar options
                        if candidate_full.lower() in excluded_texts:
                            logger.debug(f"Skipping excluded candidate: '{candidate_full}'")
                            continue
                        
                        # Check for exact match
                        if candidate_full.lower() == judge_name.strip().lower():
                            candidate_url = link.get_attribute("href")
                            logger.info(f"Exact match found: '{candidate_full}' with candidate URL: {candidate_url}")
                            
                            # Click the link and wait for the judge page to load
                            link.click()
                            WebDriverWait(driver, 30).until(
                                EC.presence_of_element_located((By.TAG_NAME, "h3"))
                            )
                            
                            # Verify the URL was updated correctly
                            if candidate_url == self.search_url or "judge_person_id=" not in candidate_url:
                                candidate_url = driver.current_url
                                logger.debug("Candidate URL not updated; using current URL from DOM as fallback")
                            
                            # Scrape the judge page
                            return self._scrape_judge_page(driver, candidate_url)
                    else:
                        logger.debug("Candidate row does not have enough columns to extract name")
                except Exception as inner_e:
                    logger.debug(f"Error processing candidate row: {inner_e}")
                    continue
            
            logger.error("No exact match found among the search results")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error during judge search scraping for '{judge_name}': {e}")
            return pd.DataFrame()
        finally:
            # Release the driver back to the pool
            if driver:
                self.session_manager.release_driver(driver)
    
    def _scrape_judge_page(self, driver, judge_url, reload=True):
        """
        Extract judge record data from a judge's page
        
        Args:
            driver: WebDriver instance
            judge_url: URL of the judge's page
            reload: Whether to reload the page or use the current DOM
            
        Returns:
            pandas.DataFrame: DataFrame containing the judge's record
        """
        logger.info(f"Scraping judge page from URL: {judge_url} (reload={reload})")
        
        if reload:
            driver.get(judge_url)
            time.sleep(2)
        
        # Extract judge ID from URL
        judge_id_match = re.search(r"judge_person_id=(\d+)", judge_url)
        judge_id = judge_id_match.group(1) if judge_id_match else ""
        
        # Extract judge name from h3 element
        try:
            judge_name = driver.find_element(By.TAG_NAME, "h3").text.strip()
            logger.info(f"Found judge name: {judge_name}")
        except Exception as e:
            logger.error(f"Could not find judge name: {e}")
            judge_name = ""
        
        # Wait for judge record table to load
        try:
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#judgerecord tbody tr"))
            )
            table_element = driver.find_element(By.CSS_SELECTOR, "#judgerecord")
            logger.info("Judge record table loaded")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Judge record table did not load properly: {e}")
            return pd.DataFrame()
        
        # Extract table rows
        try:
            tbody = table_element.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
        except Exception as e:
            logger.error(f"Could not find tbody or rows in judge record table: {e}")
            return pd.DataFrame()
        
        logger.info(f"Found {len(rows)} rows in judge record table")
        
        # Process each row
        data_list = []
        for index, row in enumerate(rows[1:], start=2):  # Skip header row
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 9:
                    record = {
                        "JudgeID": judge_id,
                        "JudgeName": judge_name,
                        "Tournament": self._extract_clean(cols[0]),
                        "Lv": self._extract_clean(cols[1]),
                        "Date": self._extract_clean(cols[2], field="Date"),
                        "Ev": self._extract_clean(cols[3]),
                        "Rd": self._extract_clean(cols[4]),
                        "Aff": self._extract_clean(cols[5]),
                        "Neg": self._extract_clean(cols[6]),
                        "Vote": self._extract_clean(cols[7]),
                        "Result": self._extract_clean(cols[8], field="Result")
                    }
                    data_list.append(record)
                else:
                    logger.debug(f"Skipping row {index} due to insufficient columns")
            except Exception as e:
                logger.debug(f"Exception processing row {index}: {e}")
        
        if data_list:
            logger.info("Successfully extracted judge record data")
            return pd.DataFrame(data_list)
        else:
            logger.error(f"No valid rows found on judge page: {judge_url}")
            return pd.DataFrame()
    
    def _extract_clean(self, cell, field=None):
        """
        Clean the content of a table cell by stripping HTML tags and extra whitespace
        
        Args:
            cell: WebElement containing the cell data
            field: Optional field name for special processing
            
        Returns:
            str: Cleaned text content
        """
        try:
            raw = cell.get_attribute("innerHTML")
            text = re.sub('<[^<]+?>', '', raw).strip()
            
            if field == "Date":
                match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                return match.group(1) if match else ''
            elif field == "Result":
                return re.sub(r'\s+', ' ', text).strip()
            else:
                return re.sub(r'\s+', ' ', text).strip()
        except Exception as e:
            logger.debug(f"Error cleaning cell: {e}")
            return ''