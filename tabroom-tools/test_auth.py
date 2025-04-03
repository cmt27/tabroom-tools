# test_auth.py
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).resolve().parent))

from app.auth.session_manager import TabroomSession
from app.auth.utils import test_login, check_login_status, get_authenticated_session, clear_session

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
    
    logger.info("Testing direct login...")
    session = TabroomSession()
    login_result = session.login(username, password)
    logger.info(f"Direct login result: {'Success' if login_result else 'Failed'}")
    
    logger.info("Testing login status check...")
    is_logged_in = check_login_status()
    logger.info(f"Login status: {'Logged in' if is_logged_in else 'Not logged in'}")
    
    logger.info("Testing get_authenticated_session...")
    auth_session = get_authenticated_session()
    logger.info(f"Got authenticated session: {'Yes' if auth_session else 'No'}")
    
    logger.info("Testing logout...")
    logout_result = clear_session()
    logger.info(f"Logout result: {'Success' if logout_result else 'Failed'}")
    
    logger.info("Testing login status after logout...")
    is_logged_in = check_login_status()
    logger.info(f"Login status: {'Logged in' if is_logged_in else 'Not logged in'}")
    
    # Test credential storage and encryption
    logger.info("Testing credential storage...")
    if os.path.exists(session.credentials_file):
        logger.info(f"Credentials file exists: {session.credentials_file}")
        stored_credentials = session.load_credentials()
        if stored_credentials:
            logger.info(f"Stored username: {stored_credentials.get('username')}")
            logger.info("Stored password: [REDACTED]")
        else:
            logger.error("Failed to load stored credentials")
    else:
        logger.warning(f"Credentials file does not exist: {session.credentials_file}")
    
    logger.info("All tests completed")

if __name__ == "__main__":
    test_authentication()