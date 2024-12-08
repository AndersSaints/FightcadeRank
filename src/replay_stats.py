"""
Module for handling Fightcade replay statistics.
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ReplayStats:
    """Calculate statistics from replay data."""
    
    def __init__(self):
        """Initialize the replay stats calculator."""
        self.total_matches = 0
        self.wins = 0
        self.losses = 0
        self.win_rate = 0.0
        self.total_games = 0
        self.last_played = None
        self.opponents: Dict[str, int] = {}
        self.character_usage: Dict[str, int] = {}
        
    def calculate_stats(self, replays: List[Dict], username: str) -> Optional[Dict]:
        """Calculate statistics from replay data."""
        if not replays:
            logger.warning("No replays provided for statistics calculation")
            return None
            
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
                self._process_single_replay(replay, username)
            except Exception as e:
                logger.error(f"Error processing replay {replay.get('quark', 'unknown')}: {str(e)}")
                continue
                
        if self.total_matches > 0:
            self.win_rate = (self.wins / self.total_matches) * 100
            
    def _process_single_replay(self, replay: Dict, username: str) -> None:
        """Process a single replay entry."""
        try:
            # Update match count
            self.total_matches += 1
            
            # Process timestamp
            timestamp = replay.get('ts', 0)
            if timestamp:
                replay_date = datetime.fromtimestamp(timestamp)
                if not self.last_played or replay_date > self.last_played:
                    self.last_played = replay_date
            
            # Process player data
            p1_data = replay.get('p1', {})
            p2_data = replay.get('p2', {})
            
            if not p1_data or not p2_data:
                logger.warning(f"Incomplete player data in replay {replay.get('quark', 'unknown')}")
                return
                
            p1_name = p1_data.get('name', '').lower()
            p2_name = p2_data.get('name', '').lower()
            
            if username.lower() not in [p1_name, p2_name]:
                logger.warning(f"Username {username} not found in replay {replay.get('quark', 'unknown')}")
                return
                
            # Determine if user won
            is_p1 = username.lower() == p1_name
            winner = replay.get('winner', 0)
            
            if (is_p1 and winner == 1) or (not is_p1 and winner == 2):
                self.wins += 1
            else:
                self.losses += 1
                
            # Update opponent stats
            opponent = p2_name if is_p1 else p1_name
            self.opponents[opponent] = self.opponents.get(opponent, 0) + 1
            
            # Update character usage
            character = p1_data.get('char', '') if is_p1 else p2_data.get('char', '')
            if character:
                self.character_usage[character] = self.character_usage.get(character, 0) + 1
                
        except Exception as e:
            logger.error(f"Error processing replay data: {str(e)}")
            raise
            
    def _compile_stats(self) -> Dict:
        """Compile the calculated statistics into a dictionary."""
        return {
            'total_matches': self.total_matches,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(self.win_rate, 2),
            'last_played': self.last_played.isoformat() if self.last_played else None,
            'opponents': dict(sorted(self.opponents.items(), key=lambda x: x[1], reverse=True)),
            'character_usage': dict(sorted(self.character_usage.items(), key=lambda x: x[1], reverse=True))
        }
