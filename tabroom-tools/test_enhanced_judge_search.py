# test_enhanced_judge_search.py
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

logger = logging.getLogger(__name__)

def validate_entry_data(df):
    """
    Validate that the dataframe contains the enhanced entry data fields
    
    Args:
        df: DataFrame from judge search
        
    Returns:
        bool: True if enhanced data present, False otherwise
    """
    # Check that the enhanced fields exist
    required_fields = ["AffCode", "AffName", "AffPoints", "NegCode", "NegName", "NegPoints"]
    missing_fields = [field for field in required_fields if field not in df.columns]
    
    if missing_fields:
        logger.error(f"Missing required fields: {missing_fields}")
        return False
    
    # Check that at least some rows have entry names populated
    aff_names_present = df["AffName"].astype(str).str.strip().str.len() > 0
    neg_names_present = df["NegName"].astype(str).str.strip().str.len() > 0
    
    if not aff_names_present.any() and not neg_names_present.any():
        logger.error("No entry names were found in the data")
        return False
    
    # Check that at least some preliminary rounds have points (elims won't have points)
    aff_points_present = df["AffPoints"].astype(str).str.strip().str.len() > 0
    neg_points_present = df["NegPoints"].astype(str).str.strip().str.len() > 0
    points_present = aff_points_present | neg_points_present
    
    if not points_present.any():
        logger.warning("No points were found in the data. This may be normal if all rounds are elimination rounds.")
    
    # Basic data quality checks
    logger.info(f"Rows with Aff names: {aff_names_present.sum()} of {len(df)}")
    logger.info(f"Rows with Neg names: {neg_names_present.sum()} of {len(df)}")
    logger.info(f"Rows with points: {points_present.sum()} of {len(df)}")
    
    # Print some sample rows for manual verification
    if not df.empty:
        sample_size = min(3, len(df))
        logger.info(f"\nSample of {sample_size} rows with enhanced data:")
        sample_rows = df.sample(n=sample_size) if len(df) > sample_size else df
        
        for _, row in sample_rows.iterrows():
            logger.info(f"Round: {row.get('Rd', '?')} - Date: {row.get('Date', '?')}")
            logger.info(f"Aff: {row.get('AffCode', '?')} - {row.get('AffName', '?')} - Points: {row.get('AffPoints', '?')}")
            logger.info(f"Neg: {row.get('NegCode', '?')} - {row.get('NegName', '?')} - Points: {row.get('NegPoints', '?')}")
            logger.info(f"Vote: {row.get('Vote', '?')} - Result: {row.get('Result', '?')}\n")
    
    return True

def main():
    """
    Test the enhanced Judge Search Mode scraper
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
    judge_name = input("Enter judge name to search (e.g., 'Chris Theis'): ")
    
    # Search for the judge
    print(f"Searching for judge: {judge_name}")
    results = scraper.search_judge(judge_name)
    
    # Display results
    if not results.empty:
        print(f"Found {len(results)} records for {judge_name}")
        
        # Validate the enhanced data fields
        if validate_entry_data(results):
            print("✅ Enhanced judge data validation successful")
        else:
            print("❌ Enhanced judge data validation failed")
        
        # Save results to CSV
        output_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(output_dir, exist_ok=True)
        
        safe_name = judge_name.replace(" ", "_").lower()
        output_file = os.path.join(output_dir, f"enhanced_judge_{safe_name}.csv")
        results.to_csv(output_file, index=False)
        print(f"Results saved to {output_file}")
    else:
        print(f"No records found for {judge_name}")

if __name__ == "__main__":
    main()