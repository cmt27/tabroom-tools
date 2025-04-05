#!/usr/bin/env python3
"""
Test script for the tournament scraper functionality.

This script allows you to enter a tournament URL, runs the tournament scraper
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

# Import the necessary components
from app.scraping.scraper_manager import ScraperManager
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
        df: pandas DataFrame containing the judge records
    """
    # Handle None values or non-DataFrame objects
    if df is None:
        print("\nNo results found (search returned None).")
        return
    
    # Make sure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        print(f"\nNo results found (search returned {type(df)} instead of DataFrame).")
        return
        
    if df.empty:
        print("\nNo results found.")
        return
    
    print(f"\nFound {len(df)} rounds from the tournament.\n")
    
    # Display a summary of the results
    print("Summary of tournament data:")
    print("-" * 80)
    
    # Display tournament name and date if available
    if 'TournamentName' in df.columns and not df['TournamentName'].empty:
        print(f"Tournament: {df['TournamentName'].iloc[0]}")
    
    if 'TournamentDate' in df.columns and not df['TournamentDate'].empty:
        print(f"Date: {df['TournamentDate'].iloc[0]}")
    
    # Display judge count
    judge_count = len(df['JudgeID'].unique())
    print(f"\nTotal judges: {judge_count}")
    
    # Display tournaments found
    tournaments = df['Tournament'].unique()
    print(f"\nTournaments judged by these judges ({len(tournaments)}):")
    for tournament in tournaments:
        print(f"- {tournament}")
    
    # Display a sample of the rounds judged
    print("\nSample of rounds judged:")
    print("-" * 80)
    
    # Select columns to display
    display_cols = ['JudgeName', 'Tournament', 'Date', 'Rd', 'AffCode', 'NegCode', 'Vote', 'Result']
    
    # Add debater names if available
    if 'AffName' in df.columns and df['AffName'].any():
        display_cols.extend(['AffName', 'AffPoints'])
    
    if 'NegName' in df.columns and df['NegName'].any():
        display_cols.extend(['NegName', 'NegPoints'])
    
    # Display a sample of the data (first 5 rows)
    sample_df = df[display_cols].head(5)
    
    # Print each row in a readable format
    for _, row in sample_df.iterrows():
        print(f"Judge: {row['JudgeName']}")
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
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tournament_scrape_results_{timestamp}.csv"
        df.to_csv(filename, index=False)
        print(f"Results saved to {filename}")

def main():
    """Main function to run the tournament scraper test."""
    logger = setup_logging()
    
    print("=" * 80)
    print("Tournament Scraper Test")
    print("=" * 80)
    
    print("\nIMPORTANT: The tournament scraper functionality on Tabroom.com requires authentication")
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
            print("\nWARNING: Proceeding without authentication. The tournament scraper functionality")
            print("may not work properly without valid Tabroom.com credentials.")
    
    try:
        # Initialize the scraper manager
        print("\nInitializing scraper manager...")
        scraper_manager = ScraperManager(
            storage_dir=config.DATA_DIR,
            encryption_key=config.ENCRYPTION_KEY
        )
        
        # Login if credentials are provided
        if username and password:
            print("Logging in to Tabroom.com...")
            login_success = scraper_manager.ensure_login(username, password)
            if login_success:
                print("Login successful!")
            else:
                print("Login failed. Proceeding without authentication.")
        
        # Get tournament URL from user
        tournament_url = input("\nEnter tournament judge list URL: ")
        
        if not tournament_url:
            print("No tournament URL provided. Exiting.")
            return
        
        # Get max judges option
        max_judges_input = input("\nEnter maximum number of judges to scrape (leave blank for all): ")
        max_judges = int(max_judges_input) if max_judges_input.strip() else None
        
        # Run the scraper
        print(f"\nScraping tournament: {tournament_url}")
        print("This may take several minutes. Please wait...")
        
        # Set up more detailed logging for debugging
        logging.getLogger('app.scraping').setLevel(logging.DEBUG)
        
        try:
            # Ensure the scraper manager is properly initialized
            if not hasattr(scraper_manager, 'tournament_scraper') or scraper_manager.tournament_scraper is None:
                print("Initializing tournament scraper...")
                # Get a driver to force initialization
                driver = scraper_manager._get_authenticated_driver()
                if driver is None:
                    raise Exception("Failed to initialize authenticated driver")
                    
                if not scraper_manager._initialized_scrapers:
                    scraper_manager._initialize_scrapers()
                    
            # Now scrape the tournament
            results = scraper_manager.scrape_tournament(tournament_url, max_judges=max_judges)
            
            # Display the results
            display_results(results)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            print(f"\nAn unexpected error occurred: {e}")
            
        # Close the scraper manager
        print("\nClosing scraper manager...")
        scraper_manager.close()
        
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        print(f"\nAn error occurred: {e}")
    finally:
        # Clean up
        print("\nTest completed.")

if __name__ == "__main__":
    main()