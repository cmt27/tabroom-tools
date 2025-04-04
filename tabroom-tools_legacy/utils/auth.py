
import os
import json
from pathlib import Path
import streamlit as st

COOKIE_PATH = Path("/data/cookies.json")

def ensure_cookie_file():
    try:
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not COOKIE_PATH.exists():
            with open(COOKIE_PATH, 'w') as f:
                json.dump([], f)
    except Exception as e:
        print(f"Failed to ensure cookie file: {e}")

def load_cookies():
    ensure_cookie_file()
    try:
        with open(COOKIE_PATH, 'r') as f:
            cookies = json.load(f)
            if isinstance(cookies, list):
                return cookies
    except Exception as e:
        print(f"Failed to load cookies: {e}")
    return []

def save_cookies(cookies):
    try:
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_PATH, 'w') as f:
            json.dump(cookies, f, indent=2)
    except Exception as e:
        print(f"Failed to save cookies: {e}")

def is_logged_in_from_cookies(driver):
    try:
        driver.get("https://www.tabroom.com/user/chapter")
        return "/user/login" not in driver.current_url
    except Exception as e:
        print(f"Error checking login status from cookies: {e}")
        return False

def login_if_required(driver):
    if "/user/login" not in driver.current_url:
        return

    st.warning("Login required to access Tabroom. Please enter your credentials.")
    email = st.text_input("Tabroom Email")
    password = st.text_input("Tabroom Password", type="password")
    login_attempted = st.button("Log In")

    if login_attempted and email and password:
        try:
            driver.find_element("name", "email").send_keys(email)
            driver.find_element("name", "password").send_keys(password)
            driver.find_element("css selector", 'button[type="submit"]').click()
            driver.implicitly_wait(5)
            cookies = driver.get_cookies()
            save_cookies(cookies)
            st.success("Login successful and cookies saved.")
        except Exception as e:
            st.error(f"Login failed: {e}")

def apply_cookies_to_context(driver, cookies):
    """Attach cookies to the browser context."""
    if not cookies:
        return
    try:
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Failed to apply individual cookie: {e}")
    except Exception as e:
        print(f"Failed to apply cookies: {e}")
