# test_judge_search.py
import os
import sys
import logging
import pandas as pd
from app.auth.session_manager import TabroomSession
from app.scraping.judge_search import JudgeSearchScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    """
    Test the Judge Search Mode scraper
    """
    # Initialize the session manager
    session = TabroomSession()
    
    # Ensure we're logged in
    if not session.ensure_login():
        print("Failed to log in. Please check your credentials.")
        return
    
    # Initialize the judge search scraper
    scraper = JudgeSearchScraper(session)
    
    # Example judge name to search for
    judge_name = input("Enter judge name to search (e.g., 'John Smith'): ")
    
    # Search for the judge
    print(f"Searching for judge: {judge_name}")
    results = scraper.search_judge(judge_name)
    
    # Display results
    if not results.empty:
        print(f"Found {len(results)} records for {judge_name}")
        print(results.head())
        
        # Save results to CSV
        output_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(output_dir, exist_ok=True)
        
        safe_name = judge_name.replace(" ", "_").lower()
        output_file = os.path.join(output_dir, f"judge_{safe_name}.csv")
        results.to_csv(output_file, index=False)
        print(f"Results saved to {output_file}")
    else:
        print(f"No records found for {judge_name}")

if __name__ == "__main__":
    main()