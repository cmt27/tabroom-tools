# test_auth.py
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).resolve().parent))

from app.auth.session_manager import TabroomSession
from app.auth.utils import test_login, check_login_status, get_authenticated_session, get_authenticated_driver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_authentication():
    """Test the authentication module"""
    username = input("Enter your Tabroom username (email): ")
    password = input("Enter your Tabroom password: ")
    
    logger.info("=== Testing Browser Creation ===")
    session = TabroomSession()
    driver = session.get_driver()
    if driver:
        logger.info("Browser created successfully")
        session.release_driver(driver)
    else:
        logger.error("Failed to create browser")
    
    logger.info("\n=== Testing Direct Login ===")
    login_result = test_login(username, password)
    logger.info(f"Direct login result: {'Success' if login_result else 'Failed'}")
    
    logger.info("\n=== Testing Login Status Check ===")
    is_logged_in = check_login_status()
    logger.info(f"Login status: {'Logged in' if is_logged_in else 'Not logged in'}")
    
    logger.info("\n=== Testing Authenticated Session ===")
    auth_session = get_authenticated_session()
    if auth_session:
        logger.info("Got authenticated session successfully")
        
        logger.info("\n=== Testing Authenticated Driver ===")
        auth_driver = auth_session.get_driver()
        if auth_driver:
            logger.info("Got authenticated driver successfully")
            auth_session.release_driver(auth_driver)
        else:
            logger.error("Failed to get authenticated driver")
    else:
        logger.error("Failed to get authenticated session")
    
    # Check stored credentials
    logger.info("\n=== Testing Credential Storage ===")
    stored_credentials = auth_session.credential_manager.load_credentials()
    if stored_credentials:
        logger.info(f"Stored username: {stored_credentials.get('username')}")
        logger.info("Stored password: [REDACTED]")
    else:
        logger.error("Failed to load stored credentials")
    
    logger.info("\n=== Testing Logout ===")
    logout_result = auth_session.logout()
    logger.info(f"Logout result: {'Success' if logout_result else 'Failed'}")
    
    logger.info("\n=== Testing Login Status After Logout ===")
    is_logged_in = check_login_status()
    logger.info(f"Login status: {'Logged in' if is_logged_in else 'Not logged in'}")
    
    logger.info("\nAll tests completed")

if __name__ == "__main__":
    test_authentication()