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
from .api import FightcadeAPI
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
    
    def update_cache_info(self, stats: Dict):
        """Update cache statistics."""
        if stats['is_valid']:
            text = f"Cache: {stats['total_players']} players, {stats['size_bytes']/1024:.1f}KB"
        else:
            text = "Cache: Invalid"
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
        self.sort_column = None
        self.sort_ascending = True
        
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
        
        # Add tooltips
        self._add_tooltip(self.search_entry, "Enter player name to search")
        self._add_tooltip(self.clear_button, "Clear search (Esc)")
        self._add_tooltip(self.search_button, "Search for player (Enter)")
    
    def _create_content_frame(self):
        """Create the main content frame with results table."""
        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        
        # Table headers with sorting
        headers = [
            ("Rank", "rank"),
            ("ELO", "elo"),
            ("Player", "name"),
            ("Country", "country"),
            ("Matches", "matches"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "winrate"),
            ("Time (hrs)", "time")
        ]
        
        header_frame = ctk.CTkFrame(content)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        for i, (header, key) in enumerate(headers):
            frame = ctk.CTkFrame(header_frame)
            frame.grid(row=0, column=i, sticky="ew", padx=2)
            frame.grid_columnconfigure(0, weight=1)
            
            label = ctk.CTkLabel(
                frame,
                text=header,
                font=("Helvetica", 12, "bold"),
                cursor="hand2"
            )
            label.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
            label.bind("<Button-1>", lambda e, k=key: self._sort_rankings(k))
            
            self._add_tooltip(label, f"Click to sort by {header}")
        
        # Results frame with scrollbar
        self.results_frame = ctk.CTkScrollableFrame(content)
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
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
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
    
    def _update_cache_info(self):
        """Update cache information in status bar."""
        stats = self.api.cache.get_stats()
        self.status_bar.update_cache_info(stats)
    
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
                player, offset = self.api.search_player(
                    username,
                    lambda msg: self.after(0, self.update_progress, msg)
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
        
        start_idx = self.current_page * settings.PAGE_SIZE
        page_data = self.rankings_data[start_idx:start_idx + settings.PAGE_SIZE]
        
        # Create headers
        headers = ["Rank", "ELO", "Player", "Country", "Matches", "Wins", "Losses", "Win Rate", "Time (hrs)"]
        for j, text in enumerate(headers):
            label = ctk.CTkLabel(self.results_frame, text=text, font=("Helvetica", 12, "bold"))
            label.grid(row=0, column=j, sticky="ew", padx=5, pady=5)
        
        for i, player in enumerate(page_data, 1):
            # Use the found_rank from search result instead of API rank
            rank = player.get('found_rank', player.get('rank', 0))
            
            # Extract country info
            country = player.get('country', {})
            country_code = country.get('iso_code', '').lower() if isinstance(country, dict) else ''
            
            # Get game info with proper fallbacks
            game_info = player.get('gameinfo', {}).get('kof2002', {})
            matches = game_info.get('num_matches', 0)
            wins = game_info.get('wins', 0)
            losses = game_info.get('losses', 0)
            time_played = round(game_info.get('time_played', 0) / 3600, 1)  # Convert to hours
            win_rate = (wins / matches) if matches > 0 else 0
            
            # Create rank label
            rank_label = ctk.CTkLabel(self.results_frame, text=str(rank))
            rank_label.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            
            # Create ELO rank image label
            elo_rank = min(6, max(1, (rank // 100) + 1))  # Convert rank to ELO tier (1-6)
            rank_image = self._load_rank_image(elo_rank)
            if rank_image:
                elo_label = ctk.CTkLabel(self.results_frame, text="", image=rank_image)
                elo_label.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
                self._add_tooltip(elo_label, f"Rank Tier {elo_rank}")
            
            # Create player name label
            name_label = ctk.CTkLabel(self.results_frame, text=player.get('name', ''))
            name_label.grid(row=i, column=2, sticky="ew", padx=5, pady=2)
            
            # Create country flag label
            if country_code:
                flag_image = self._load_flag_image(country_code)
                if flag_image:
                    flag_label = ctk.CTkLabel(self.results_frame, text="", image=flag_image)
                    flag_label.grid(row=i, column=3, sticky="ew", padx=5, pady=2)
                    self._add_tooltip(flag_label, country.get('name', country_code.upper()))
                else:
                    # Fallback to text if flag not found
                    flag_label = ctk.CTkLabel(self.results_frame, text=country_code.upper())
                    flag_label.grid(row=i, column=3, sticky="ew", padx=5, pady=2)
            else:
                flag_label = ctk.CTkLabel(self.results_frame, text="")
                flag_label.grid(row=i, column=3, sticky="ew", padx=5, pady=2)
            
            # Add remaining stats
            stats = [
                str(matches),
                str(wins),
                str(losses),
                f"{win_rate:.2%}",
                str(time_played)
            ]
            
            for j, text in enumerate(stats, 4):
                label = ctk.CTkLabel(self.results_frame, text=text)
                label.grid(row=i, column=j, sticky="ew", padx=5, pady=2)
        
        # Update navigation
        total_pages = (len(self.rankings_data) - 1) // settings.PAGE_SIZE + 1
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
    
    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_rankings()
    
    def next_page(self):
        """Go to next page."""
        total_pages = (len(self.rankings_data) - 1) // settings.PAGE_SIZE + 1
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
    
    def _sort_rankings(self, key):
        """Sort rankings by the specified key."""
        if not self.rankings_data:
            return
            
        if self.sort_column == key:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = key
            self.sort_ascending = True
        
        def get_sort_key(player):
            if key == 'rank':
                return int(player.get('rank', 0))
            elif key == 'name':
                return player.get('name', '').lower()
            elif key == 'country':
                country = player.get('country', {})
                return country.get('iso_code', '') if isinstance(country, dict) else ''
            elif key in ['matches', 'wins', 'losses']:
                return int(player.get('gameinfo', {}).get('kof2002', {}).get(key, 0))
            elif key == 'winrate':
                game_info = player.get('gameinfo', {}).get('kof2002', {})
                wins = game_info.get('wins', 0)
                matches = game_info.get('num_matches', 0)
                return (wins / matches) if matches > 0 else 0
            elif key == 'time':
                return float(player.get('gameinfo', {}).get('kof2002', {}).get('time_played', 0))
            return 0
        
        self.rankings_data.sort(
            key=get_sort_key,
            reverse=not self.sort_ascending
        )
        self.display_rankings()
    
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
