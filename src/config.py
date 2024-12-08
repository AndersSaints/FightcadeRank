"""
Configuration settings for the FightcadeRank application.
"""
from pydantic import BaseSettings
from typing import Dict, Any
import os
from pathlib import Path

class Settings(BaseSettings):
    # API Settings
    BASE_URL: str = "https://www.fightcade.com/api/"
    GAME_ID: str = "kof2002"
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    
    # Cache Settings
    CACHE_DURATION: int = 600  # 10 minutes in seconds
    CACHE_DIR: Path = Path("cache")
    
    # Search Settings
    BATCH_SIZE: int = 100
    MAX_SEARCH_OFFSET: int = 5000
    
    # Rate Limiting
    RATE_LIMIT_DELAY: int = 30  # seconds
    ERROR_DELAY: int = 10  # seconds
    REQUEST_DELAY: int = 3  # seconds
    
    # UI Settings
    WINDOW_SIZE: tuple = (1200, 800)
    MIN_WINDOW_SIZE: tuple = (1000, 600)
    PAGE_SIZE: int = 15
    
    # Debug Settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")
    
    # Browser Headers
    BROWSER_HEADERS: Dict[str, str] = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.fightcade.com",
        "Referer": "https://www.fightcade.com/",
    }
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        
        # Create necessary directories
        self.CACHE_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)

# Create global settings instance
settings = Settings()
