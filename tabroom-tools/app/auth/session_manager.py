# app/auth/session_manager.py
import logging
import time
import traceback
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

from app import config
from app.auth.driver_pool import WebDriverPool
from app.auth.credential_manager import CredentialManager
from app.auth.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class TabroomSession:
    """Authentication and session management for tabroom.com"""
    
    def __init__(self, storage_dir=None, encryption_key=None):
        """
        Initialize the session manager
        
        Args:
            storage_dir: Directory to store session data (cookies, credentials)
            encryption_key: Key for encrypting credentials
        """
        self.driver_pool = WebDriverPool()
        self.credential_manager = CredentialManager(storage_dir, encryption_key)
        self.cookie_manager = CookieManager(storage_dir)
        self._login_verified = False
        
    def login(self, username=None, password=None, save_credentials=True, max_retries=3):
        """
        Login to tabroom.com using form submission
        
        Args:
            username: Tabroom username/email
            password: Tabroom password
            save_credentials: Whether to save credentials for future use
            max_retries: Maximum number of login attempts
            
        Returns:
            bool: True if login successful, False otherwise
        """
        # Get credentials if not provided
        if not username or not password:
            stored_credentials = self.credential_manager.load_credentials()
            if stored_credentials:
                username = stored_credentials.get("username")
                password = stored_credentials.get("password")
            
            if not username or not password:
                logger.error("No credentials provided and no stored credentials found")
                return False
        
        # Save credentials if requested
        if save_credentials:
            self.credential_manager.save_credentials(username, password)
        
        # Attempt login
        driver = None
        login_success = False
        attempt = 0
        
        while attempt < max_retries and not login_success:
            attempt += 1
            logger.info(f"Login attempt {attempt}/{max_retries}")
            
            try:
                # Get a driver
                driver = self.driver_pool.get_driver(reuse=False)  # Force a fresh driver for login
                if not driver:
                    logger.error("Failed to create browser driver")
                    continue
                
                # Navigate to login page
                driver.get(config.LOGIN_URL)
                logger.info(f"Loaded login page: {driver.title}")
                
                # Wait for page to load
                time.sleep(2)
                
                # Based on the HTML structure, target the specific elements
                # Use JavaScript for more reliable interaction across browsers
                form_filled = driver.execute_script("""
                    // Check if main login form exists
                    var emailField = document.getElementById('login_email');
                    var passwordField = document.getElementById('login_password');
                    
                    if (!emailField || !passwordField) {
                        // Try looking for the fields in the login-popup
                        emailField = document.getElementById('username');
                        passwordField = document.getElementById('password');
                        
                        if (!emailField || !passwordField) {
                            return false;
                        }
                    }
                    
                    // Clear and set values
                    emailField.value = '';
                    passwordField.value = '';
                    emailField.value = arguments[0];
                    passwordField.value = arguments[1];
                    
                    return true;
                """, username, password)
                
                if not form_filled:
                    logger.error("Failed to find and fill login form")
                    continue
                
                # Submit the form instead of clicking the button
                form_submitted = driver.execute_script("""
                    // Find the form the login fields belong to
                    var emailField = document.getElementById('login_email') || document.getElementById('username');
                    if (!emailField) return false;
                    
                    var form = emailField.closest('form');
                    if (form) {
                        // Submit the form
                        form.submit();
                        return true;
                    }
                    return false;
                """)
                
                if not form_submitted:
                    logger.error("Failed to submit login form")
                    continue
                
                # Wait for page to load after login
                time.sleep(3)
                
                # Check if login was successful
                login_success = self._verify_login(driver, username)
                
                if login_success:
                    self._login_verified = True
                    logger.info(f"Login successful for {username}")
                    self.cookie_manager.save_cookies(driver)
                    return True
                else:
                    # Try to get any error messages
                    error_message = driver.execute_script("""
                        var warnings = document.getElementsByClassName('warning');
                        if (warnings.length > 0) {
                            return warnings[0].textContent.trim();
                        }
                        return '';
                    """)
                    
                    if error_message:
                        logger.error(f"Login failed: {error_message}")
                    else:
                        logger.error("Login failed: No success indicators found")
                
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"Login error: {e}\n{error_trace}")
            finally:
                # Brief delay before retry
                if attempt < max_retries and not login_success:
                    time.sleep(config.RETRY_DELAY)
        
        # Release driver if we're returning
        if driver:
            self.driver_pool.release_driver()
            
        return login_success
    
    def is_logged_in(self):
        """
        Check if the current session is logged in
        
        Returns:
            bool: True if logged in, False otherwise
        """
        # If we've already verified login in this session, avoid redundant checks
        if self._login_verified:
            logger.debug("Login already verified in this session")
            return True
            
        # Check if cookies exist before creating a driver
        if not os.path.exists(self.cookie_manager.cookie_file):
            logger.debug("No cookie file exists, not logged in")
            return False
            
        driver = None
        try:
            driver = self.driver_pool.get_driver()
            if not driver:
                logger.error("Failed to create driver for login check")
                return False
            
            # Try to load cookies
            if not self.cookie_manager.load_cookies(driver, config.TABROOM_URL):
                logger.warning("Failed to load cookies")
                return False
            
            # Navigate to a page that requires login
            driver.get(f"{config.TABROOM_URL}/user/home.mhtml")
            
            # Check for logout link or other logged-in indicators
            is_logged_in = self._verify_login(driver)
            if is_logged_in:
                self._login_verified = True
            
            return is_logged_in
            
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
        finally:
            if driver:
                self.driver_pool.release_driver()
    
    def ensure_login(self, username=None, password=None):
        """
        Ensure we have an active session, logging in if necessary
        
        Args:
            username: Username to use if login is required
            password: Password to use if login is required
            
        Returns:
            bool: True if logged in, False otherwise
        """
        # Check if already logged in
        if self.is_logged_in():
            logger.info("Already logged in")
            return True
        
        # If not logged in, attempt login
        logger.info("Not logged in, attempting login")
        login_result = self.login(username, password)
        
        # Update login verification flag
        self._login_verified = login_result
        
        return login_result
    
    def logout(self):
        """
        Logout from tabroom.com and clear session data
        
        Returns:
            bool: True if successful, False otherwise
        """
        driver = None
        try:
            driver = self.driver_pool.get_driver()
            if not driver:
                # Clear cookies even if driver creation fails
                self.cookie_manager.clear_cookies()
                self._login_verified = False
                return True
            
            # Load cookies first
            if self.cookie_manager.load_cookies(driver, config.TABROOM_URL):
                # Navigate to tabroom.com
                driver.get(config.TABROOM_URL)
                
                # Find and click logout link if available
                logout_link = self._wait_for_element(
                    driver,
                    "//a[contains(@href, 'logout.mhtml') or @id='tabroom_logout']",
                    By.XPATH,
                    timeout=5
                )
                
                if logout_link:
                    logout_link.click()
                    
                    # Wait for logout to complete
                    self._wait_for_element(
                        driver,
                        "//a[contains(@href, 'login.mhtml') or contains(text(), 'Log In')]",
                        By.XPATH,
                        timeout=10
                    )
            
            # Clear cookies regardless
            self.cookie_manager.clear_cookies()
            self._login_verified = False
            logger.info("Successfully logged out and cleared session data")
            return True
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            self._login_verified = False
            return False
        finally:
            if driver:
                self.driver_pool.release_driver()

    def get_driver(self):
        """
        Get an authenticated WebDriver instance
        
        Returns:
            WebDriver: Authenticated WebDriver instance or None if authentication failed
        """
        try:
            # Ensure we're logged in
            if not self.ensure_login():
                logger.error("Failed to ensure login before getting driver")
                return None
                
            # Get a new driver, reusing existing ones when possible
            driver = self.driver_pool.get_driver(reuse=True)
            if not driver:
                logger.error("Failed to get driver from pool")
                return None
                
            # Load cookies to authenticate - don't navigate to index page first
            if not self.cookie_manager.load_cookies(driver, config.TABROOM_URL):
                logger.warning("Failed to load cookies to driver")
                self.driver_pool.release_driver()
                return None
                
            # Driver is authenticated with cookies, so we can skip verification
            # unless we want to be extra cautious
            logger.info("Successfully provided authenticated driver")
            return driver
            
        except Exception as e:
            logger.error(f"Error getting authenticated driver: {e}")
            if 'driver' in locals() and driver:
                self.driver_pool.release_driver()
            return None
            
    def get_authenticated_driver(self):
        """
        Alias for get_driver() to maintain compatibility with code that expects this method name
        
        Returns:
            WebDriver: Authenticated WebDriver instance or None if authentication failed
        """
        logger.debug("get_authenticated_driver called - using get_driver as alias")
        return self.get_driver()
    
    def release_driver(self, driver=None):
        """
        Release a driver back to the pool
        
        Args:
            driver: WebDriver instance to release (optional - if None, uses thread-specific driver)
        """
        if driver:
            # Save cookies before releasing
            try:
                self.cookie_manager.save_cookies(driver)
            except Exception as e:
                logger.warning(f"Failed to save cookies when releasing driver: {e}")
        
        self.driver_pool.release_driver()
    
    def _wait_for_element(self, driver, selector, by=By.CSS_SELECTOR, timeout=10, 
                          condition=EC.presence_of_element_located):
        """
        Wait for an element to be present/visible/clickable
        
        Args:
            driver: WebDriver instance
            selector: Element selector
            by: Selector type (By.ID, By.XPATH, etc.)
            timeout: Maximum wait time in seconds
            condition: Expected condition to wait for
            
        Returns:
            WebElement if found, None otherwise
        """
        try:
            element = WebDriverWait(driver, timeout).until(
                condition((by, selector))
            )
            return element
        except TimeoutException:
            logger.warning(f"Timeout waiting for element: {selector}")
            return None
        except Exception as e:
            logger.error(f"Error waiting for element {selector}: {e}")
            return None
    
    def _verify_login(self, driver, username=None):
        """
        Verify if the current session is logged in
        
        Args:
            driver: WebDriver instance
            username: Optional username to verify
            
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            # Log current URL and page title
            logger.info(f"Verifying login - URL: {driver.current_url} - Title: {driver.title}")
            
            # Take a screenshot for debugging if enabled
            self._take_debug_screenshot(driver, "verify_login")
            
            # Check login status via JavaScript for more reliable cross-browser behavior
            login_indicators = driver.execute_script("""
                // Common indicators of being logged in
                var indicators = {
                    // Check for logout link
                    logoutLink: document.querySelector('a[href*="logout.mhtml"]') !== null,
                    
                    // Check for tabroom_logout element
                    logoutElement: document.getElementById('tabroom_logout') !== null,
                    
                    // Check for account link
                    accountLink: document.querySelector('a[href*="account.mhtml"]') !== null,
                    
                    // Check for dashboard link
                    dashboardLink: document.querySelector('a[href*="dashboard"]') !== null,
                    
                    // Check for URL indicators
                    authenticatedUrl: window.location.href.includes('/user/home') || 
                                     window.location.href.includes('/dashboard')
                };
                
                // Check if username verification element exists
                if (arguments[0]) {
                    var userElement = document.getElementById('tabroom_edlee');
                    if (userElement) {
                        indicators.usernameVerified = userElement.textContent.toLowerCase().includes(arguments[0].toLowerCase());
                    }
                }
                
                return indicators;
            """, username)
            
            # Log the found indicators
            for indicator, found in login_indicators.items():
                if found:
                    logger.info(f"Found login indicator: {indicator}")
            
            # Check if any login indicator was found
            if any(login_indicators.values()):
                # If username verification was requested and failed, log a warning
                if username and not login_indicators.get('usernameVerified', True):
                    logger.warning(f"Username verification failed for {username}")
                
                # But still consider it a success if any indicator was found
                return True
            
            # No login indicators found
            logger.warning("No login indicators found")
            return False
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error verifying login status: {e}\n{error_trace}")
            return False
    
    def _take_debug_screenshot(self, driver, prefix):
        """
        Take a debug screenshot if debug mode is enabled
        
        Args:
            driver: WebDriver instance
            prefix: Prefix for the screenshot filename
        """
        if not config.DEBUG:
            return
            
        try:
            screenshots_dir = os.path.join(config.DATA_DIR, "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            driver.save_screenshot(filepath)
            logger.debug(f"Saved debug screenshot: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to take debug screenshot: {e}")