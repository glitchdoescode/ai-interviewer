"""
Logging utilities for the AI Interviewer platform.

This module provides logging setup and configuration for the application.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/ai_interviewer.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> None:
    """
    Configure application logging with console and file handlers.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to the log file
        max_file_size: Maximum size of log file before rotating (bytes)
        backup_count: Number of backup log files to keep
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers (in case this function is called multiple times)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create and configure handlers
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # File handler (with rotation)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    file_handler.setLevel(numeric_level)
    file_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # Add handlers to the root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Log that logging has been set up
    logging.info("Logging configured with level: %s", log_level) 