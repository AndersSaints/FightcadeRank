"""
Fightcade API client implementation.
"""
from typing import Dict, Tuple, Optional, Any, List
import cloudscraper
import time
from .config import settings
from .cache import PlayerCache
from .logger import setup_logging

logger = setup_logging()

class FightcadeAPI:
    def __init__(self):
        """Initialize the API client with cloudscraper and cache."""
        self.cache = PlayerCache()
        self.scraper = None
        self._init_delayed = False
    
    def _ensure_initialized(self):
        """Ensure API is initialized before making requests."""
        if not self._init_delayed:
            self.scraper = self._init_scraper()
            self._init_session()
            self._init_delayed = True
    
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
        except Exception as e:
            logger.error("Failed to initialize session", 
                        error=str(e))
            raise
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None, max_retries: int = 3) -> Dict:
        """Make a request to the Fightcade API with retries."""
        self._ensure_initialized()  # Initialize only when needed
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                response = self.scraper.request(method, settings.BASE_URL + endpoint, json=data, params=params)
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
        return self._make_request("POST", "", data=data)
    
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
        return self._make_request("POST", "", data=data)
    
    def search_player(self, username: str, progress_callback=None) -> Tuple[Optional[Dict], int]:
        """Search for a player using cache and API calls with parallel processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        self._ensure_initialized()
        if not username:
            raise ValueError("Player name cannot be empty")
        
        def update_progress(message: str) -> None:
            """Update progress with logging."""
            if progress_callback:
                progress_callback(message)
            logger.info("Search progress update", message=message)
        
        try:
            # First check if player exists
            update_progress("Checking if player exists...")
            user_data = self.get_user(username)
            
            if user_data.get('res') != 'OK':
                update_progress("Player not found")
                return None, 0
            
            update_progress("Player found, searching for ranking...")
            
            # Check cache first
            cached_player, start_offset = self.cache.search_player(username)
            if cached_player:
                update_progress(f"Found player in cache at rank {start_offset + 1}")
                return cached_player, start_offset
            
            # Thread-safe variables
            found_player = None
            found_offset = None
            search_complete = threading.Event()
            
            def search_batch(start_offset: int, batch_number: int) -> Optional[Tuple[Dict, int]]:
                """Search a batch of players."""
                if search_complete.is_set():
                    return None
                    
                try:
                    current_page = (start_offset // settings.BATCH_SIZE) + 1
                    update_progress(f"Searching page {current_page}...")
                    
                    response = self.search_rankings(start_offset)
                    if response.get('res') != 'OK':
                        if 'rate' in str(response.get('error', '')).lower():
                            time.sleep(settings.RATE_LIMIT_DELAY)
                            return None
                        return None
                    
                    players = response.get('results', {}).get('results', [])
                    if not players:
                        return None
                    
                    # Add to cache
                    self.cache.add_players(players, start_offset)
                    
                    # Check this batch
                    for i, player in enumerate(players):
                        if search_complete.is_set():
                            return None
                        if player.get('name', '').lower() == username.lower():
                            return (player, start_offset + i)
                    
                    time.sleep(settings.REQUEST_DELAY)
                    return None
                    
                except Exception as e:
                    logger.error("Batch search failed", 
                               batch=batch_number, 
                               error=str(e))
                    return None
            
            # Calculate batches for parallel processing
            max_workers = 5  # Maximum concurrent requests
            batch_size = settings.BATCH_SIZE
            total_batches = settings.MAX_SEARCH_OFFSET // batch_size
            
            update_progress(f"Starting parallel search with {max_workers} workers...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all batches
                future_to_batch = {
                    executor.submit(search_batch, i * batch_size, i): i 
                    for i in range(total_batches)
                }
                
                try:
                    for future in as_completed(future_to_batch):
                        batch_num = future_to_batch[future]
                        try:
                            result = future.result()
                            if result:
                                player, offset = result
                                found_player = player
                                found_offset = offset
                                search_complete.set()
                                break
                        except Exception as e:
                            logger.error("Future failed", 
                                       batch=batch_num, 
                                       error=str(e))
                finally:
                    # Make sure to signal completion to stop other threads
                    search_complete.set()
            
            if found_player:
                rank = found_offset + 1
                update_progress(f"Found player at rank {rank}")
                return found_player, found_offset
            
            update_progress("Player not found in rankings")
            return None, 0
            
        except Exception as e:
            logger.error("Search failed", 
                        player=username, 
                        error=str(e))
            raise
    
    def get_rankings(self, offset: int = 0, limit: int = None) -> List[Dict]:
        """
        Get rankings for the specified offset and limit.
        
        Args:
            offset: Starting position (0-based)
            limit: Number of players to fetch (defaults to BATCH_SIZE)
        """
        try:
            if offset >= settings.MAX_SEARCH_OFFSET:
                logger.warning("max_offset_reached", offset=offset)
                return []

            # Use default batch size if no limit specified
            if limit is None:
                limit = settings.BATCH_SIZE
                
            # Ensure limit doesn't exceed maximum batch size
            limit = min(limit, settings.BATCH_SIZE)

            logger.info("fetching_rankings", offset=offset, limit=limit)
            
            # Use the search_rankings method which has the correct endpoint
            response = self.search_rankings(offset, limit)
            
            if response and response.get('res') == 'OK':
                results = response.get('results', {}).get('results', [])
                if isinstance(results, list):
                    return results
                logger.warning("invalid_rankings_data", data=response)
                return []
            
            logger.error("rankings_fetch_failed", response=response)
            return []
            
        except Exception as e:
            logger.error("rankings_fetch_error", offset=offset, limit=limit, error=str(e))
            return []
