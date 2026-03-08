
import logging
import os
from datetime import datetime

def setup_logger(name: str = "med_system", log_dir: str = "logs") -> logging.Logger:
    """
    Configure and return a logger instance that logs to both console and file.
    
    Args:
        name: Name of the logger
        log_dir: Directory to save log files
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger already has handlers, assume it's configured and return it
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Create logs directory if it doesn't exist
    # Using absolute path relative to project root if possible, or just local
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"med_system_{timestamp}.log")
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create a default instance for easy import
logger = setup_logger()
