"""
Cache implementation for storing player data.
"""
from typing import Dict, List, Tuple, Optional
import json
import time
from pathlib import Path
from .config import settings
from .logger import setup_logging

logger = setup_logging()

class PlayerCache:
    def __init__(self):
        """Initialize the cache with disk storage support."""
        self.cache_file = settings.CACHE_DIR / "player_cache.json"
        self.rankings_cache = {
            'timestamp': None,
            'data': [],
            'last_offset': 0
        }
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    if self._is_cache_valid(data.get('timestamp')):
                        self.rankings_cache = data
                        logger.info("cache_loaded", 
                                  players_count=len(data['data']), 
                                  last_offset=data['last_offset'])
                    else:
                        logger.info("cache_expired", 
                                  cache_age=time.time() - (data.get('timestamp') or 0))
        except Exception as e:
            logger.error("cache_load_error", error=str(e))
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.rankings_cache, f)
            logger.info("cache_saved", 
                       players_count=len(self.rankings_cache['data']), 
                       last_offset=self.rankings_cache['last_offset'])
        except Exception as e:
            logger.error("cache_save_error", error=str(e))
    
    def _is_cache_valid(self, timestamp: Optional[float] = None) -> bool:
        """Check if cache is valid (less than configured duration old)."""
        if timestamp is None:
            timestamp = self.rankings_cache['timestamp']
        
        if not timestamp:
            return False
        
        elapsed_time = time.time() - timestamp
        return elapsed_time < settings.CACHE_DURATION
    
    def add_players(self, players: List[Dict], offset: int) -> None:
        """Add players to cache and update last offset."""
        if not self._is_cache_valid():
            logger.info("cache_expired_clearing")
            self.rankings_cache['data'] = []
            self.rankings_cache['timestamp'] = time.time()
            self.rankings_cache['last_offset'] = 0
        
        # Only add players that aren't already in cache
        existing_names = {p.get('name', '').lower() for p in self.rankings_cache['data']}
        new_players = [p for p in players if p.get('name', '').lower() not in existing_names]
        
        if new_players:
            self.rankings_cache['data'].extend(new_players)
            self.rankings_cache['last_offset'] = max(
                self.rankings_cache['last_offset'], 
                offset + len(players)
            )
            logger.info("players_added_to_cache", 
                       new_count=len(new_players), 
                       total_count=len(self.rankings_cache['data']))
            self._save_cache()
        else:
            logger.info("no_new_players_to_cache")
    
    def search_player(self, player_name: str) -> Tuple[Optional[Dict], int]:
        """Search for player in cache."""
        if not self._is_cache_valid():
            logger.info("cache_invalid")
            return None, 0
        
        target = player_name.lower()
        logger.info("searching_cache", 
                   cache_size=len(self.rankings_cache['data']))
        
        for i, player in enumerate(self.rankings_cache['data']):
            if player.get('name', '').lower() == target:
                logger.info("player_found_in_cache", position=i)
                return player, i
        
        logger.info("player_not_in_cache", 
                   last_offset=self.rankings_cache['last_offset'])
        return None, self.rankings_cache['last_offset']
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the current cache state."""
        return {
            'total_players': len(self.rankings_cache['data']),
            'last_offset': self.rankings_cache['last_offset'],
            'is_valid': self._is_cache_valid(),
            'age': time.time() - (self.rankings_cache['timestamp'] or time.time()),
            'size_bytes': self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
