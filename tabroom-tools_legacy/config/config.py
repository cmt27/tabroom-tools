import json
import os

CONFIG_FILE = "config/config.json"

def load_config():
    """
    Load configuration parameters from the config.json file.
    Returns:
        dict: Configuration parameters.
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    else:
        config = {}
    return config

# Global configuration object
CONFIG = load_config()