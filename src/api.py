"""
Fightcade API client implementation.
"""
from typing import Dict, Tuple, Optional, Any, List
import cloudscraper
import time
from .config import settings
from .cache import PlayerCache, ReplayCache
from .logger import setup_logging

logger = setup_logging()

class FightcadeAPI:
    def __init__(self):
        """Initialize the API client."""
        self.scraper = cloudscraper.create_scraper()
        self.player_cache = PlayerCache()
        self.replay_cache = ReplayCache()
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
    
    def search_player(self, username: str, progress_callback=None, load_replays=True) -> Tuple[Optional[Dict], int]:
        """
        Search for a player using cache and API calls with parallel processing.
        
        Args:
            username: Player name to search for
            progress_callback: Optional callback function to report progress
            load_replays: Whether to load replay stats (defaults to True)
        """
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
            cached_player, start_offset = self.player_cache.search_player(username)
            if cached_player:
                update_progress(f"Found player in cache at rank {start_offset + 1}")
                
                # Get player replays and calculate stats only if requested
                if load_replays:
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
                    
                    players = response.get('results', {}).get('results', [])
                    if not players:
                        return None
                    
                    # Add to cache
                    self.player_cache.add_players(players, start_offset)
                    
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
                
                # Get player replays and calculate stats only if requested
                if load_replays:
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
            "gameid": settings.GAME_ID
        }
        
        logger.info("Fetching player replays", 
                   username=username,
                   offset=offset,
                   limit=limit,
                   gameid=settings.GAME_ID)
        
        response = self._make_request("POST", "", data=data)
        
        # Debug print full response structure
        print(f"\n=== API Response for {username} (offset: {offset}, limit: {limit}) ===")
        if response.get('res') == 'OK':
            results = response.get('results', {})
            print(f"Response Status: OK")
            print(f"Total Count: {results.get('count', 0)}")
            print(f"Results in batch: {len(results.get('results', []))}")
            print(f"First result: {results.get('results', [{}])[0] if results.get('results') else None}")
            print(f"Last result: {results.get('results', [{}])[-1] if results.get('results') else None}")
        else:
            print(f"Response Status: {response.get('res')}")
            print(f"Error: {response.get('error')}")
        print("=" * 80)
        
        return response

    def get_all_player_replays(self, username: str, max_replays: int = None, progress_callback=None) -> List[Dict]:
        """Get all available replays for a player using maximum batch size to minimize API calls."""
        import threading
        
        def update_progress(message: str) -> None:
            """Update progress with logging."""
            if progress_callback:
                progress_callback(message)
            logger.info("Replay fetch progress", username=username, message=message)

        try:
            # First get total matches from user info
            response = self.get_user(username)
            if response.get('res') != 'OK':
                logger.warning("Failed to get user info", username=username)
                return []
            
            total_matches = response.get('user', {}).get('gameinfo', {}).get(settings.GAME_ID, {}).get('num_matches', 0)
            logger.info("Total matches found", username=username, total_matches=total_matches)
            
            if total_matches == 0:
                return []
            
            # Check cache
            cached_data = self.replay_cache.get_player_replays(username)
            if cached_data and cached_data['replays']:
                cached_count = len(cached_data['replays'])
                logger.info("Found cached replays", username=username, cached_count=cached_count)
                
                # If we don't have all replays, fetch them all again
                if cached_count < total_matches:
                    logger.info("Cache incomplete, fetching all replays", 
                              username=username, 
                              cached_count=cached_count,
                              total_matches=total_matches)
                    cached_data = None
                else:
                    # Get latest replay to check for new ones
                    latest_response = self.get_player_replays(username, offset=0, limit=1)
                    if latest_response.get('res') == 'OK':
                        latest_replay = latest_response.get('results', {}).get('results', [])
                        if latest_replay:
                            cached_latest = max(replay['date'] for replay in cached_data['replays'])
                            logger.info("Comparing dates", 
                                      username=username, 
                                      latest_replay_date=latest_replay[0]['date'],
                                      cached_latest_date=cached_latest)
                            if latest_replay[0]['date'] <= cached_latest:
                                logger.info("Using cached replays - no new matches", username=username)
                                return cached_data['replays']
                    
                    update_progress(f"Fetching new replays...")
            else:
                logger.info("No cached replays found", username=username)
                update_progress(f"Fetching replays for {username}...")

            # Fetch all replays
            all_replays = []
            offset = 0
            batch_size = 100  # Use maximum batch size to reduce API calls
            batch_num = 0
            
            while True:
                batch_num += 1
                logger.info("Fetching batch", 
                           username=username,
                           batch=batch_num, 
                           offset=offset)
                
                response = self.get_player_replays(
                    username,
                    offset=offset,
                    limit=batch_size
                )
                
                if response.get('res') != 'OK':
                    if 'rate' in str(response.get('error', '')).lower():
                        logger.warning("Rate limit hit, waiting...", batch=batch_num)
                        time.sleep(settings.RATE_LIMIT_DELAY)
                        continue
                    logger.warning("Batch request failed", 
                                 batch=batch_num,
                                 error=response.get('error'))
                    break
                
                results = response.get('results', {}).get('results', [])
                current_count = len(results)
                
                logger.info(f"Batch {batch_num} fetched {current_count} replays (offset: {offset})")
                
                if current_count == 0:
                    logger.info("No more results, stopping", 
                              batch=batch_num,
                              total_fetched=len(all_replays))
                    break
                
                all_replays.extend(results)
                logger.info(f"Total replays so far: {len(all_replays)} (batch {batch_num})")
                
                offset += current_count  # Use actual number of results received for offset
                time.sleep(settings.REQUEST_DELAY)
            
            logger.info("Batch fetching complete", 
                       username=username,
                       total_fetched=len(all_replays))
            
            # Combine with cached replays if we have them
            if cached_data and cached_data['replays']:
                logger.info("Combining with cached replays", 
                          new_count=len(all_replays),
                          cached_count=len(cached_data['replays']))
                all_replays = all_replays + cached_data['replays']
            
            # Update cache
            self.replay_cache.cache_player_replays(username, all_replays)
            
            logger.info("Final replay count", 
                       username=username,
                       total_count=len(all_replays))
            
            return all_replays
            
        except Exception as e:
            logger.error("Error fetching replays", username=username, error=str(e))
            return []
    
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
        self.total_matches = 0
        self.wins = 0
        self.losses = 0
        
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
                
                # Get the scores
                player_score = player_data.get('score', 0)
                opponent_score = opponent_data.get('score', 0)
                
                # Skip invalid data
                if player_score < 0 or opponent_score < 0:
                    logger.warning(f"Invalid match data: player_score={player_score}, opponent_score={opponent_score}")
                    continue
                
                # Only count ranked matches
                if replay.get('ranked', 0) > 0:
                    # Add the scores to our totals
                    self.wins += player_score
                    self.losses += opponent_score
                    self.total_matches += player_score + opponent_score
                
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
