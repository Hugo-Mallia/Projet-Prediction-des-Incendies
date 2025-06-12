from fastapi import FastAPI
import logging
import os

def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    log_dir = os.path.abspath(log_dir)
    os.makedirs(log_dir, exist_ok=True)  # Crée le dossier logs si besoin

    log_file = os.path.join(log_dir, 'app.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    return logger

logger = setup_logging()