import logging
import sys
from config.config import CONFIG

# Get log level from configuration, default to DEBUG if not set
log_level = CONFIG.get("LOG_LEVEL", "DEBUG").upper()

# Create a logger for the application with the new name "tabroom-tools"
logger = logging.getLogger("tabroom-tools")
logger.setLevel(getattr(logging, log_level, logging.DEBUG))

# Create handler to output logs to stdout (container logs)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(getattr(logging, log_level, logging.DEBUG))

# Create formatter and add it to the handler
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Prevent log duplication if other handlers are present
logger.propagate = False