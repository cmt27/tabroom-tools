import sys
import os
# Add the parent directory (i.e. /app) to sys.path so that sibling packages are found.
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

from config.config import CONFIG
from utils.logger import logger
from scrapers.scraper_list import scrape_judges
from scrapers.scraper_search import scrape_judge_by_search
from scrapers.scraper_common import login, is_logged_in
from data.data_store import refresh_judge_data, export_judge_data_csv, search_judge_data
from metrics.compute_metrics import compute_metrics_per_judge, compute_metrics_for_team_per_judge

# Function to create a new Selenium driver instance.
def get_driver():
    chrome_options = Options()
    opts = CONFIG.get("CHROME_DRIVER_OPTIONS", {})
    if opts.get("headless", False):
        chrome_options.add_argument("--headless")
    if opts.get("no_sandbox", False):
        chrome_options.add_argument("--no-sandbox")
    if opts.get("disable_dev_shm_usage", False):
        chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = CONFIG.get("CHROMIUM_BINARY", "/usr/bin/chromium")
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    return driver

def get_logged_in_driver():
    """
    Returns a persistent, logged-in Selenium driver stored in st.session_state.
    If a valid driver exists and is logged in, it is returned; otherwise, a new driver is created,
    logged in, and stored in st.session_state.
    """
    if "driver" in st.session_state:
        driver = st.session_state.driver
        try:
            if is_logged_in(driver):
                logger.info("Reusing existing logged-in driver from session state.")
                return driver
        except Exception:
            pass
    driver = get_driver()
    # Use the credentials stored in session_state (which should have been set during login).
    login(driver, st.session_state.username, st.session_state.password)
    st.session_state.driver = driver
    return driver

# Initialize session state for login credentials if not already set.
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'password' not in st.session_state:
    st.session_state.password = ""

# --- Login Section ---
if not st.session_state.logged_in:
    st.title("Tabroom Tools")
    st.write("""
        **Welcome to Tabroom Tools!**
        
        This application allows you to import judge data from Tabroom using several methods:
        
        - **Import Tournament Judge Data:** Enter a tournament judge list URL to import judge records.
        - **Search Stored Judge Data:** Search through your stored judge data by judge name.
        - **Direct Judge Data Scraping:** Directly scrape judge data from Tabroom's judge search page.
        
        You also have the option to filter the data by team/entry. When active, an additional CSV export 
        will be provided with per‑judge metrics computed for rounds involving that team/entry.
        
        Please log in with your Tabroom credentials to begin.
    """)
    
    username = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Log In"):
        if username.strip() == "" or password.strip() == "":
            st.error("Both email and password are required.")
        else:
            try:
                driver = get_driver()
                # Explicitly perform login using provided credentials.
                login(driver, username, password)
                if is_logged_in(driver):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.password = password
                    st.session_state.driver = driver
                    st.success("Login successful!")
                    st.experimental_rerun()  # Refresh to display mode options.
                else:
                    st.error("Login failed. Please check your credentials.")
            except Exception as e:
                st.error(f"An error occurred during login: {e}")

# --- Main Application ---
if st.session_state.logged_in:
    st.sidebar.title("Data Import Options")
    mode = st.sidebar.selectbox("Select an Option", [
        "Import Tournament Judge Data", 
        "Search Stored Judge Data", 
        "Direct Judge Data Scraping"
    ])
    st.sidebar.write("""
        **Import Tournament Judge Data:**  
        Enter a tournament judge list URL to import judge records.
        
        **Search Stored Judge Data:**  
        Search through your stored judge data by judge name.
        
        **Direct Judge Data Scraping:**  
        Directly scrape judge data from Tabroom's judge search page.
    """)

    # Option for team/entry filtering (applies across modes)
    use_team_filter = st.sidebar.checkbox("Apply Team/Entry Filter")
    team_filter = ""
    if use_team_filter:
        team_filter = st.sidebar.text_input("Team/Entry (e.g., Main High School)", value="")

    # For tasks that require accessing Tabroom, obtain the persistent logged-in driver.
    driver = None
    if mode in ["Import Tournament Judge Data", "Direct Judge Data Scraping"]:
        driver = get_logged_in_driver()
    from utils.auth import load_cookies, apply_cookies_to_context, is_logged_in_from_cookies, login_if_required
    apply_cookies_to_context(driver, load_cookies())
    if not is_logged_in_from_cookies(driver):
        driver.get("https://www.tabroom.com/user/login")
        login_if_required(driver)
    from utils.auth import load_cookies, apply_cookies_to_context, is_logged_in_from_cookies, login_if_required
    apply_cookies_to_context(driver, load_cookies())
    if not is_logged_in_from_cookies(driver):
        page = driver
        page.goto("https://www.tabroom.com/user/login")
        login_if_required(page)

    def display_export_buttons(raw_csv, overall_metrics_df, team_metrics_df=None):
        overall_metrics_df = overall_metrics_df.drop(columns=["JudgeID"], errors="ignore")
        if team_metrics_df is not None:
            team_metrics_df = team_metrics_df.drop(columns=["JudgeID"], errors="ignore")
            try:
                col1, col2, col3 = st.columns(3)
            except Exception as e:
                logger.debug(f"Expected 3 columns but got fewer: {e}")
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("Download Raw Data CSV", data=raw_csv, file_name="judge_data.csv", mime="text/csv")
                with col2:
                    csv_overall = overall_metrics_df.to_csv(index=False).encode("utf-8")
                    st.download_button("Download Overall Metrics CSV", data=csv_overall, file_name="judge_metrics.csv", mime="text/csv")
                st.download_button("Download Team Metrics CSV", data=team_metrics_df.to_csv(index=False).encode("utf-8"),
                                   file_name="judge_team_metrics.csv", mime="text/csv")
                return
            with col1:
                st.download_button("Download Raw Data CSV", data=raw_csv, file_name="judge_data.csv", mime="text/csv")
            with col2:
                csv_overall = overall_metrics_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Overall Metrics CSV", data=csv_overall, file_name="judge_metrics.csv", mime="text/csv")
            with col3:
                csv_team = team_metrics_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Team Metrics CSV", data=csv_team, file_name="judge_team_metrics.csv", mime="text/csv")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("Download Raw Data CSV", data=raw_csv, file_name="judge_data.csv", mime="text/csv")
            with col2:
                csv_overall = overall_metrics_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Overall Metrics CSV", data=csv_overall, file_name="judge_metrics.csv", mime="text/csv")

    if mode == "Import Tournament Judge Data":
        st.header("Import Tournament Judge Data")
        st.write("Enter the tournament judge list URL to import judge records.")
        judge_list_url = st.text_input("Judge List URL")
        
        if st.button("Import Data"):
            if judge_list_url.strip() == "":
                st.error("Please enter a valid judge list URL.")
            else:
                st.info("Importing data, please wait...")
                try:
                    data = scrape_judges(judge_list_url, st.session_state.username, st.session_state.password)
                    refresh_judge_data(data)
                    raw_csv = export_judge_data_csv()
                    overall_metrics = compute_metrics_per_judge(data)
                    
                    team_metrics = None
                    if use_team_filter and team_filter.strip() != "":
                        team_metrics = compute_metrics_for_team_per_judge(data, team_filter)
                    
                    st.success("Data import complete!")
                    display_export_buttons(raw_csv, overall_metrics, team_metrics_df=team_metrics)
                except Exception as e:
                    st.error(f"An error occurred during data import: {e}")
    
    elif mode == "Search Stored Judge Data":
        st.header("Search Stored Judge Data")
        st.write("Enter a judge name to search through your stored judge data.")
        judge_name = st.text_input("Judge Name")
        
        if st.button("Search Data"):
            if judge_name.strip() == "":
                st.error("Please enter a judge name.")
            else:
                st.info(f"Searching for judge '{judge_name}'...")
                try:
                    results = search_judge_data(judge_name)
                    if results.empty:
                        st.warning("No records found for the given judge.")
                    else:
                        raw_csv = results.to_csv(index=False).encode("utf-8")
                        overall_metrics = compute_metrics_per_judge(results)
                        team_metrics = None
                        if use_team_filter and team_filter.strip() != "":
                            team_metrics = compute_metrics_for_team_per_judge(results, team_filter)
                        st.success("Data found!")
                        display_export_buttons(raw_csv, overall_metrics, team_metrics_df=team_metrics)
                except Exception as e:
                    st.error(f"An error occurred during the search: {e}")
    
    elif mode == "Direct Judge Data Scraping":
        st.header("Direct Judge Data Scraping")
        st.write("Enter the judge's name to directly scrape their data using Tabroom's judge search page.")
        judge_name = st.text_input("Judge Name for Scraping", key="scrape_judge_name")
        
        if st.button("Scrape Judge Data"):
            if judge_name.strip() == "":
                st.error("Please enter a judge name.")
            else:
                st.info("Scraping judge data, please wait...")
                try:
                    data = scrape_judge_by_search(driver, judge_name)
                    if data.empty:
                        st.error("No judge data was found. Please check the judge name or try again later.")
                    else:
                        refresh_judge_data(data)
                        raw_csv = export_judge_data_csv()
                        overall_metrics = compute_metrics_per_judge(data)
                        team_metrics = None
                        if use_team_filter and team_filter.strip() != "":
                            team_metrics = compute_metrics_for_team_per_judge(data, team_filter)
                        st.success("Data scraping complete!")
                        display_export_buttons(raw_csv, overall_metrics, team_metrics_df=team_metrics)
                except Exception as e:
                    st.error(f"An error occurred during judge data scraping: {e}")