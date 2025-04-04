# test_driver.py
import os
import sys
import logging
from pathlib import Path
import subprocess
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("driver_test")

def get_chrome_version():
    """Get Chrome/Chromium version on macOS"""
    try:
        # For macOS
        cmd = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=10)
        output = stdout.decode('utf-8').strip()
        
        import re
        match = re.search(r'Chrome\s+(\d+\.\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)
        
        # Try Chromium
        cmd = ['/Applications/Chromium.app/Contents/MacOS/Chromium', '--version']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=10)
        output = stdout.decode('utf-8').strip()
        
        match = re.search(r'Chromium\s+(\d+\.\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)
    except Exception as e:
        logger.error(f"Error detecting Chrome version: {e}")
    
    return "Unknown"

def try_create_driver_with_version(version=None, chrome_type=None):
    """Try to create a driver with specific version and type"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        if version:
            logger.info(f"Trying with ChromeDriver version {version}")
            driver_path = ChromeDriverManager(version=version, chrome_type=chrome_type).install()
        else:
            logger.info(f"Trying with latest ChromeDriver{'for Chromium' if chrome_type else ''}")
            driver_path = ChromeDriverManager(chrome_type=chrome_type).install()
        
        logger.info(f"Using driver at: {driver_path}")
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Test if it works
        driver.get("about:blank")
        driver_version = driver.capabilities.get('browserVersion', 'unknown')
        chrome_version = driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'unknown')
        logger.info(f"SUCCESS: Driver working! Browser: {driver_version}, Driver: {chrome_version}")
        
        driver.quit()
        return True, driver_path
    except Exception as e:
        logger.error(f"FAILED: {e}")
        return False, None

def find_working_driver():
    """Try different approaches to find a working driver"""
    chrome_version = get_chrome_version()
    logger.info(f"Detected Chrome version: {chrome_version}")
    
    # List of known working older versions to try
    versions_to_try = ["114.0.5735.90", "113.0.5672.63", "112.0.5615.49", "111.0.5563.64", "110.0.5481.77"]
    
    # First try the automatic version detection
    logger.info("Trying latest driver...")
    success, path = try_create_driver_with_version()
    if success:
        return path
    
    # Try with specific older versions
    for version in versions_to_try:
        success, path = try_create_driver_with_version(version)
        if success:
            return path
    
    # Try with Chromium
    logger.info("Trying with Chromium...")
    success, path = try_create_driver_with_version(chrome_type=ChromeType.CHROMIUM)
    if success:
        return path
    
    # Try downloading a specific driver manually
    logger.info("All automated attempts failed. Now trying manual download...")
    try:
        # Known fixed URL for a reasonably recent driver
        url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_mac64.zip"
        if "arm64" in subprocess.check_output(["uname", "-m"]).decode():
            url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_mac_arm64.zip"
        
        import urllib.request
        import zipfile
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = os.path.join(tmp_dir, "chromedriver.zip")
            driver_path = os.path.join(tmp_dir, "chromedriver")
            
            logger.info(f"Downloading from {url}...")
            urllib.request.urlretrieve(url, zip_path)
            
            logger.info("Extracting driver...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # Make it executable
            os.chmod(driver_path, 0o755)
            
            # Test it
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get("about:blank")
            logger.info("Manual download successful!")
            driver.quit()
            
            # Create a permanent location for the driver
            user_driver_dir = os.path.expanduser("~/chromedriver")
            os.makedirs(user_driver_dir, exist_ok=True)
            permanent_path = os.path.join(user_driver_dir, "chromedriver")
            import shutil
            shutil.copy2(driver_path, permanent_path)
            os.chmod(permanent_path, 0o755)
            
            logger.info(f"Driver copied to: {permanent_path}")
            return permanent_path
    except Exception as e:
        logger.error(f"Manual download failed: {e}")
    
    logger.error("All attempts to find a working driver failed!")
    return None

if __name__ == "__main__":
    logger.info("Starting ChromeDriver compatibility test")
    driver_path = find_working_driver()
    
    if driver_path:
        logger.info(f"SUCCESS! Found working driver at: {driver_path}")
        print("\n" + "="*80)
        print(f"WORKING DRIVER PATH: {driver_path}")
        print("="*80 + "\n")
        print("Add this to your config.py file:")
        print(f"CHROMIUM_DRIVER_PATH = \"{driver_path}\"")
    else:
        logger.error("Failed to find a working driver.")