"""
Cache implementation for storing player data.
"""
from typing import Dict, List, Tuple, Optional, Any
import json
import time
from pathlib import Path
from collections import OrderedDict
from .config import settings
from .logger import setup_logging

logger = setup_logging()

class PlayerCache:
    def __init__(self):
        """Initialize the cache with lazy loading."""
        self.cache_file = settings.CACHE_DIR / "players.json"
        self.last_update = 0
        self.data = {}
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        settings.CACHE_DIR.mkdir(exist_ok=True)
    
    def _load_cache(self):
        """Load cache data from file if needed."""
        if not self.data and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.data = cache_data.get('data', {})
                    self.last_update = cache_data.get('timestamp', 0)
            except Exception as e:
                logger.error("Failed to load cache", error=str(e))
                self.data = {}
                self.last_update = 0
    
    def get(self, key: str) -> Optional[Dict]:
        """Get a value from the cache."""
        self._load_cache()
        if not self.is_valid():
            return None
        return self.data.get(key)
    
    def set(self, key: str, value: Dict) -> None:
        """Set a value in the cache."""
        self._load_cache()
        self.data[key] = value
        self.last_update = int(time.time())
        self._save_cache()
    
    def _save_cache(self) -> None:
        """Save cache data to file."""
        try:
            cache_data = {
                'timestamp': self.last_update,
                'data': self.data
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.error("Failed to save cache", error=str(e))
    
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return (time.time() - self.last_update) < settings.CACHE_DURATION
    
    def search_player(self, player_name: str) -> Tuple[Optional[Dict], int]:
        """
        Search for a player in the cached rankings.
        Returns (player_data, position) if found, (None, last_position) if not found.
        """
        self._load_cache()
        if not self.is_valid():
            return None, 0
        
        target_name = player_name.lower()
        for i, (_, player) in enumerate(self.data.items()):
            if player.get('name', '').lower() == target_name:
                logger.info("player_found_in_cache", position=i)
                return player, i
        
        # Return None and the size of cache as the last checked position
        return None, len(self.data)
    
    def add_players(self, players: List[Dict], offset: int) -> None:
        """Add players to cache and update last offset."""
        self._load_cache()
        
        # If cache is expired, clear it
        if not self.is_valid():
            self.data = {}
            self.last_update = int(time.time())
        
        # Add new players to cache
        for player in players:
            name = player.get('name', '').lower()
            if name:  # Only add players with valid names
                self.data[name] = player
        
        # Save the updated cache
        self._save_cache()
        logger.info("players_added_to_cache", new_count=len(players), total_count=len(self.data))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        self._load_cache()
        cache_size = 0
        if self.cache_file.exists():
            cache_size = self.cache_file.stat().st_size
        
        return {
            'is_valid': self.is_valid(),
            'total_players': len(self.data),
            'size_bytes': cache_size,
            'last_update': self.last_update
        }
    
    def clean_cache(self) -> None:
        """Clear all cached data and remove the cache file."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()  # Delete the cache file
            self.data = {}  # Clear the in-memory cache
            self.last_update = 0
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error("Failed to clear cache", error=str(e))
            raise

class ReplayCache:
    def __init__(self):
        """Initialize the replay cache with FIFO queue."""
        self.cache_file = settings.CACHE_DIR / settings.REPLAY_CACHE_FILE
        self.data = OrderedDict()  # Using OrderedDict for FIFO implementation
        self._ensure_cache_dir()
        self._load_cache()
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        settings.CACHE_DIR.mkdir(exist_ok=True)
    
    def _load_cache(self):
        """Load cache data from file if needed."""
        if not self.data and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # Convert to OrderedDict to maintain FIFO order
                    self.data = OrderedDict(cache_data.get('data', {}))
            except Exception as e:
                logger.error("Failed to load replay cache", error=str(e))
                self.data = OrderedDict()
    
    def get_player_replays(self, username: str) -> Optional[Dict]:
        """Get cached replays for a player with metadata."""
        username = username.lower()
        return self.data.get(username)
    
    def cache_player_replays(self, username: str, replays: List[Dict], total_matches: int) -> None:
        """Cache replays for a player with metadata, maintaining FIFO order."""
        username = username.lower()
        
        # If player already in cache, update their position (remove and re-add)
        if username in self.data:
            del self.data[username]
        
        # Add new player's replays with metadata
        self.data[username] = {
            'replays': replays,
            'total_matches': total_matches,
            'cached_at': int(time.time())
        }
        
        # If cache exceeds max size, remove oldest entry
        while len(self.data) > settings.MAX_CACHED_PLAYERS:
            self.data.popitem(last=False)  # Remove oldest item (FIFO)
        
        self._save_cache()
        
        logger.info("Cached replays for player", 
                   username=username, 
                   replay_count=len(replays),
                   total_matches=total_matches,
                   cache_size=len(self.data))
    
    def _save_cache(self) -> None:
        """Save cache data to file."""
        try:
            cache_data = {
                'data': dict(self.data)  # Convert OrderedDict to dict for JSON serialization
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.error("Failed to save replay cache", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_size = 0
        if self.cache_file.exists():
            cache_size = self.cache_file.stat().st_size
        
        return {
            'total_players': len(self.data),
            'size_bytes': cache_size,
            'players': list(self.data.keys())
        }
    
    def clean_cache(self) -> None:
        """Clear all cached replay data and remove the cache file."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()  # Delete the cache file
            self.data = OrderedDict()  # Clear the in-memory cache
            logger.info("Replay cache cleared successfully")
        except Exception as e:
            logger.error("Failed to clear replay cache", error=str(e))
            raise
