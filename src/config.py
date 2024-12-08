"""
Configuration settings for the FightcadeRank application.
"""
from pydantic_settings import BaseSettings
from typing import Dict, Any, Tuple
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
    REQUEST_DELAY: int = 1  # seconds
    
    # UI Settings
    WINDOW_SIZE: Tuple[int, int] = (1200, 800)
    MIN_WINDOW_SIZE: Tuple[int, int] = (1000, 600)
    PAGE_SIZE: int = 15
    TOOLTIP_DELAY: int = 500  # milliseconds
    
    # Table Column Widths
    COLUMN_WIDTHS: Dict[str, int] = {
        "rank": 80,
        "name": 200,
        "country": 100,
        "matches": 100,
        "wins": 80,
        "losses": 80,
        "winrate": 100,
        "time": 100
    }
    
    # Theme Colors
    COLORS: Dict[str, Dict[str, str]] = {
        "header": {
            "bg": "#2b2b2b",
            "fg": "#ffffff"
        },
        "row": {
            "bg": "#1e1e1e",
            "alt_bg": "#252525",
            "fg": "#e0e0e0"
        },
        "highlight": {
            "bg": "#3a3a3a",
            "fg": "#ffffff"
        }
    }
    
    # Debug Settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")
    
    # Browser Headers
    BROWSER_HEADERS: Dict[str, str] = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        
        # Create necessary directories
        self.CACHE_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)

# Create global settings instance
settings = Settings()
