"""
Logging configuration for the application.

Provides structured logging with configurable levels and formats.
"""

import logging
import sys
from typing import Optional

from .config import get_settings


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return the application logger.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom log format string
    
    Returns:
        logging.Logger: Configured logger instance
    """
    settings = get_settings()
    
    # Determine log level
    if level is None:
        level = "DEBUG" if settings.debug else "INFO"
    
    # Default format string
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        )
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create application logger
    logger = logging.getLogger("metadata_inventory")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    
    return logger


# Global logger instance
logger = setup_logging()
