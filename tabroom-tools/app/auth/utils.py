# app/auth/utils.py
import logging
from .session_manager import TabroomSession

logger = logging.getLogger(__name__)

def test_login(username, password):
    """
    Test login functionality
    
    Args:
        username: Tabroom username
        password: Tabroom password
        
    Returns:
        bool: True if login was successful, False otherwise
    """
    session = TabroomSession()
    return session.login(username, password)

def check_login_status():
    """
    Check if currently logged in
    
    Returns:
        bool: True if logged in, False otherwise
    """
    session = TabroomSession()
    return session.is_logged_in()

def get_authenticated_session(username=None, password=None):
    """
    Get an authenticated session (creating one if necessary)
    
    Args:
        username: Optional username to use if login is required
        password: Optional password to use if login is required
        
    Returns:
        TabroomSession: Authenticated session or None if authentication failed
    """
    session = TabroomSession()
    if session.ensure_login(username, password):
        return session
    return None

def clear_session():
    """
    Clear all session data (cookies, etc.)
    
    Returns:
        bool: True if successful, False otherwise
    """
    session = TabroomSession()
    return session.logout()