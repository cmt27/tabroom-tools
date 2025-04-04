import time
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.config import CONFIG
from utils.logger import logger
from scrapers.scraper_common import login, scrape_judge_page

def scrape_judge_by_search(driver, judge_name: str) -> pd.DataFrame:
    """
    Uses Tabroom's judge search functionality to find a judge by name and scrape their data.
    
    Process:
      1. Navigate to the judge search page (https://www.tabroom.com/index/paradigm.mhtml).
      2. Locate separate input fields for first and last names using their name attributes.
         - Split judge_name and fill each field.
      3. Submit the form and wait for results.
      4. Attempt a direct match by checking for an <h3> element.
         - If the header text matches judge_name (case-insensitive), scrape the current page (without reloading).
      5. Otherwise, collect candidate links (those with href containing "judge_person_id"),
         filtering out known sidebar options.
      6. For each candidate link, locate its parent table row and extract the candidate’s full name
         from the first two <td> cells.
      7. Compare the candidate full name to the provided judge name (case-insensitive).
         - If an exact match is found, save its URL, click the link, and wait for a judge-specific element.
         - If the candidate URL isn't updated or lacks "judge_person_id", use driver.current_url as fallback.
      8. Call scrape_judge_page with the determined URL.
      9. If no exact match is found, log an error and return an empty DataFrame.
    """
    search_url = "https://www.tabroom.com/index/paradigm.mhtml"
    logger.info(f"Navigating to judge search page: {search_url}")
    driver.get(search_url)
    time.sleep(2)
    
    try:
        try:
            first_input = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.NAME, "search_first"))
            )
            last_input = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.NAME, "search_last"))
            )
            logger.info("Found separate input fields for judge first and last names.")
            
            parts = judge_name.strip().split(None, 1)
            if len(parts) == 2:
                first_name, last_name = parts[0], parts[1]
            else:
                first_name, last_name = "", parts[0]
            
            first_input.clear()
            first_input.send_keys(first_name)
            last_input.clear()
            last_input.send_keys(last_name)
            
            last_input.send_keys(Keys.ENTER)
            logger.info(f"Submitted judge search for first: '{first_name}' and last: '{last_name}'")
        except Exception as e:
            logger.debug(f"Separate first/last inputs not found or error occurred ({e}); falling back to single input.")
            search_input = WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.ID, "searchtext"))
            )
            search_input.clear()
            search_input.send_keys(judge_name)
            search_input.send_keys(Keys.ENTER)
            logger.info(f"Submitted judge search using single input for: '{judge_name}'")
        
        time.sleep(8)
        
        try:
            h3_element = driver.find_element(By.TAG_NAME, "h3")
            header_text = h3_element.text.strip()
            logger.info(f"Found header: '{header_text}'")
            if header_text.lower() == judge_name.strip().lower():
                logger.info("Direct match found via <h3> element; scraping judge page from current DOM.")
                return scrape_judge_page(driver, driver.current_url, reload=False)
        except Exception as e:
            logger.debug("No <h3> element found for direct match; proceeding to candidate links.")
        
        all_links = driver.find_elements(By.CSS_SELECTOR, "a")
        candidate_links = [link for link in all_links if link.get_attribute("href") and "judge_person_id=" in link.get_attribute("href")]
        logger.info(f"Found {len(candidate_links)} candidate judge result links based on href filtering.")
        
        if not candidate_links:
            logger.error("No candidate judge links found in search results.")
            page_source_snippet = driver.page_source[:1000]
            logger.debug(f"Page source snippet: {page_source_snippet}")
            return pd.DataFrame()
        
        excluded_texts = {"view past ratings", "view upcoming ratings", "view judging record"}
        
        for link in candidate_links:
            try:
                tr = link.find_element(By.XPATH, "./ancestor::tr")
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) >= 2:
                    candidate_first = tds[0].text.strip()
                    candidate_last = tds[1].text.strip()
                    candidate_full = f"{candidate_first} {candidate_last}"
                    logger.debug(f"Candidate full name: '{candidate_full}'")
                    
                    if candidate_full.lower() in excluded_texts:
                        logger.debug(f"Skipping excluded candidate: '{candidate_full}'")
                        continue
                    
                    if candidate_full.lower() == judge_name.strip().lower():
                        candidate_url = link.get_attribute("href")
                        logger.info(f"Exact match found: '{candidate_full}' with candidate URL: {candidate_url}")
                        link.click()
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "h3"))
                        )
                        if candidate_url == search_url or "judge_person_id=" not in candidate_url:
                            candidate_url = driver.current_url
                            logger.debug("Candidate URL not updated; using current URL from DOM as fallback.")
                        return scrape_judge_page(driver, candidate_url)
                else:
                    logger.debug("Candidate row does not have enough columns to extract name.")
            except Exception as inner_e:
                logger.debug(f"Error processing candidate row: {inner_e}")
                continue
        
        logger.error("No exact match found among the search results.")
        return pd.DataFrame()
    
    except Exception as e:
        logger.error(f"Error during judge search scraping for '{judge_name}': {e}")
        return pd.DataFrame()