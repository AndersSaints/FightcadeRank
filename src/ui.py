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
                                  bg=self._fg_color, highlightthickness=0)
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
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize variables
        self.search_thread = None
        self.rankings_data = []
        self.current_page = 0
        self.total_players = 0
        
        # Configure grid
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
        
        # Update cache info
        self._update_cache_info()
        
        logger.info("ui_initialized")
    
    def _create_header_frame(self):
        """Create the header frame with search controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        # Search entry
        self.search_entry = ctk.CTkEntry(
            header, 
            placeholder_text="Enter player name...",
            width=200
        )
        self.search_entry.pack(side="left", padx=5)
        
        # Search button
        self.search_button = ctk.CTkButton(
            header,
            text="Search",
            command=self.search_player
        )
        self.search_button.pack(side="left", padx=5)
        
        # Loading spinner
        self.spinner = LoadingSpinner(header)
        self.spinner.pack(side="left", padx=5)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(header, text="")
        self.progress_label.pack(side="left", padx=5)
    
    def _create_content_frame(self):
        """Create the main content frame with results table."""
        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Configure grid
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        
        # Headers
        headers = ["Rank", "Player", "Country", "Matches", "Wins", "Losses", "Time Played"]
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(content, text=header, font=("Arial", 12, "bold"))
            label.grid(row=0, column=i, sticky="ew", padx=5, pady=5)
        
        # Results frame with scrollbar
        self.results_frame = ctk.CTkScrollableFrame(content)
        self.results_frame.grid(row=1, column=0, columnspan=len(headers), 
                              sticky="nsew", padx=5, pady=5)
        
        # Navigation frame
        nav_frame = ctk.CTkFrame(content)
        nav_frame.grid(row=2, column=0, columnspan=len(headers), 
                      sticky="ew", padx=5, pady=5)
        
        # Previous page button
        self.prev_button = ctk.CTkButton(
            nav_frame,
            text="Previous",
            command=self.prev_page,
            state="disabled"
        )
        self.prev_button.pack(side="left", padx=5)
        
        # Page info
        self.page_label = ctk.CTkLabel(nav_frame, text="Page 0 of 0")
        self.page_label.pack(side="left", padx=5)
        
        # Next page button
        self.next_button = ctk.CTkButton(
            nav_frame,
            text="Next",
            command=self.next_page,
            state="disabled"
        )
        self.next_button.pack(side="left", padx=5)
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
    
    def _update_cache_info(self):
        """Update cache information in status bar."""
        stats = self.api.cache.get_cache_stats()
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
                player, rank = self.api.search_player(
                    username,
                    lambda msg: self.after(0, self.update_progress, msg)
                )
                
                if player:
                    self.rankings_data = [player]
                    self.current_page = 0
                    self.after(0, self.display_rankings)
                
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
        
        for i, player in enumerate(page_data):
            rank = start_idx + i + 1
            row = [
                str(rank),
                player.get('name', ''),
                player.get('country', ''),
                str(player.get('gameinfo', {}).get('kof2002', {}).get('num_matches', 0)),
                str(player.get('gameinfo', {}).get('kof2002', {}).get('wins', 0)),
                str(player.get('gameinfo', {}).get('kof2002', {}).get('losses', 0)),
                str(player.get('gameinfo', {}).get('kof2002', {}).get('time_played', 0))
            ]
            
            for j, text in enumerate(row):
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
        self.progress_label.configure(text=message)
        self.status_bar.update_status(message)
    
    def show_error(self, message: str):
        """Show error message."""
        self.progress_label.configure(text=f"Error: {message}")
        self.status_bar.update_status(f"Error: {message}")
        logger.error("error_displayed", message=message)
