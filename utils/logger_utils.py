import logging
import os

def setup_logger(name: str, log_file: str, level=logging.DEBUG, log_dir="."):
    """Crée un logger avec un FileHandler."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        fh = logging.FileHandler(log_path)
        fh.setLevel(level)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger

#from logger_utils import setup_logger

#eclc_logger = setup_logger("hotel.eclc", "eclc_pricing.log")
#booking_logger = setup_logger("hotel.booking", "booking.log")
