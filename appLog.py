import logging
import os
import logging.config
from logging.handlers import SocketHandler
import pythonjsonlogger.jsonlogger
from src import logcolor
import socket # Added for socket.error

# Ensure the logs directory exists
os.makedirs('src/logs', exist_ok=True)

try:
    logging.config.fileConfig("src/logging.ini", disable_existing_loggers=True)
except FileNotFoundError:
    logging.basicConfig(level=logging.DEBUG) # Basic config if file not found
    logging.error("logging.ini not found. Basic logging configured.")
except Exception as e:
    logging.basicConfig(level=logging.DEBUG)
    logging.error(f"Error loading logging configuration: {e}. Basic logging configured.")

# Get the logger named 'appLog' as configured in logging.ini
log = logging.getLogger('appLog')

# The SocketHandler is configured in logging.ini, so manual addition is not needed here.
# The try-except block for socket handler connection errors during addHandler is also not needed here
# as fileConfig handles handler setup. Errors during logging via SocketHandler will be handled by the logging system.
