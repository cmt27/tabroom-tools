import os
import time
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.config import CONFIG
from utils.logger import logger
import json

# Determine a portable cookies file path using the current working directory.
# Updated to use the "resources" folder for cookies.
COOKIES_FILE_DEFAULT = CONFIG.get("COOKIES_FILE", os.path.join(os.getcwd(), "resources", "cookies.json"))

def load_cookies(driver, cookies_file=None):
    """
    Loads cookies from a file (default: resources/cookies.json relative to the current working directory)
    and adds them to the Selenium driver.
    
    This function first navigates to the base URL.
    Previously, it deleted all cookies, but to preserve saved cookies between sessions,
    we now refrain from deleting them. It loads cookies from the file—cleaning each cookie dictionary
    by omitting keys like "domain" and "sameSite", and ensuring the expiry is an integer.
    """
    if cookies_file is None:
        cookies_file = COOKIES_FILE_DEFAULT
    if not os.path.exists(cookies_file):
        logger.debug("No cookies file found.")
        return

    base_url = CONFIG.get("TABROOM_BASE_URL", "https://www.tabroom.com")
    driver.get(base_url)
    # Removed deletion of cookies to preserve saved session.
    with open(cookies_file, "r") as f:
        cookies = json.load(f)
    for cookie in cookies:
        # Build a new dictionary that excludes "domain" and "sameSite"
        new_cookie = {}
        for k, v in cookie.items():
            if k in ("domain", "sameSite"):
                continue
            if k == "expiry":
                try:
                    new_cookie[k] = int(v)
                except Exception:
                    continue
            else:
                new_cookie[k] = v
        try:
            driver.add_cookie(new_cookie)
        except Exception as e:
            logger.debug(f"Failed to add cookie {new_cookie}: {e}")
    logger.debug("Cookies loaded from file.")
    driver.refresh()

def save_cookies(driver, cookies_file=None):
    """
    Saves cookies from the Selenium driver to a file (default: resources/cookies.json relative to current working directory).
    
    This function removes the "domain" and "sameSite" keys from each cookie before saving.
    """
    if cookies_file is None:
        cookies_file = COOKIES_FILE_DEFAULT
    cookies = driver.get_cookies()
    cleaned_cookies = []
    for cookie in cookies:
        # Build a new cookie dict excluding "domain" and "sameSite"
        new_cookie = {k: v for k, v in cookie.items() if k not in ("domain", "sameSite")}
        if "expiry" in new_cookie:
            try:
                new_cookie["expiry"] = int(new_cookie["expiry"])
            except Exception:
                new_cookie.pop("expiry", None)
        cleaned_cookies.append(new_cookie)
    os.makedirs(os.path.dirname(cookies_file), exist_ok=True)
    with open(cookies_file, "w") as f:
        json.dump(cleaned_cookies, f)
    logger.debug("Cookies saved to file.")

def is_logged_in(driver) -> bool:
    """
    Checks if the user is logged in by inspecting the current URL and page content.
    
    Returns True if:
      - The current URL contains '/user/chapter', which indicates a logged-in state,
      - OR if the page source includes common login indicators such as 'logout' or 'my account'.
    
    Returns False if the URL contains '/user/login' or if such indicators are absent.
    """
    try:
        current_url = driver.current_url.lower()
        if "/user/login" in current_url:
            return False
        if "/user/chapter" in current_url:
            return True
        page_source = driver.page_source.lower()
        if "logout" in page_source or "my account" in page_source:
            return True
        return False
    except Exception:
        return False

def login(driver, username: str, password: str, cookies_file=None):
    """
    Logs into Tabroom using provided credentials.
    
    Process:
      1. Navigate to the base URL.
      2. If cookies have not been loaded on this driver instance, load them.
      3. Refresh the page and briefly wait to check if already logged in.
      4. If not logged in, navigate to the login page, submit credentials,
         and use an explicit wait to detect successful login.
      5. Save new cookies upon success.
    """
    if cookies_file is None:
        cookies_file = COOKIES_FILE_DEFAULT
    base_url = CONFIG.get("TABROOM_BASE_URL", "https://www.tabroom.com")
    logger.info("Logging in to tabroom.com")
    driver.get(base_url)
    time.sleep(2)
    # Only load cookies once per driver instance.
    if not hasattr(driver, "cookies_loaded"):
        load_cookies(driver, cookies_file)
        driver.cookies_loaded = True
    driver.refresh()
    # Brief wait to check if already logged in via cookies.
    try:
        WebDriverWait(driver, 5).until(lambda d: is_logged_in(d))
        if is_logged_in(driver):
            logger.info("Already logged in via cookies.")
            return
    except Exception:
        pass
    logger.info("Not logged in; performing login.")
    login_url = f"{base_url}/user/login/login"
    driver.get(login_url)
    logger.info(f"Navigated to login page: {login_url}")
    wait = WebDriverWait(driver, 30)
    username_input = wait.until(EC.visibility_of_element_located((By.ID, "login_email")))
    password_input = wait.until(EC.visibility_of_element_located((By.ID, "login_password")))
    username_input.clear()
    username_input.send_keys(username)
    password_input.clear()
    password_input.send_keys(password)
    password_input.send_keys(Keys.ENTER)
    logger.info("Sent ENTER key to submit the login form.")
    logger.info("Waiting for login to process...")
    try:
        WebDriverWait(driver, 10).until(lambda d: "/user/chapter" in d.current_url.lower())
    except Exception:
        logger.error("Login process timed out.")
    logger.info(f"Current URL after login attempt: {driver.current_url}")
    if is_logged_in(driver):
        logger.info("Successful login.")
        save_cookies(driver, cookies_file)
    else:
        logger.error("Login failed; please check credentials.")
        raise Exception("Login failed.")

def extract_clean(cell, field=None):
    """
    Cleans the content of a table cell by stripping HTML tags and extra whitespace.
    For the 'Date' field, extracts a date in YYYY-MM-DD format.
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

def scrape_judge_page(driver, judge_url: str, reload: bool = True) -> pd.DataFrame:
    """
    Navigates to an individual judge page (if reload is True) and extracts the judge record table.
    
    Returns a DataFrame with columns: JudgeID, JudgeName, Tournament, Lv, Date, Ev, Rd, Aff, Neg, Vote, Result.
    """
    logger.info(f"Scraping judge page from URL: {judge_url} (reload={reload})")
    if reload:
        driver.get(judge_url)
        time.sleep(2)
    wait = WebDriverWait(driver, 45)
    judge_id_match = re.search(r"judge_person_id=(\d+)", judge_url)
    judge_id = judge_id_match.group(1) if judge_id_match else ""
    try:
        judge_name = driver.find_element(By.TAG_NAME, "h3").text.strip()
        logger.info(f"Found judge name: {judge_name}")
    except Exception as e:
        logger.error(f"Could not find judge name: {e}")
        judge_name = ""
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#judgerecord tbody tr")))
        table_element = driver.find_element(By.CSS_SELECTOR, "#judgerecord")
        logger.info("Judge record table loaded.")
        time.sleep(2)
    except Exception as e:
        logger.error(f"Judge record table did not load properly: {e}")
        return pd.DataFrame()
    try:
        tbody = table_element.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
    except Exception as e:
        logger.error(f"Could not find tbody or rows in judge record table: {e}")
        return pd.DataFrame()
    logger.info(f"Found {len(rows)} rows in judge record table.")
    data_list = []
    for index, row in enumerate(rows[1:], start=2):
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 9:
                record = {
                    "JudgeID": judge_id,
                    "JudgeName": judge_name,
                    "Tournament": extract_clean(cols[0]),
                    "Lv": extract_clean(cols[1]),
                    "Date": extract_clean(cols[2], field="Date"),
                    "Ev": extract_clean(cols[3]),
                    "Rd": extract_clean(cols[4]),
                    "Aff": extract_clean(cols[5]),
                    "Neg": extract_clean(cols[6]),
                    "Vote": extract_clean(cols[7]),
                    "Result": extract_clean(cols[8], field="Result")
                }
                data_list.append(record)
            else:
                logger.debug(f"Skipping row {index} due to insufficient columns.")
        except Exception as e:
            logger.debug(f"Exception processing row {index}: {e}")
    if data_list:
        logger.info("Successfully extracted judge record data.")
        return pd.DataFrame(data_list)
    else:
        logger.error(f"No valid rows found on judge page: {judge_url}")
        return pd.DataFrame()

def test_login(driver_constructor, username: str, password: str) -> bool:
    """
    Helper function to test login using provided credentials.
    
    Creates a driver using driver_constructor, attempts login, and returns True if login is successful.
    """
    driver = driver_constructor()
    try:
        login(driver, username, password)
        return is_logged_in(driver)
    except Exception as e:
        logger.error(f"test_login encountered an error: {e}")
        return False
    finally:
        driver.quit()