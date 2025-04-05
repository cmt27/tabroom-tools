#!/usr/bin/env python3
"""
Patch for the JudgeSearchScraper class to handle method name inconsistencies.

This script monkey patches the TabroomSession class to add a get_authenticated_driver method
that simply calls the existing get_driver method. This fixes the issue where the JudgeSearchScraper
is trying to call get_authenticated_driver() but the method is actually named get_driver().
"""

import sys
import os
from pathlib import Path

# Add the tabroom-tools directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent / "tabroom-tools"))

# Import the necessary components
from app.auth.session_manager import TabroomSession

# Monkey patch the TabroomSession class to add a get_authenticated_driver method
def get_authenticated_driver(self):
    """
    Alias for get_driver() to handle method name inconsistencies.
    
    Returns:
        WebDriver: Authenticated WebDriver instance or None if authentication failed
    """
    return self.get_driver()

# Add the method to the TabroomSession class
TabroomSession.get_authenticated_driver = get_authenticated_driver

print("Successfully patched TabroomSession class with get_authenticated_driver method")