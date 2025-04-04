# test_scraper_manager.py
import os
import sys
import logging
import argparse
import pandas as pd
from app.scraping import ScraperManager

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
    Test the Scraper Manager with different scraping modes
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test Tabroom Scraper Manager')
    parser.add_argument('--mode', choices=['judge_search'], default='judge_search',
                        help='Scraping mode to test')
    parser.add_argument('--query', type=str, help='Search query (e.g., judge name)')
    parser.add_argument('--username', type=str, help='Tabroom username')
    parser.add_argument('--password', type=str, help='Tabroom password')
    parser.add_argument('--output', type=str, default='data',
                        help='Output directory for results')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Initialize the scraper manager
    scraper = ScraperManager()
    
    try:
        # Ensure we're logged in
        if not scraper.ensure_login(args.username, args.password):
            print("Failed to log in. Please check your credentials.")
            return
        
        # Execute the requested scraping mode
        if args.mode == 'judge_search':
            if not args.query:
                args.query = input("Enter judge name to search: ")
            
            print(f"Searching for judge: {args.query}")
            results = scraper.search_judge(args.query)
            
            if not results.empty:
                print(f"Found {len(results)} records for {args.query}")
                print(results.head())
                
                # Save results to CSV
                safe_name = args.query.replace(" ", "_").lower()
                output_file = os.path.join(args.output, f"judge_{safe_name}.csv")
                results.to_csv(output_file, index=False)
                print(f"Results saved to {output_file}")
            else:
                print(f"No records found for {args.query}")
        
    finally:
        # Clean up resources
        scraper.close()

if __name__ == "__main__":
    main()
