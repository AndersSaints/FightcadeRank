"""
Fightcade API client implementation.
"""
from typing import Dict, Tuple, Optional, Any
import cloudscraper
import time
from .config import settings
from .cache import PlayerCache
from .logger import setup_logging

logger = setup_logging()

class FightcadeAPI:
    def __init__(self):
        """Initialize the API client with cloudscraper and cache."""
        self.scraper = self._init_scraper()
        self.cache = PlayerCache()
        self._init_session()
    
    def _init_scraper(self) -> cloudscraper.CloudScraper:
        """Initialize cloudscraper with robust settings."""
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            },
            debug=settings.DEBUG
        )
        
        # Add headers
        headers = settings.BROWSER_HEADERS.copy()
        headers['User-Agent'] = settings.USER_AGENT
        scraper.headers.update(headers)
        
        return scraper
    
    def _init_session(self) -> None:
        """Initialize session by visiting the main page."""
        try:
            response = self.scraper.get('https://www.fightcade.com/')
            response.raise_for_status()
            logger.info("Session initialized successfully", 
                       status_code=response.status_code)
            time.sleep(2)  # Give time for any JS to execute
        except Exception as e:
            logger.error("Failed to initialize session", 
                        error=str(e))
            raise
    
    def _make_request(self, data: Dict, max_retries: int = 3) -> Dict:
        """Make an API request with retry logic."""
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                response = self.scraper.post(settings.BASE_URL, json=data)
                response.raise_for_status()
                return response.json()
            
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.warning("Request retry attempt failed", 
                             attempt=retry_count, 
                             error=str(e))
                time.sleep(settings.ERROR_DELAY)
        
        logger.error("Request failed after maximum retries", 
                    max_retries=max_retries, 
                    final_error=str(last_error))
        raise last_error
    
    def get_user(self, username: str) -> Dict:
        """Get user information."""
        data = {
            "req": "getuser",
            "username": username
        }
        
        logger.info("Fetching user information", username=username)
        return self._make_request(data)
    
    def search_rankings(self, offset: int = 0, limit: int = None) -> Dict:
        """Search rankings with pagination."""
        if limit is None:
            limit = settings.BATCH_SIZE
            
        data = {
            "req": "searchrankings",
            "offset": offset,
            "limit": limit,
            "gameid": settings.GAME_ID,
            "byElo": True,
            "recent": True
        }
        
        logger.info("Searching rankings", 
                   offset=offset, 
                   limit=limit)
        return self._make_request(data)
    
    def search_player(self, player_name: str, 
                     progress_callback: Optional[callable] = None) -> Tuple[Optional[Dict], int]:
        """Search for a player using cache and API calls."""
        if not player_name:
            raise ValueError("Player name cannot be empty")
        
        def update_progress(message: str) -> None:
            """Update progress with logging."""
            if progress_callback:
                progress_callback(message)
            logger.info("Search progress update", message=message)
        
        try:
            # First check if player exists
            update_progress("Checking if player exists...")
            user_data = self.get_user(player_name)
            
            if user_data.get('res') != 'OK':
                update_progress("Player not found")
                return None, 0
            
            update_progress("Player found, searching for ranking...")
            
            # Check cache
            cached_player, start_offset = self.cache.search_player(player_name)
            if cached_player:
                update_progress(f"Found player in cache at rank {start_offset + 1}")
                return cached_player, start_offset
            
            # Start searching from last cached position
            offset = start_offset
            while offset < settings.MAX_SEARCH_OFFSET:
                update_progress("Searching...")
                
                try:
                    response = self.search_rankings(offset)
                    if response.get('res') != 'OK':
                        if 'rate' in str(response.get('error', '')).lower():
                            update_progress("Rate limited, waiting...")
                            time.sleep(settings.RATE_LIMIT_DELAY)
                            continue
                        break
                    
                    players = response.get('results', {}).get('results', [])
                    if not players:
                        break
                    
                    # Add to cache
                    self.cache.add_players(players, offset)
                    
                    # Check this batch
                    for i, player in enumerate(players):
                        if player.get('name', '').lower() == player_name.lower():
                            rank = offset + i + 1
                            update_progress(f"Found player at rank {rank}")
                            return player, offset + i
                    
                    offset += settings.BATCH_SIZE
                    time.sleep(settings.REQUEST_DELAY)
                    
                except Exception as e:
                    update_progress(f"Error during search: {str(e)}")
                    time.sleep(settings.ERROR_DELAY)
                    continue
            
            update_progress("Player not found in rankings")
            return None, 0
            
        except Exception as e:
            logger.error("Search failed", 
                        player=player_name, 
                        error=str(e))
            raise
