"""
UI implementation using customtkinter.
"""
import customtkinter as ctk
from typing import Optional, List, Dict
import threading
from datetime import datetime
import time
from PIL import Image, ImageTk
from pathlib import Path
from .config import settings
from .api import FightcadeAPI, ReplayStats
from .logger import setup_logging

logger = setup_logging()

class LoadingSpinner(ctk.CTkFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.angle = 0
        self.is_spinning = False
        
        # Create canvas for spinner
        self.canvas = ctk.CTkCanvas(self, width=30, height=30, 
                                  bg=self._fg_color[1], highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")
        
        # Draw initial spinner
        self._draw_spinner()
    
    def _draw_spinner(self):
        """Draw the spinner at current angle."""
        self.canvas.delete("spinner")
        # Draw arc from current angle
        self.canvas.create_arc(5, 5, 25, 25, 
                             start=self.angle, 
                             extent=300,
                             tags="spinner", 
                             width=2, 
                             outline="#1f538d")
    
    def start(self):
        """Start spinning animation."""
        if not self.is_spinning:
            self.is_spinning = True
            self._spin()
    
    def stop(self):
        """Stop spinning animation."""
        self.is_spinning = False
    
    def _spin(self):
        """Animate the spinner."""
        if self.is_spinning:
            self.angle = (self.angle + 10) % 360
            self._draw_spinner()
            self.after(50, self._spin)

class StatusBar(ctk.CTkFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Status message
        self.status_label = ctk.CTkLabel(self, text="Ready")
        self.status_label.pack(side="left", padx=5)
        
        # Cache info
        self.cache_label = ctk.CTkLabel(self, text="Cache: Empty")
        self.cache_label.pack(side="right", padx=5)
    
    def update_status(self, message: str):
        """Update status message."""
        self.status_label.configure(text=message)
    
    def update_cache_info(self, player_stats: Dict, replay_stats: Dict):
        """Update cache statistics."""
        cache_info = []
        
        if player_stats['total_players'] > 0:
            cache_info.append(f"Players: {player_stats['total_players']}")
        
        if player_stats['size_bytes'] > 0:
            size_mb = player_stats['size_bytes'] / (1024 * 1024)
            cache_info.append(f"Size: {size_mb:.1f}MB")
        
        if replay_stats['total_players'] > 0:
            cache_info.append(f"Cached Replays: {replay_stats['total_players']}")
        
        text = " | ".join(cache_info) if cache_info else "Cache: Empty"
        self.cache_label.configure(text=text)

class FCRankApp(ctk.CTk):
    def __init__(self):
        """Initialize the main application window."""
        super().__init__()
        
        # Configure window
        self.title("Fightcade KOF 2002 Rankings")
        self.geometry(f"{settings.WINDOW_SIZE[0]}x{settings.WINDOW_SIZE[1]}")
        self.minsize(*settings.MIN_WINDOW_SIZE)
        
        # Set theme and styling
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize variables
        self.search_thread = None
        self.rankings_data = []
        self.current_page = 0
        self.total_players = 0
        
        # Initialize image caches
        self.flag_images = {}
        self.rank_images = {}
        self.flags_dir = Path("flags")
        self.rank_dir = Path("rank")
        
        # Configure grid with better responsiveness
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Initialize API
        self.api = FightcadeAPI()
        
        # Create UI components
        self._create_header_frame()
        self._create_content_frame()
        self._create_status_bar()
        
        # Set up keyboard shortcuts
        self.bind('<Return>', lambda e: self.search_player())
        self.bind('<Control-f>', lambda e: self.search_entry.focus())
        self.bind('<Escape>', lambda e: self.clear_search())
        
        # Update cache info
        self._update_cache_info()
        
        # Start preloading images in background
        threading.Thread(target=self._preload_images, daemon=True).start()
        
        logger.info("ui_initialized")
    
    def _preload_images(self):
        """Preload images in background for better performance."""
        try:
            # Preload rank images (small set)
            for rank_file in self.rank_dir.glob("rank*.png"):
                if rank_file.name not in self.rank_images:
                    try:
                        rank_num = int(rank_file.stem[4:])
                        self._load_rank_image(rank_num)
                    except Exception as e:
                        logger.error(f"Failed to preload rank: {rank_file.name}", error=str(e))
            
            # Preload most common flag images
            common_flags = ['us', 'br', 'jp', 'kr', 'cn', 'gb', 'fr', 'de', 'es', 'mx']
            for code in common_flags:
                flag_file = self.flags_dir / f"{code}.png"
                if flag_file.exists() and code not in self.flag_images:
                    try:
                        self._load_flag_image(code)
                    except Exception as e:
                        logger.error(f"Failed to preload flag: {code}", error=str(e))
        except Exception as e:
            logger.error("Failed to preload images", error=str(e))
    
    def _load_flag_image(self, country_code: str) -> Optional[ImageTk.PhotoImage]:
        """Load a single flag image."""
        if country_code in self.flag_images:
            return self.flag_images[country_code]
        
        flag_file = self.flags_dir / f"{country_code}.png"
        if flag_file.exists() and not flag_file.name.startswith("._"):
            try:
                img = Image.open(flag_file)
                img = img.resize((24, 16), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.flag_images[country_code] = photo
                return photo
            except Exception as e:
                logger.error(f"Failed to load flag: {country_code}", error=str(e))
        return None
    
    def _load_rank_image(self, rank_num: int) -> Optional[ImageTk.PhotoImage]:
        """Load a single rank image."""
        if rank_num in self.rank_images:
            return self.rank_images[rank_num]
        
        rank_file = self.rank_dir / f"rank{rank_num}.png"
        if rank_file.exists():
            try:
                img = Image.open(rank_file)
                img = img.resize((24, 24), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.rank_images[rank_num] = photo
                return photo
            except Exception as e:
                logger.error(f"Failed to load rank: {rank_num}", error=str(e))
        return None
    
    def _create_header_frame(self):
        """Create the header frame with search controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        header.grid_columnconfigure(1, weight=1)  # Make search entry expand
        
        # Search label
        search_label = ctk.CTkLabel(
            header,
            text="Player Search:",
            font=("Helvetica", 12, "bold")
        )
        search_label.grid(row=0, column=0, padx=(5, 0), pady=5)
        
        # Search entry with better styling
        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text="Enter player name...",
            width=300,
            height=32
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Clear button
        self.clear_button = ctk.CTkButton(
            header,
            text="Clear",
            command=self.clear_search,
            width=60,
            height=32
        )
        self.clear_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Search button with icon
        self.search_button = ctk.CTkButton(
            header,
            text="Search",
            command=self.search_player,
            width=80,
            height=32
        )
        self.search_button.grid(row=0, column=3, padx=5, pady=5)
        
        # Loading spinner
        self.spinner = LoadingSpinner(header)
        self.spinner.grid(row=0, column=4, padx=5, pady=5)

        # Add a separator
        separator = ctk.CTkFrame(header, width=2, height=32)
        separator.grid(row=0, column=5, padx=10, pady=5)
        
        # Ranking pages label
        ranking_label = ctk.CTkLabel(
            header,
            text="Ranking Pages:",
            font=("Helvetica", 12, "bold")
        )
        ranking_label.grid(row=0, column=6, padx=(5, 0), pady=5)
        
        # Ranking pages entry
        self.ranking_pages_entry = ctk.CTkEntry(
            header,
            placeholder_text="# of pages",
            width=80,
            height=32
        )
        self.ranking_pages_entry.grid(row=0, column=7, padx=5, pady=5)
        self.ranking_pages_entry.insert(0, "1")  # Default value
        
        # Get Rankings button
        self.get_rankings_button = ctk.CTkButton(
            header,
            text="Get Rankings",
            command=self.get_rankings,
            width=100,
            height=32
        )
        self.get_rankings_button.grid(row=0, column=8, padx=5, pady=5)
        
        # Clean Cache button
        self.clean_cache_button = ctk.CTkButton(
            header,
            text="Clean Cache",
            command=self.clean_cache,
            width=100,
            height=32
        )
        self.clean_cache_button.grid(row=0, column=9, padx=5, pady=5)
        
        # Add tooltips
        self._add_tooltip(self.search_entry, "Enter player name to search")
        self._add_tooltip(self.clear_button, "Clear search (Esc)")
        self._add_tooltip(self.search_button, "Search for player (Enter)")
        self._add_tooltip(self.ranking_pages_entry, "Enter number of ranking pages to fetch (1-50)")
        self._add_tooltip(self.get_rankings_button, "Fetch rankings for specified number of pages")
        self._add_tooltip(self.clean_cache_button, "Clear the player cache")
    
    def _create_content_frame(self):
        """Create the main content frame with results table."""
        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        
        # Table headers
        headers = [
            "Rank",
            "ELO",
            "Player",
            "Country",
            "Matches",
            "Wins",
            "Losses",
            "Win Rate",
            "Time (hrs)",
            "On Page"
        ]

        # Configure column widths
        column_widths = {
            0: 60,  # Rank
            1: 60,  # ELO
            2: 200, # Player
            3: 80,  # Country
            4: 80,  # Matches
            5: 80,  # Wins
            6: 80,  # Losses
            7: 100, # Win Rate
            8: 100, # Time
            9: 60   # On Page
        }
        
        header_frame = ctk.CTkFrame(content)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Configure header columns
        for i in range(len(headers)):
            header_frame.grid_columnconfigure(i, weight=0, minsize=column_widths[i])
        
        # Create headers
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(
                header_frame,
                text=header,
                font=("Helvetica", 12, "bold"),
                width=column_widths[i]
            )
            label.grid(row=0, column=i, sticky="ew", padx=5, pady=5)
        
        # Results frame with scrollbar
        self.results_frame = ctk.CTkScrollableFrame(content)
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure results frame columns
        for i in range(len(headers)):
            self.results_frame.grid_columnconfigure(i, weight=0, minsize=column_widths[i])
        
        # Navigation frame
        nav_frame = ctk.CTkFrame(content)
        nav_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        # Previous page button
        self.prev_button = ctk.CTkButton(
            nav_frame,
            text="◀ Previous",
            command=self.prev_page,
            state="disabled",
            width=100
        )
        self.prev_button.pack(side="left", padx=5)
        
        # Page info
        self.page_label = ctk.CTkLabel(
            nav_frame,
            text="Page 0 of 0",
            font=("Helvetica", 12)
        )
        self.page_label.pack(side="left", padx=20)
        
        # Next page button
        self.next_button = ctk.CTkButton(
            nav_frame,
            text="Next ▶",
            command=self.next_page,
            state="disabled",
            width=100
        )
        self.next_button.pack(side="left", padx=5)

        # Add a separator
        separator = ctk.CTkFrame(nav_frame, width=2, height=32)
        separator.pack(side="left", padx=20)

        # Load Stats button
        self.load_stats_button = ctk.CTkButton(
            nav_frame,
            text="Load Stats",
            command=self.load_player_stats,
            width=100,
            height=32
        )
        self.load_stats_button.pack(side="left", padx=5)
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
    
    def _update_cache_info(self):
        """Update cache information in the status bar."""
        try:
            player_stats = self.api.player_cache.get_stats()
            replay_stats = self.api.replay_cache.get_stats()
            self.status_bar.update_cache_info(player_stats, replay_stats)
        except Exception as e:
            logger.error("Failed to update cache info", error=str(e))
            self.status_bar.cache_label.configure(text="Cache info unavailable")
    
    def search_player(self, username: Optional[str] = None):
        """Start player search in a separate thread."""
        if self.search_thread and self.search_thread.is_alive():
            logger.info("search_already_running")
            return
        
        if username is None:
            username = self.search_entry.get().strip()
        
        if not username:
            self.show_error("Please enter a username")
            return
        
        # Disable search controls
        self.search_button.configure(state="disabled")
        self.search_entry.configure(state="disabled")
        
        # Start spinner
        self.spinner.start()
        
        # Clear previous results
        self.rankings_data = []
        
        def search_task():
            """Search task to run in separate thread."""
            try:
                # Only fetch basic player info without replay stats
                player, offset = self.api.search_player(
                    username,
                    progress_callback=lambda msg: self.after(0, self.update_progress, msg),
                    load_replays=False  # Don't fetch replay stats immediately
                )
                
                if player:
                    # Calculate actual rank (offset + 1)
                    actual_rank = offset + 1
                    player['found_rank'] = actual_rank
                    self.rankings_data = [player]
                    self.current_page = 0
                    self.after(0, self.display_rankings)
                    self.after(0, lambda: self.update_progress("Found player"))
                
            except Exception as e:
                logger.error("search_error", error=str(e))
                self.after(0, self.show_error, str(e))
            
            finally:
                # Re-enable search controls
                self.after(0, self._end_search)
        
        self.search_thread = threading.Thread(target=search_task)
        self.search_thread.daemon = True
        self.search_thread.start()
        
        logger.info("search_started", username=username)
    
    def _end_search(self):
        """Clean up after search completion."""
        self.search_button.configure(state="normal")
        self.search_entry.configure(state="normal")
        self.spinner.stop()
        self._update_cache_info()
    
    def display_rankings(self):
        """Display current page of rankings."""
        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        
        start_idx = self.current_page * 15
        page_data = self.rankings_data[start_idx:start_idx + 15]
        
        for i, player in enumerate(page_data):
            # Get position in rankings
            position = player.get('found_rank', player.get('rank', 0))
            
            # Create position label with fixed width
            position_label = ctk.CTkLabel(self.results_frame, text=str(position), width=60)
            position_label.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            
            # Get game info with proper fallbacks
            game_info = player.get('gameinfo', {}).get('kof2002', {})
            
            # Get rank from game info for the rank image
            api_rank = game_info.get('rank', 1)  # Default to 1 if not found
            rank_image = self._load_rank_image(api_rank)
            if rank_image:
                elo_label = ctk.CTkLabel(self.results_frame, text="", image=rank_image, width=60)
                elo_label.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
                self._add_tooltip(elo_label, f"Rank {api_rank}")
            
            # Create player name label with fixed width
            name_label = ctk.CTkLabel(self.results_frame, text=player.get('name', ''), width=200)
            name_label.grid(row=i, column=2, sticky="ew", padx=5, pady=2)
            
            # Extract country info
            country = player.get('country', {})
            country_code = country.get('iso_code', '').lower() if isinstance(country, dict) else ''
            
            # Get stats from replay calculation
            replay_stats = player.get('replay_stats', {})
            matches = replay_stats.get('total_matches', 0)
            wins = replay_stats.get('wins', 0)
            losses = replay_stats.get('losses', 0)
            win_rate = replay_stats.get('win_rate', 0.0)  # Already in percentage form
            
            time_played = round(game_info.get('time_played', 0) / 3600, 1)  # Convert to hours
            
            # Create country flag label with fixed width
            flag_label = ctk.CTkLabel(self.results_frame, text="", width=80)
            if country_code:
                flag_image = self._load_flag_image(country_code)
                if flag_image:
                    flag_label.configure(image=flag_image)
                    self._add_tooltip(flag_label, country.get('name', country_code.upper()))
                else:
                    flag_label.configure(text=country_code.upper())
            flag_label.grid(row=i, column=3, sticky="ew", padx=5, pady=2)
            
            # Add remaining stats with fixed widths
            stats = [
                (str(matches), 80),
                (str(wins), 80),
                (str(losses), 80),
                (f"{win_rate:.1f}%", 100),  # Display win rate with one decimal place
                (str(time_played), 100),
                (str((position - 1) // 15 + 1), 60)  # Calculate which page the player is on
            ]
            
            for j, (text, width) in enumerate(stats, 4):
                label = ctk.CTkLabel(self.results_frame, text=text, width=width)
                label.grid(row=i, column=j, sticky="ew", padx=5, pady=2)
        
        # Update navigation
        total_pages = (len(self.rankings_data) - 1) // 15 + 1
        self.page_label.configure(
            text=f"Page {self.current_page + 1} of {total_pages}"
        )
        
        self.prev_button.configure(
            state="normal" if self.current_page > 0 else "disabled"
        )
        self.next_button.configure(
            state="normal" if self.current_page < total_pages - 1 else "disabled"
        )
        
        logger.info("rankings_displayed", 
                   page=self.current_page + 1, 
                   total_pages=total_pages)
    
    def _determine_rank(self, position: int) -> int:
        """
        DEPRECATED: No longer used as rank is now taken directly from API response.
        Previously used to determine rank based on player position.
        """
        return position
    
    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_rankings()
    
    def next_page(self):
        """Go to next page."""
        total_pages = (len(self.rankings_data) - 1) // 15 + 1
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_rankings()
    
    def update_progress(self, message: str):
        """Update progress message and status bar."""
        self.status_bar.update_status(message)
    
    def show_error(self, message: str):
        """Show error message."""
        self.status_bar.update_status(f"Error: {message}")
        logger.error("error_displayed", message=message)

    def clear_search(self):
        """Clear search entry and results."""
        self.search_entry.delete(0, 'end')
        self.search_entry.focus()
        self.rankings_data = []
        self.current_page = 0
        self.display_rankings()
        self.update_progress("")
    
    def _add_tooltip(self, widget, text):
        """Add tooltip to widget."""
        tooltip_timer = None
        
        def show_tooltip(event):
            nonlocal tooltip_timer
            # Cancel any existing timer
            if tooltip_timer:
                widget.after_cancel(tooltip_timer)
            # Start new timer for 500ms delay
            tooltip_timer = widget.after(500, lambda: create_tooltip(event))
        
        def create_tooltip(event):
            tooltip = ctk.CTkToplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ctk.CTkLabel(
                tooltip,
                text=text,
                font=("Helvetica", 11),
                fg_color=("gray80", "gray20"),
                corner_radius=6
            )
            label.pack(padx=5, pady=5)
            
            def hide_tooltip():
                tooltip.destroy()
            
            widget._tooltip = tooltip
            widget.after(2000, hide_tooltip)
        
        def hide_tooltip(event):
            nonlocal tooltip_timer
            # Cancel pending tooltip
            if tooltip_timer:
                widget.after_cancel(tooltip_timer)
                tooltip_timer = None
            # Destroy existing tooltip
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                del widget._tooltip
        
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)

    def get_rankings(self):
        """Fetch rankings for the specified number of pages."""
        try:
            ui_pages = int(self.ranking_pages_entry.get().strip())
            if ui_pages < 1:
                self.show_error("Please enter a positive number of pages")
                return
            if ui_pages > 50:
                self.show_error("Maximum 50 pages allowed")
                return
                
            # Calculate total players needed based on UI pages
            total_players_needed = ui_pages * settings.UI_PAGE_SIZE
            
            # Calculate how many API calls we need (each API call can fetch up to 100 players)
            api_calls_needed = (total_players_needed + settings.BATCH_SIZE - 1) // settings.BATCH_SIZE
                
            # Disable controls during fetch
            self.get_rankings_button.configure(state="disabled")
            self.ranking_pages_entry.configure(state="disabled")
            self.spinner.start()
            
            # Start fetching in a separate thread
            def fetch_task():
                try:
                    self.update_progress("Fetching rankings...")
                    rankings = []
                    
                    for api_call in range(api_calls_needed):
                        # Calculate remaining players needed
                        remaining_players = total_players_needed - len(rankings)
                        
                        # For the last batch, only request what we need (up to 100)
                        batch_size = min(settings.BATCH_SIZE, remaining_players)
                        
                        # Calculate API offset based on current progress
                        api_offset = api_call * settings.BATCH_SIZE
                        
                        self.update_progress(f"Fetching players {api_offset + 1}-{min(api_offset + batch_size, total_players_needed)} of {total_players_needed}...")
                        
                        # Get page data
                        page_data = self.api.get_rankings(api_offset, batch_size)
                        if not page_data:
                            break
                            
                        # Add rank to each player based on offset
                        for i, player in enumerate(page_data):
                            player['rank'] = api_offset + i + 1
                        rankings.extend(page_data)
                        
                        # Update display after each batch if we have data
                        if len(rankings) >= settings.UI_PAGE_SIZE:
                            self.rankings_data = rankings
                            self.current_page = 0
                            self.after(0, self.display_rankings)
                        
                        # Rate limiting between requests
                        time.sleep(settings.REQUEST_DELAY)
                        
                        # If we have enough players for the requested UI pages, stop
                        if len(rankings) >= total_players_needed:
                            break
                        
                    # Final update
                    if rankings:
                        # Trim to exact number of players needed for UI pages
                        self.rankings_data = rankings[:total_players_needed]
                        self.current_page = 0
                        self.after(0, self.display_rankings)
                        self.after(0, lambda: self.update_progress(f"Loaded {len(self.rankings_data)} players ({ui_pages} pages)"))
                    else:
                        self.after(0, lambda: self.show_error("No rankings data received"))
                    
                except Exception as e:
                    logger.error("rankings_fetch_error", error=str(e))
                    self.after(0, lambda: self.show_error(f"Failed to fetch rankings: {str(e)}"))
                
                finally:
                    # Re-enable controls
                    self.after(0, lambda: self.get_rankings_button.configure(state="normal"))
                    self.after(0, lambda: self.ranking_pages_entry.configure(state="normal"))
                    self.after(0, self.spinner.stop)
            
            thread = threading.Thread(target=fetch_task)
            thread.daemon = True
            thread.start()
            
        except ValueError:
            self.show_error("Please enter a valid number")

    def clean_cache(self):
        """Clean all caches."""
        try:
            self.api.player_cache.clean_cache()
            self.api.replay_cache.clean_cache()
            self.update_progress("Cache cleared successfully")
            # Update both the cache info and status bar
            self._update_cache_info()
            self.status_bar.update_status("Cache cleared successfully")
        except Exception as e:
            logger.error("Failed to clear cache", error=str(e))
            self.show_error(f"Failed to clear cache: {str(e)}")

    def load_player_stats(self):
        """Load player stats for all displayed players."""
        if not self.rankings_data:
            self.show_error("No players to load stats for")
            return
            
        # Disable the load stats button during loading
        self.load_stats_button.configure(state="disabled")
        self.spinner.start()
        
        def load_stats_task():
            try:
                self.update_progress("Loading player stats...")
                
                # Get current page data
                start_idx = self.current_page * 15
                page_data = self.rankings_data[start_idx:start_idx + 15]
                
                # Load stats for each player on the current page
                for i, player in enumerate(page_data):
                    username = player.get('name')
                    if not username:
                        continue
                        
                    self.update_progress(f"Loading stats for {username}...")
                    
                    try:
                        # Fetch replay stats for the player
                        replay_response = self.api.get_player_replays(username)
                        
                        # Update player data with stats
                        if replay_response and replay_response.get('res') == 'OK':
                            # Extract replay results
                            replay_results = replay_response.get('results', {}).get('results', [])
                            
                            # Calculate stats from replay results
                            stats_calculator = ReplayStats()
                            replay_stats = stats_calculator.calculate_stats(replay_results, username)
                            
                            if replay_stats:
                                # Update player data with calculated stats
                                player['replay_stats'] = replay_stats
                                # Update the display immediately for each player
                                self.after(0, self.display_rankings)
                        
                        # Small delay between requests
                        time.sleep(settings.REQUEST_DELAY)
                        
                    except Exception as e:
                        logger.error(f"Failed to load stats for {username}", error=str(e))
                        continue
                
                self.after(0, lambda: self.update_progress("Stats loaded successfully"))
                
            except Exception as e:
                logger.error("stats_loading_error", error=str(e))
                self.after(0, lambda: self.show_error(f"Failed to load stats: {str(e)}"))
                
            finally:
                # Re-enable the load stats button
                self.after(0, lambda: self.load_stats_button.configure(state="normal"))
                self.after(0, self.spinner.stop)
        
        # Start loading stats in a separate thread
        thread = threading.Thread(target=load_stats_task)
        thread.daemon = True
        thread.start()
        
        logger.info("stats_loading_started")
