# app/scraping/judge_search.py
import time
import re
import os
import logging
import traceback
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
                
                # Save the full page source for debugging
                try:
                    debug_file = os.path.join(config.DATA_DIR, "search_results_debug.html")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    logger.info(f"Saved full page source to {debug_file}")
                except Exception as e:
                    logger.error(f"Error saving page source: {e}")
                
                # Log a snippet of the page source
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
            # Always return an empty DataFrame, never None
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
                    # Extract the base record data
                    record = {
                        "JudgeID": judge_id,
                        "JudgeName": judge_name,
                        "Tournament": self._extract_clean(cols[0]),
                        "Lv": self._extract_clean(cols[1]),
                        "Date": self._extract_clean(cols[2], field="Date"),
                        "Ev": self._extract_clean(cols[3]),
                        "Rd": self._extract_clean(cols[4]),
                        "AffCode": self._extract_clean(cols[5]),
                        "NegCode": self._extract_clean(cols[6]),
                        "Vote": self._extract_clean(cols[7]),
                        "Result": self._extract_clean(cols[8], field="Result")
                    }
                    
                    # Initialize new fields
                    record["AffName"] = ""
                    record["AffPoints"] = ""
                    record["NegName"] = ""
                    record["NegPoints"] = ""
                    
                    # Extract links to entry pages
                    try:
                        aff_link_element = cols[5].find_element(By.TAG_NAME, "a")
                        neg_link_element = cols[6].find_element(By.TAG_NAME, "a")
                        
                        aff_link = aff_link_element.get_attribute("href")
                        neg_link = neg_link_element.get_attribute("href")
                        
                        # Extract aff entry data
                        if aff_link:
                            logger.info(f"Row {index} - Scraping Aff entry page: {aff_link}")
                            aff_data = self._scrape_entry_page(
                                driver, 
                                aff_link, 
                                judge_name=judge_name,
                                round_info=record["Rd"],
                                opponent_code=record["NegCode"]
                            )
                            if aff_data:
                                record["AffName"] = aff_data.get("name", "")
                                record["AffPoints"] = aff_data.get("points", "")
                        
                        # Extract neg entry data
                        if neg_link:
                            logger.info(f"Row {index} - Scraping Neg entry page: {neg_link}")
                            neg_data = self._scrape_entry_page(
                                driver, 
                                neg_link, 
                                judge_name=judge_name,
                                round_info=record["Rd"],
                                opponent_code=record["AffCode"]
                            )
                            if neg_data:
                                record["NegName"] = neg_data.get("name", "")
                                record["NegPoints"] = neg_data.get("points", "")
                        
                    except Exception as e:
                        logger.warning(f"Error extracting entry data for row {index}: {e}")
                    
                    data_list.append(record)
                else:
                    logger.debug(f"Skipping row {index} due to insufficient columns")
            except Exception as e:
                logger.debug(f"Exception processing row {index}: {e}")
        
        if data_list:
            logger.info("Successfully extracted judge record data with entry details")
            return pd.DataFrame(data_list)
        else:
            logger.error(f"No valid rows found on judge page: {judge_url}")
            return pd.DataFrame()
    
    def _scrape_entry_page(self, driver, entry_url, judge_name, round_info, opponent_code):
        """
        Extract debater name and points from an entry page
        
        Args:
            driver: WebDriver instance
            entry_url: URL of the entry page
            judge_name: Name of the judge to match
            round_info: Round identifier to match
            opponent_code: Code of the opponent entry to match
            
        Returns:
            dict: Dictionary containing name and points (if available)
        """
        original_url = driver.current_url
        result = {"name": "", "points": ""}
        
        try:
            # Navigate to entry page
            driver.get(entry_url)
            time.sleep(2)
            
            # Extract entry name
            try:
                name_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h4.nospace.semibold"))
                )
                result["name"] = name_element.text.strip()
                logger.info(f"Found entry name: {result['name']}")
            except Exception as e:
                logger.warning(f"Could not find entry name: {e}")
            
            # Find all result rows - both bluebordertop and regular rows
            result_rows = driver.find_elements(By.CSS_SELECTOR, "div.bluebordertop.row, div.row")
            logger.info(f"Found {len(result_rows)} result rows on entry page")
            
            # Save page source for debugging if needed
            if config.DEBUG:
                debug_file = os.path.join(config.DATA_DIR, "entry_page_debug.html")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                logger.debug(f"Saved entry page source to {debug_file}")
            
            # Extract target round number from round_info
            target_round_num = None
            if "Round" in round_info or "R" in round_info:
                match = re.search(r'(\d+)', round_info)
                if match:
                    target_round_num = match.group(1)
                    logger.info(f"Looking for Round {target_round_num}")
            
            # Process each row to find matching round, judge, and opponent
            for idx, row in enumerate(result_rows):
                try:
                    # Log row for debugging
                    if config.DEBUG:
                        logger.debug(f"Processing row {idx+1}: {row.get_attribute('outerHTML')[:100]}...")
                    
                    # First check if this is the target round
                    round_span = row.find_element(By.CSS_SELECTOR, "span.tenth.semibold")
                    row_round_text = round_span.text.strip()
                    logger.debug(f"Row {idx+1} round text: '{row_round_text}'")
                    
                    # Skip if this is not our target round
                    if target_round_num and "Round" in row_round_text:
                        row_round_match = re.search(r'Round\s*(\d+)', row_round_text, re.IGNORECASE)
                        if not row_round_match or row_round_match.group(1) != target_round_num:
                            logger.debug(f"Skipping row {idx+1} - not the target round")
                            continue
                    
                    # Now check for the specific round without relying on the "Round" prefix
                    if not self._round_matches(row_round_text, round_info):
                        logger.debug(f"Skipping row {idx+1} - round doesn't match: '{row_round_text}' vs '{round_info}'")
                        continue
                        
                    logger.info(f"Found potential matching round: '{row_round_text}'")
                    
                    # Check if this row contains our judge
                    if not self._row_contains_judge(row, judge_name):
                        logger.debug(f"Skipping row {idx+1} - judge not found")
                        continue
                        
                    logger.info(f"Found matching judge: {judge_name}")
                    
                    # Check if this row contains our opponent
                    if not self._row_contains_opponent(row, opponent_code):
                        logger.debug(f"Skipping row {idx+1} - opponent not found")
                        continue
                        
                    logger.info(f"Found matching opponent: {opponent_code}")
                    
                    # We found the matching row! Now extract the speaker points
                    points = self._extract_points_from_row(row)
                    if points:
                        result["points"] = points
                        logger.info(f"Successfully extracted speaker points: {points}")
                    else:
                        logger.warning(f"No speaker points found in matching row")
                    
                    # We found a match, no need to process more rows
                    break
                    
                except NoSuchElementException:
                    logger.debug(f"Skipping row {idx+1} - missing expected elements")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing row {idx+1}: {e}")
                    continue
            
            # If no points were found but we know this is an elimination round, log it
            if not result["points"] and self._is_elimination_round(round_info):
                logger.info(f"No points found, but this is an elimination round ({round_info}) where points may not exist")
                
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error scraping entry page {entry_url}: {e}\n{error_trace}")
        finally:
            # Return to original page
            driver.get(original_url)
            time.sleep(1)
        
        return result
    
    def _round_matches(self, row_round, target_round):
        """
        Check if the round in the row matches the target round
        
        Args:
            row_round: Round text from the row
            target_round: Target round to match
            
        Returns:
            bool: True if rounds match, False otherwise
        """
        # Clean up round text
        row_round = row_round.lower().strip()
        target_round = target_round.lower().strip()
        
        # Direct match
        if row_round == target_round:
            return True
        
        # Extract round numbers for numeric comparison
        row_numbers = re.findall(r'\d+', row_round)
        target_numbers = re.findall(r'\d+', target_round)
        
        # If both have numbers, compare them
        if row_numbers and target_numbers:
            return row_numbers[0] == target_numbers[0]
        
        # Check for common round formats
        elim_rounds = {
            "double": ["double", "doubles", "dbls", "double octas", "double octafinals"],
            "triple": ["triple", "triples", "trips", "triple octas"],
            "octas": ["octas", "octafinals", "oct", "octafi"],
            "quarte": ["quarte", "quarters", "quarterfinals", "qf"],
            "semis": ["semis", "semifinals", "semi", "sf"],
            "finals": ["finals", "final", "f"]
        }
        
        # Check elimination round matches
        for elim_key, variations in elim_rounds.items():
            if any(var in target_round for var in variations):
                return any(var in row_round for var in variations)
        
        return False
    
    def _row_contains_judge(self, row, judge_name):
        """
        Check if the row contains the specified judge
        
        Args:
            row: WebElement representing the row
            judge_name: Name of the judge to match
            
        Returns:
            bool: True if judge is found, False otherwise
        """
        try:
            # Get all judge links in the row
            judge_links = row.find_elements(By.CSS_SELECTOR, "a[href*='judge.mhtml']")
            
            # Split judge name for more flexible matching
            judge_parts = judge_name.lower().split()
            judge_first = judge_parts[0] if len(judge_parts) > 0 else ""
            judge_last = judge_parts[-1] if len(judge_parts) > 0 else ""
            
            for link in judge_links:
                link_text = link.text.strip().lower()
                
                # Direct match (case insensitive)
                if judge_name.lower() in link_text:
                    return True
                    
                # Match both parts separately - handles "Last, First" format
                if judge_first in link_text and judge_last in link_text:
                    return True
                    
                # Handle "Last, First" format specifically
                if "," in link_text:
                    parts = [p.strip() for p in link_text.split(",")]
                    if len(parts) >= 2 and judge_last == parts[0] and judge_first in parts[1]:
                        return True
            
            return False
        except Exception as e:
            logger.debug(f"Error checking judge match: {e}")
            return False
    
    def _row_contains_opponent(self, row, opponent_code):
        """
        Check if the row contains the specified opponent
        
        Args:
            row: WebElement representing the row
            opponent_code: Opponent code to match
            
        Returns:
            bool: True if opponent is found, False otherwise
        """
        try:
            # Find opponent link
            opponent_links = row.find_elements(By.CSS_SELECTOR, "a.white.padtop.padbottom")
            
            for link in opponent_links:
                link_text = link.text.strip()
                
                # Check for "vs" format
                if "vs" in link_text.lower():
                    extracted_opponent = link_text.replace("vs", "").strip()
                    return self._similar_codes(extracted_opponent, opponent_code)
            
            return False
        except Exception as e:
            logger.debug(f"Error checking opponent match: {e}")
            return False
    
    def _extract_points_from_row(self, row):
        """
        Extract speaker points from a row using multiple methods
        
        Args:
            row: WebElement representing the row
            
        Returns:
            str: Speaker points if found, empty string otherwise
        """
        try:
            # Method 1: Try the exact path where we've seen points before
            try:
                points_span = row.find_element(By.CSS_SELECTOR, "span.fifth.marno")
                points_text = points_span.text.strip()
                
                # Validate that it's a number in the right range
                try:
                    points_value = float(points_text)
                    if 20 <= points_value <= 30:
                        return points_text
                except ValueError:
                    pass
            except NoSuchElementException:
                pass
            
            # Method 2: Try a more general approach with multiple selectors
            selectors = [
                "span.fifth.marno", 
                "span.fifth", 
                "div.full.nospace.smallish span", 
                "span.half div.full.nospace.smallish span"
            ]
            
            for selector in selectors:
                try:
                    elements = row.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        # Validate points
                        try:
                            value = float(text)
                            if 20 <= value <= 30:
                                return text
                        except ValueError:
                            continue
                except Exception:
                    continue
            
            # Method 3: Try extracting from HTML
            html = row.get_attribute('outerHTML')
            match = re.search(r'<span class="fifth marno">\s*(\d{2}(?:\.\d+)?)\s*</span>', html)
            if match:
                try:
                    value = float(match.group(1))
                    if 20 <= value <= 30:
                        return match.group(1)
                except ValueError:
                    pass
            
            return ""
        except Exception as e:
            logger.debug(f"Error extracting points: {e}")
            return ""
    
    def _is_elimination_round(self, round_info):
        """
        Check if the round is an elimination round
        
        Args:
            round_info: Round information text
            
        Returns:
            bool: True if elimination round, False otherwise
        """
        round_info = round_info.lower()
        elim_indicators = [
            "octa", "quart", "semi", "final", "double", "triple",
            "oct", "qf", "sf", "f", "dbls", "trips"
        ]
        
        return any(indicator in round_info for indicator in elim_indicators)
    
    def _similar_codes(self, code1, code2):
        """
        Check if two entry codes are similar
        
        Args:
            code1: First entry code
            code2: Second entry code
            
        Returns:
            bool: True if codes are similar, False otherwise
        """
        # Clean and normalize codes
        code1 = code1.lower().strip()
        code2 = code2.lower().strip()
        
        # Direct match
        if code1 == code2:
            return True
        
        # Compare parts (school name and team code)
        parts1 = code1.split()
        parts2 = code2.split()
        
        # Check for school name match (first parts)
        school1 = ' '.join(parts1[:-1]) if len(parts1) > 1 else code1
        school2 = ' '.join(parts2[:-1]) if len(parts2) > 1 else code2
        
        # Check for team code match (last parts)
        team1 = parts1[-1] if len(parts1) > 0 else ''
        team2 = parts2[-1] if len(parts2) > 0 else ''
        
        # Schools match and teams match
        if (school1 in school2 or school2 in school1) and team1 == team2:
            return True
        
        return False
    
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