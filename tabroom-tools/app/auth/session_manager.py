# app/auth/session_manager.py
import os
import pickle
import base64
import logging
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException

from app import config
from app.auth.driver_manager import WebDriverPool

logger = logging.getLogger(__name__)

class TabroomSession:
    """Enhanced authentication and session management for tabroom.com"""
    def __init__(self, cookie_dir=None, encryption_key=None):
        """
        Initialize the session manager
        
        Args:
            cookie_dir: Directory to store cookies (defaults to config value)
            encryption_key: Key to encrypt credentials (defaults to config value)
        """
        self.cookie_dir = cookie_dir or config.COOKIE_DIR
        self.encryption_key = encryption_key or config.ENCRYPTION_KEY or b'TabroomDefaultKey'
        os.makedirs(self.cookie_dir, exist_ok=True)
        
        self.cookie_file = os.path.join(self.cookie_dir, "tabroom_cookies.pkl")
        self.credentials_file = os.path.join(self.cookie_dir, "credentials.enc")
        self.driver_pool = WebDriverPool()
        
    def _encrypt_data(self, data):
        """Encrypt data using AES"""
        cipher = AES.new(self.encryption_key, AES.MODE_CBC)
        padded_data = pad(data.encode(), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        iv = cipher.iv
        return base64.b64encode(iv + encrypted_data).decode()
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt data using AES"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            iv = encrypted_bytes[:AES.block_size]
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv=iv)
            decrypted_data = unpad(cipher.decrypt(encrypted_bytes[AES.block_size:]), AES.block_size)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            return None
    
    def save_credentials(self, username, password):
        """Save tabroom.com credentials securely using encryption"""
        try:
            credentials = {
                "username": username,
                "password": password
            }
            credentials_json = str(credentials)
            encrypted_data = self._encrypt_data(credentials_json)
            
            with open(self.credentials_file, "w") as f:
                f.write(encrypted_data)
            logger.info("Credentials saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            return False
    
    def load_credentials(self):
        """Load stored tabroom.com credentials if available"""
        if not os.path.exists(self.credentials_file):
            return None
        
        try:
            with open(self.credentials_file, "r") as f:
                encrypted_data = f.read()
            
            decrypted_json = self._decrypt_data(encrypted_data)
            if decrypted_json:
                # Convert string representation of dict back to dict
                credentials = eval(decrypted_json)
                return credentials
            return None
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return None
    
    def wait_for_element(self, driver, selector, by=By.CSS_SELECTOR, timeout=10, condition=EC.presence_of_element_located):
        """
        Wait for an element to appear on the page
        
        Args:
            driver: WebDriver instance
            selector: Element selector (CSS selector by default)
            by: Type of selector (defaults to CSS_SELECTOR)
            timeout: Maximum wait time in seconds
            condition: Expected condition to wait for
            
        Returns:
            The element if found, None otherwise
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
    
    def load_cookies(self, driver):
        """Load cookies into the provided WebDriver if available"""
        if not os.path.exists(self.cookie_file):
            logger.info("No stored cookies found")
            return False
        
        try:
            # First navigate to the domain (required before adding cookies)
            driver.get(config.TABROOM_URL)
            
            # Wait for the page to load
            self.wait_for_element(driver, "body")
            
            # Load cookies from file
            with open(self.cookie_file, "rb") as f:
                cookies = pickle.load(f)
                
            # Add cookies to the driver
            for cookie in cookies:
                try:
                    # Some browsers/drivers have issues with expiry dates
                    if 'expiry' in cookie:
                        del cookie['expiry']
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"Error adding cookie: {e}")
            
            # Refresh to apply cookies
            driver.refresh()
            
            logger.info("Cookies loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False
    
    def save_cookies(self, driver):
        """Save cookies from the current WebDriver session"""
        try:
            cookies = driver.get_cookies()
            with open(self.cookie_file, "wb") as f:
                pickle.dump(cookies, f)
            logger.info("Cookies saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False
    
    def login(self, username=None, password=None, save_credentials=True, max_retries=3):
        """
        Login to tabroom.com with retry mechanism
        
        Args:
            username: Tabroom username
            password: Tabroom password
            save_credentials: Whether to save credentials for future use
            max_retries: Maximum number of login attempts
            
        Returns:
            bool: True if login was successful, False otherwise
        """
        # If no credentials provided, try to load stored credentials
        if (username is None or password is None):
            stored_credentials = self.load_credentials()
            if stored_credentials:
                username = stored_credentials.get("username")
                password = stored_credentials.get("password")
            else:
                logger.error("No credentials provided and no stored credentials found")
                return False
        
        if save_credentials:
            self.save_credentials(username, password)
        
        driver = None
        attempts = 0
        
        while attempts < max_retries:
            attempts += 1
            try:
                driver = self.driver_pool.get_driver()
                
                # Navigate to login page
                driver.get(config.LOGIN_URL)
                
                # Wait for the login form to load completely
                username_field = self.wait_for_element(
                    driver, 
                    "login_email", 
                    By.ID, 
                    timeout=10, 
                    condition=EC.presence_of_element_located
                )
                
                if not username_field:
                    logger.error("Login form not found or not loaded completely")
                    continue  # Try again
                
                password_field = driver.find_element(By.ID, "login_password")
                
                # Clear fields and enter credentials
                username_field.clear()
                password_field.clear()
                username_field.send_keys(username)
                password_field.send_keys(password)
                
                # Submit form
                login_button = self.wait_for_element(
                    driver,
                    "//input[@type='submit' and @value=' Log Into Your Account ']",
                    By.XPATH,
                    timeout=5
                )
                
                if not login_button:
                    logger.error("Login button not found")
                    continue  # Try again
                    
                login_button.click()
                
                # Wait for login to complete by checking for logout link
                success = self.wait_for_element(
                    driver,
                    "//a[contains(text(), 'Log Out') or @id='tabroom_logout']",
                    By.XPATH,
                    timeout=10,
                    condition=EC.presence_of_element_located
                )
                
                if success:
                    # Additional verification - check if user's email is displayed
                    email_element = self.wait_for_element(
                        driver,
                        "tabroom_edlee",
                        By.ID,
                        timeout=5
                    )
                    
                    if email_element and username.lower() in email_element.text.lower():
                        # Save cookies for future use
                        self.save_cookies(driver)
                        logger.info(f"Login successful for {username}")
                        return True
                
                # Check if there's an error message
                error_elements = driver.find_elements(By.CLASS_NAME, "warning")
                if error_elements:
                    error_text = error_elements[0].text
                    logger.error(f"Login failed: {error_text}")
                else:
                    logger.error(f"Login failed: No success indicator found (attempt {attempts}/{max_retries})")
                
                # Short delay before retry
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Login error: {e}")
                time.sleep(2)  # Wait before retry
                
            finally:
                if driver and attempts >= max_retries:
                    self.driver_pool.release_driver()
        
        logger.error(f"Login failed after {max_retries} attempts")
        return False
    
    def is_logged_in(self):
        """Check if the current session is logged in to tabroom.com"""
        driver = None
        try:
            driver = self.driver_pool.get_driver()
            
            # Try to load cookies
            if not self.load_cookies(driver):
                return False
            
            # Navigate to a page that requires login
            driver.get(f"{config.TABROOM_URL}/user/home.mhtml")
            
            # Check for logout link or other logged-in indicators
            logout_link = self.wait_for_element(
                driver,
                "//a[contains(@href, 'logout.mhtml') or @id='tabroom_logout']",
                By.XPATH,
                timeout=5
            )
            
            email_element = self.wait_for_element(
                driver,
                "tabroom_edlee",
                By.ID,
                timeout=5
            )
            
            if logout_link and email_element:
                logger.info("Session is logged in")
                return True
            
            logger.info("Session is not logged in")
            return False
                
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
            
        finally:
            if driver:
                self.driver_pool.release_driver()
    
    def ensure_login(self, username=None, password=None):
        """Ensure the session is logged in, attempting login if necessary"""
        # First check if already logged in
        if self.is_logged_in():
            return True
        
        # If not logged in, try to login
        logger.info("Not logged in, attempting login")
        return self.login(username, password)
    
    def logout(self):
        """Log out from tabroom.com and clear session data"""
        driver = None
        try:
            driver = self.driver_pool.get_driver()
            
            # Load cookies and check if logged in
            if not self.load_cookies(driver):
                # If no cookies, we're effectively logged out
                return True
            
            # Navigate to tabroom.com
            driver.get(config.TABROOM_URL)
            
            # Find and click logout link if available
            logout_link = self.wait_for_element(
                driver,
                "//a[contains(@href, 'logout.mhtml') or @id='tabroom_logout']",
                By.XPATH,
                timeout=5
            )
            
            if logout_link:
                logout_link.click()
                
                # Wait for logout to complete
                self.wait_for_element(
                    driver,
                    "//a[contains(@href, 'login.mhtml') or contains(text(), 'Log In')]",
                    By.XPATH,
                    timeout=10
                )
            
            # Remove cookie file
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
            
            logger.info("Successfully logged out and cleared session data")
            return True
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False
            
        finally:
            if driver:
                self.driver_pool.release_driver()