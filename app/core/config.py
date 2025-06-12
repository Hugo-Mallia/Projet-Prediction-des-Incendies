from dotenv import load_dotenv
import os

class Config:
    """Configuration settings for the application."""
    
    def __init__(self):
        load_dotenv()  # Load environment variables from a .env file
        self.DEBUG = os.getenv("DEBUG", "False") == "True"
        self.API_VERSION = os.getenv("API_VERSION", "v1")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")

config = Config()