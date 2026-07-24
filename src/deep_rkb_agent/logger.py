import logging
import os
import sys

def get_logger(name="DROA"):
    """
    Returns a configured logger that outputs to both a file (droa.log) and stdout.
    """
    logger = logging.getLogger(name)
    
    # Only configure if it hasn't been configured yet
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Log file in the repository root
        log_file = "droa.log"
            
            
        file_handler = logging.FileHandler(log_file)
        stream_handler = logging.StreamHandler(sys.stdout)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
    return logger
