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
            
            # Get the total number of ranked matches for this player
            game_info = user_data.get('user', {}).get('gameinfo', {}).get('kof2002', {})
            total_ranked_matches = game_info.get('num_matches', 0)
            
            update_progress("Player found, searching for ranking...")
            
            # Check cache first
            cached_player, start_offset = self.cache.search_player(username)
            if cached_player:
                update_progress(f"Found player in cache at rank {start_offset + 1}")
                
                # Get player replays and calculate stats
                update_progress(f"Fetching {total_ranked_matches} replays...")
                replays = self.get_all_player_replays(
                    username, 
                    max_replays=total_ranked_matches,
                    progress_callback=progress_callback
                )
                if replays:
                    stats = ReplayStats()
                    replay_stats = stats.calculate_stats(replays, username)
                    if replay_stats:
                        cached_player['replay_stats'] = replay_stats
                
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
                
                # Get player replays and calculate stats
                update_progress("Fetching player replays...")
                replays = self.get_player_replays(username)
                if replays and replays.get('res') == 'OK':
                    replay_results = replays.get('results', {}).get('results', [])
                    stats = ReplayStats()
                    replay_stats = stats.calculate_stats(replay_results, username)
                    if replay_stats:
                        found_player['replay_stats'] = replay_stats
                
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

    def get_player_replays(self, username: str, offset: int = 0, limit: int = 100) -> Dict:
        """Get player replay information."""
        data = {
            "req": "searchquarks",
            "username": username,
            "offset": offset,
            "limit": limit,
            "gameid": settings.GAME_ID  # Use game ID instead of channel name
        }
        
        logger.info("Fetching player replays", 
                   username=username,
                   offset=offset,
                   limit=limit,
                   gameid=settings.GAME_ID)
        
        response = self._make_request("POST", "", data=data)
        
        if response.get('res') == 'OK':
            results = response.get('results', {}).get('results', [])
            logger.info("Replay fetch response", 
                       username=username,
                       total_replays=len(results),
                       has_results=bool(results))
        
        return response

    def get_all_player_replays(self, username: str, max_replays: int = None, progress_callback=None) -> List[Dict]:
        """Get all available replays for a player with parallel processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        if max_replays is None:
            max_replays = settings.MAX_REPLAY_OFFSET
        
        all_replays = []
        search_complete = threading.Event()
        
        def update_progress(message: str, username: str) -> None:
            """Update progress with logging."""
            if progress_callback:
                progress_callback(message)
            logger.info("Replay fetch progress", 
                       username=username,
                       message=message)
        
        def fetch_batch(start_offset: int, batch_number: int) -> Optional[List[Dict]]:
            """Fetch a batch of replays."""
            if search_complete.is_set():
                return None
                
            try:
                response = self.get_player_replays(
                    username,
                    offset=start_offset,
                    limit=settings.REPLAY_BATCH_SIZE
                )
                
                if response.get('res') != 'OK':
                    if 'rate' in str(response.get('error', '')).lower():
                        time.sleep(settings.RATE_LIMIT_DELAY)
                    return None
                
                results = response.get('results', {}).get('results', [])
                if not results:
                    search_complete.set()
                    return None
                
                return results
                
            except Exception as e:
                logger.error("Batch fetch failed", 
                           batch=batch_number,
                           error=str(e))
                return None
        
        try:
            # Calculate number of batches needed
            total_batches = (max_replays + settings.REPLAY_BATCH_SIZE - 1) // settings.REPLAY_BATCH_SIZE
            update_progress(f"Fetching {total_batches} batches of replays...", username)
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for batch_num in range(total_batches):
                    if search_complete.is_set():
                        break
                    
                    start_offset = batch_num * settings.REPLAY_BATCH_SIZE
                    if start_offset >= max_replays:
                        break
                        
                    futures.append(
                        executor.submit(fetch_batch, start_offset, batch_num)
                    )
                    time.sleep(settings.REQUEST_DELAY)  # Avoid rate limiting
                
                # Process results as they complete
                for future in as_completed(futures):
                    if search_complete.is_set():
                        break
                        
                    result = future.result()
                    if result:
                        all_replays.extend(result)
                        
                        # Stop if we've reached the max replays
                        if len(all_replays) >= max_replays:
                            search_complete.set()
                            all_replays = all_replays[:max_replays]
                            break
                            
            logger.info("Replay fetch complete", 
                       username=username,
                       total_replays=len(all_replays))
            
            return all_replays
            
        except Exception as e:
            logger.error("Error fetching replays", 
                        username=username,
                        error=str(e))
            return all_replays

class ReplayStats:
    """Calculate statistics from replay data."""
    
    def __init__(self):
        """Initialize the replay stats calculator."""
        self.total_matches = 0
        self.wins = 0
        self.losses = 0
        self.win_rate = 0.0
        
    def calculate_stats(self, replays: List[Dict], username: str) -> Optional[Dict]:
        """Calculate statistics from replay data."""
        if not replays:
            logger.warning("No replays provided for statistics calculation")
            return {
                'total_matches': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0
            }
            
        try:
            self._process_replays(replays, username)
            return self._compile_stats()
        except Exception as e:
            logger.error(f"Error calculating replay stats: {str(e)}")
            return None
            
    def _process_replays(self, replays: List[Dict], username: str) -> None:
        """Process replay data to calculate statistics."""
        for replay in replays:
            try:
                # Get player information from the replay
                players = replay.get('players', [])
                if len(players) != 2:
                    logger.warning(f"Skipping replay with invalid player count: {len(players)}")
                    continue
                
                # Find which player is the one we're looking for
                player_data = None
                opponent_data = None
                for i, player in enumerate(players):
                    if player.get('name', '').lower() == username.lower():
                        player_data = player
                        opponent_data = players[1 - i]  # Get the other player
                        break
                
                if not player_data or not opponent_data:
                    logger.warning("Player data not found in replay")
                    continue
                
                # Get the number of matches and scores
                total_matches = replay.get('num_matches', 0)
                ranked_matches = replay.get('ranked', 0)
                player_wins = player_data.get('score', 0)
                opponent_wins = opponent_data.get('score', 0)
                
                # Skip invalid data
                if total_matches <= 0 or player_wins < 0 or opponent_wins < 0:
                    logger.warning(f"Invalid match data: total={total_matches}, wins={player_wins}, opponent_wins={opponent_wins}")
                    continue
                
                # Verify the scores add up to total matches
                if player_wins + opponent_wins != total_matches:
                    logger.warning(f"Score mismatch: total={total_matches}, wins={player_wins}, opponent_wins={opponent_wins}")
                    continue
                
                # Only count ranked matches
                if ranked_matches > 0:
                    # Calculate the proportion of ranked matches
                    ranked_ratio = ranked_matches / total_matches
                    # Apply the ratio to the wins and losses
                    self.wins += round(player_wins * ranked_ratio)
                    self.losses += round(opponent_wins * ranked_ratio)
                    self.total_matches += ranked_matches
                
            except Exception as e:
                logger.error(f"Error processing replay: {str(e)}")
                continue
                
        # Calculate win rate if there are matches
        if self.total_matches > 0:
            self.win_rate = (self.wins / self.total_matches) * 100.0
            
    def _compile_stats(self) -> Dict:
        """Compile the calculated statistics into a dictionary."""
        return {
            'total_matches': self.total_matches,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(self.win_rate, 2)  # Store as percentage
        }
