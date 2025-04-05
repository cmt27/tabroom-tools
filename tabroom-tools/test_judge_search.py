#!/usr/bin/env python3
"""
Test script for the judge search scraper functionality.

This script allows you to enter a judge's name, runs the judge search scraper
on tabroom.com, and displays the extracted output. Error logging is included
via the terminal.
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path

# Add the tabroom-tools directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent / "tabroom-tools"))

# Apply the patch to fix method name inconsistencies
try:
    # Import the patch module
    from judge_search_patch import *
    print("Applied patch for method name inconsistencies")
except ImportError:
    print("Warning: Could not apply patch for method name inconsistencies")
    print("If you encounter errors about 'get_authenticated_driver', run the judge_search_patch.py script first")

# Import the necessary components
from app.auth.session_manager import TabroomSession
from app.scraping.judge_search import JudgeSearchScraper
from app import config

# Configure logging
def setup_logging():
    """Set up logging to both file and console."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    
    return logger

def display_results(df):
    """
    Display the results in a readable format.
    
    Args:
        df: pandas DataFrame containing the judge's record
    """
    # Handle None values or non-DataFrame objects
    if df is None:
        print("\nNo results found for this judge (search returned None).")
        return
    
    # Make sure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        print(f"\nNo results found for this judge (search returned {type(df)} instead of DataFrame).")
        return
        
    if df.empty:
        print("\nNo results found for this judge.")
        return
    
    print(f"\nFound {len(df)} rounds judged by this judge.\n")
    
    # Display a summary of the results
    print("Summary of judging record:")
    print("-" * 80)
    
    # Display judge name and ID
    if 'JudgeName' in df.columns and not df['JudgeName'].empty:
        print(f"Judge Name: {df['JudgeName'].iloc[0]}")
    
    if 'JudgeID' in df.columns and not df['JudgeID'].empty:
        print(f"Judge ID: {df['JudgeID'].iloc[0]}")
    
    # Display tournaments judged
    tournaments = df['Tournament'].unique()
    print(f"\nTournaments judged ({len(tournaments)}):")
    for tournament in tournaments:
        print(f"- {tournament}")
    
    # Display a sample of the rounds judged
    print("\nSample of rounds judged:")
    print("-" * 80)
    
    # Select columns to display
    display_cols = ['Tournament', 'Date', 'Rd', 'AffCode', 'NegCode', 'Vote', 'Result']
    
    # Add debater names if available
    if 'AffName' in df.columns and df['AffName'].any():
        display_cols.extend(['AffName', 'AffPoints'])
    
    if 'NegName' in df.columns and df['NegName'].any():
        display_cols.extend(['NegName', 'NegPoints'])
    
    # Display a sample of the data (first 5 rows)
    sample_df = df[display_cols].head(5)
    
    # Print each row in a readable format
    for _, row in sample_df.iterrows():
        print(f"Tournament: {row['Tournament']}")
        print(f"Date: {row['Date']}")
        print(f"Round: {row['Rd']}")
        print(f"Aff: {row['AffCode']}")
        if 'AffName' in row and row['AffName']:
            print(f"Aff Name: {row['AffName']}")
            if 'AffPoints' in row and row['AffPoints']:
                print(f"Aff Points: {row['AffPoints']}")
        
        print(f"Neg: {row['NegCode']}")
        if 'NegName' in row and row['NegName']:
            print(f"Neg Name: {row['NegName']}")
            if 'NegPoints' in row and row['NegPoints']:
                print(f"Neg Points: {row['NegPoints']}")
        
        print(f"Vote: {row['Vote']}")
        print(f"Result: {row['Result']}")
        print("-" * 40)
    
    # Option to save the data
    save = input("\nWould you like to save the full results to a CSV file? (y/n): ")
    if save.lower() == 'y':
        filename = f"judge_record_{df['JudgeName'].iloc[0].replace(' ', '_')}.csv"
        df.to_csv(filename, index=False)
        print(f"Results saved to {filename}")

def main():
    """Main function to run the judge search scraper test."""
    logger = setup_logging()
    
    print("=" * 80)
    print("Judge Search Scraper Test")
    print("=" * 80)
    
    print("\nIMPORTANT: The judge search functionality on Tabroom.com requires authentication")
    print("for full functionality. For best results, please provide your Tabroom.com credentials.")
    
    # Check if credentials are provided
    username = os.environ.get("TABROOM_USERNAME")
    password = os.environ.get("TABROOM_PASSWORD")
    
    if not username or not password:
        print("\nTabroom.com credentials not found in environment variables.")
        print("You can set them using:")
        print("  export TABROOM_USERNAME=your_username")
        print("  export TABROOM_PASSWORD=your_password")
        
        use_login = input("\nWould you like to enter credentials now? (y/n): ")
        if use_login.lower() == 'y':
            username = input("Tabroom.com username/email: ")
            password = input("Tabroom.com password: ")
        else:
            print("\nWARNING: Proceeding without authentication. The judge search functionality")
            print("may not work properly without valid Tabroom.com credentials.")
    
    try:
        # Initialize the session manager
        print("\nInitializing session manager...")
        session_manager = TabroomSession(
            storage_dir=config.DATA_DIR,
            encryption_key=config.ENCRYPTION_KEY
        )
        
        # Login if credentials are provided
        if username and password:
            print("Logging in to Tabroom.com...")
            login_success = session_manager.login(username, password)
            if login_success:
                print("Login successful!")
            else:
                print("Login failed. Proceeding without authentication.")
        else:
            print("Proceeding without authentication. Creating a direct browser session...")
            # Create a direct browser session without authentication
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            
            # Set up Chrome options
            chrome_options = Options()
            if config.HEADLESS:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Create a Chrome service
            service = Service(executable_path=config.CHROMIUM_DRIVER_PATH)
            
            # Create a driver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Override the get_driver method to return our driver
            def get_driver_override():
                return driver
            
            # Override the release_driver method to do nothing
            def release_driver_override(driver=None):
                pass
            
            # Add get_authenticated_driver method for compatibility
            def get_authenticated_driver_override():
                return driver
            
            # Add a method to save the page source for debugging
            def save_page_source(driver, filename):
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    print(f"Page source saved to {filename}")
                except Exception as e:
                    print(f"Error saving page source: {e}")
            
            # Add the method to the global scope
            globals()['save_page_source'] = save_page_source
            
            # Monkey patch the session manager
            session_manager.get_driver = get_driver_override
            session_manager.get_authenticated_driver = get_authenticated_driver_override
            session_manager.release_driver = release_driver_override
        
        # Initialize the judge search scraper
        print("Initializing judge search scraper...")
        scraper = JudgeSearchScraper(session_manager)
        
        # Get judge name from user
        judge_name = input("\nEnter judge name (first and last name): ")
        
        if not judge_name:
            print("No judge name provided. Exiting.")
            return
        
        # Run the search
        print(f"\nSearching for judge: {judge_name}")
        print("This may take a minute or two. Please wait...")
        
        # Set up more detailed logging for debugging
        logging.getLogger('app.scraping.judge_search').setLevel(logging.DEBUG)
        
        try:
            # Wrap the search in a try-except block to catch any errors
            try:
                results = scraper.search_judge(judge_name)
            except Exception as e:
                logger.error(f"Error during judge search: {e}")
                # Create an empty DataFrame as a fallback
                results = pd.DataFrame()
            
            # Make sure results is a DataFrame, even if empty
            if results is None:
                logger.warning("Search returned None instead of a DataFrame")
                results = pd.DataFrame()
            elif not isinstance(results, pd.DataFrame):
                logger.warning(f"Search returned {type(results)} instead of DataFrame")
                results = pd.DataFrame()
            
            # Display the results
            display_results(results)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            print(f"\nAn unexpected error occurred: {e}")
            
            # Create an empty DataFrame as a fallback
            results = pd.DataFrame()
            
            # Try to display results even after an error
            try:
                display_results(results)
            except:
                print("\nNo results found for this judge (error displaying results).")
        
        # If no results were found, provide some debugging information
        if results.empty:
            print("\nDebugging information:")
            print("1. Authentication is required: The judge search functionality requires valid Tabroom.com credentials.")
            print("   Please run the script again and provide your credentials when prompted.")
            print("2. Try different name formats: Some judges may be found using 'Last, First' instead of 'First Last'.")
            print("3. Verify the judge exists: Make sure the judge is actually in the Tabroom.com database.")
            print("4. Check the debug file: The HTML of the search results page has been saved to:")
            print(f"   {os.path.join(config.DATA_DIR, 'search_results_debug.html')}")
        
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        print(f"\nAn error occurred: {e}")
    finally:
        # Clean up
        print("\nTest completed.")

if __name__ == "__main__":
    main()