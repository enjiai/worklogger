import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """
    Centralized settings class that loads configuration from environment variables.
    """
    # Database settings
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "work_logger")
    DB_SCHEMA: str = os.getenv("DB_SCHEMA", "public")
    
    # Database URL
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Test database settings
    TEST_SCHEMA: str = "test_schema"
    
    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_ORGANIZATION: str = os.getenv("OPENAI_ORGANIZATION", "")
    OPENAI_PROJECT: str = os.getenv("OPENAI_PROJECT", "")
    
    # Jira settings
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    
    # Telegram settings
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # Worklogger settings
    DIFF_CHECK_PERIOD_SECONDS: int = int(os.getenv("DIFF_CHECK_PERIOD_SECONDS", "60"))
    
    def __init__(self):
        # Validate required settings
        self._validate_settings()
        
    def _validate_settings(self):
        """Validate that all required settings are present."""
        if not self.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not set in environment variables")
        
        if not self.TELEGRAM_TOKEN:
            logger.warning("TELEGRAM_TOKEN is not set in environment variables")
            
        if not self.JIRA_API_TOKEN:
            logger.warning("JIRA_API_TOKEN is not set in environment variables")


# Create a global settings instance
settings = Settings() 