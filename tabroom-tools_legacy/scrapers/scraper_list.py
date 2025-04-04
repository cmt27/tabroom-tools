import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from config.config import CONFIG
from utils.logger import logger
from scrapers.scraper_common import login, scrape_judge_page

def get_judge_page_urls(driver) -> list:
    """
    Extracts judge page URLs from the judge list page using CSS selectors.
    """
    judge_urls = []
    wait = WebDriverWait(driver, 30)
    table = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "#judgelist"))
    logger.info("Judge list table found.")
    
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    logger.info(f"Found {len(rows)} judge list rows.")
    
    for row in rows:
        try:
            link = row.find_element(By.CSS_SELECTOR, "a.white.full.padvert").get_attribute("href")
            if link:
                judge_urls.append(link)
        except Exception:
            logger.debug("No active judge link found in a row; skipping row.")
            continue
    return judge_urls

def scrape_judges(judge_list_url: str, username: str, password: str) -> pd.DataFrame:
    """
    Scrapes judge data using the tournament judge list.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = CONFIG.get("CHROMIUM_BINARY", "/usr/bin/chromium")
    
    driver = webdriver.Chrome(options=chrome_options)
    combined_data = []
    
    try:
        logger.info("Starting login process for tournament list scraping...")
        login(driver, username, password)
        
        logger.info(f"Navigating to judge list page: {judge_list_url}")
        driver.get(judge_list_url)
        time.sleep(2)
        
        judge_urls = get_judge_page_urls(driver)
        logger.info(f"Total judge page URLs extracted: {len(judge_urls)}")
        
        scrape_limit = CONFIG.get("SCRAPE_LIMIT", 3)
        if scrape_limit <= 0:
            scrape_limit = None  # Treat 0 or negative as no limit
        
        logger.info(f"Processing up to {scrape_limit if scrape_limit else 'all'} judge pages.")
        for url in judge_urls[:scrape_limit]:
            try:
                logger.info(f"Scraping judge page: {url}")
                df_judge = scrape_judge_page(driver, url)
                if not df_judge.empty:
                    combined_data.append(df_judge)
                else:
                    logger.error(f"No data extracted from judge page: {url}")
            except Exception as e:
                logger.error(f"Exception processing judge page {url}: {e}")
                continue
        
        if combined_data:
            combined_df = pd.concat(combined_data, ignore_index=True)
            logger.info("Successfully scraped judge data from tournament list.")
            return combined_df
        else:
            logger.error("No judge data found after processing all judge pages.")
            return pd.DataFrame()
    
    except Exception as e:
        raise Exception(f"Error during tournament list scraping: {e}")
    finally:
        driver.quit()