"""Application settings and configuration."""
from pathlib import Path

# API Settings
BASE_URL = "https://www.fightcade.com"
API_ENDPOINTS = {
    "USER": "/api/v1/user",  # Changed to v1 endpoint
    "REPLAYS": "/api/v1/replays",  # Changed to v1 endpoint
    "RANKING": "/api/v1/ranking"  # Changed to v1 endpoint
}
GAME_ID = "sfiii3n"  # Street Fighter III: 3rd Strike
REPLAYS_PER_PAGE = 50
MAX_REPLAYS = 200

# Browser Settings
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "https://www.fightcade.com",
    "Referer": "https://www.fightcade.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

# Cache Settings
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_EXPIRY = 3600  # 1 hour in seconds
MAX_CACHE_SIZE = 1000

# Debug Settings
DEBUG = True  # Enable debug mode for better error messages

# UI Settings
WINDOW_TITLE = "FightcadeRank - SF3: 3rd Strike"
WINDOW_SIZE = (800, 600)
MIN_WINDOW_SIZE = (600, 400)
PADDING = 10
BUTTON_WIDTH = 15
ENTRY_WIDTH = 30

# Colors
BG_COLOR = "#2b2b2b"
FG_COLOR = "#ffffff"
BUTTON_COLOR = "#1f538d"
ERROR_COLOR = "#ff5555"
SUCCESS_COLOR = "#50fa7b"
HIGHLIGHT_COLOR = "#44475a"

# Status Messages
STATUS_SEARCHING = "Searching for player..."
STATUS_FETCHING = "Fetching replays..."
STATUS_CALCULATING = "Calculating stats..."
STATUS_COMPLETE = "Stats calculation complete!"
STATUS_ERROR = "An error occurred: {}"
STATUS_NOT_FOUND = "Player not found"

# Tooltip Settings
TOOLTIP_DELAY = 500  # milliseconds
TOOLTIP_BG = "#282a36"
TOOLTIP_FG = "#f8f8f2"

# Replay Settings
REPLAY_FETCH_DELAY = 0.5  # seconds between API calls
MAX_RETRIES = 3  # maximum number of retry attempts for failed API calls
RETRY_DELAY = 1.0  # seconds to wait between retries
