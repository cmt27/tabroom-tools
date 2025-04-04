# app/config.py
import os
from pathlib import Path
import secrets


# Base directory settings
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_DIR = os.path.join(BASE_DIR, "cookies")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)

# Encryption key for credentials
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", secrets.token_bytes(16))

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'tabroom.db')}")

# Selenium settings
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
CHROMIUM_BINARY_PATH = os.getenv("CHROMIUM_BINARY_PATH", "/usr/bin/chromium")
HEADLESS = os.getenv("HEADLESS", "True").lower() in ("true", "1", "t")

# Web UI settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Tabroom settings
TABROOM_URL = "https://www.tabroom.com"
LOGIN_URL = f"{TABROOM_URL}/user/login/login.mhtml"

# Authentication settings
LOGIN_TIMEOUT = int(os.getenv("LOGIN_TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))