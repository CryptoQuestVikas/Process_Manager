# process_manager/utils.py

import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logging():
    """
    Configures a rotating file logger for the application.
    """
    logger = logging.getLogger("ProcessManager")
    logger.setLevel(logging.INFO)

    # Prevent adding multiple handlers if this function is called more than once
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a rotating file handler
    file_handler = RotatingFileHandler(
        "proc_manager.log", maxBytes=5 * 1024 * 1024, backupCount=2
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Create a console handler for critical errors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

# Create a logger instance to be used across the application
log = setup_logging()