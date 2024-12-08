import customtkinter as ctk
import cloudscraper
from PIL import Image, ImageTk
import os
import sys
from datetime import datetime
import json
import threading
import time

class FightcadeAPI:
    def __init__(self):
        # Configure cloudscraper with more robust settings
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            },
            debug=True
        )
        
        # Add essential headers
        self.scraper.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://www.fightcade.com',
            'Referer': 'https://www.fightcade.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        })
        
        self.base_url = 'https://www.fightcade.com/api/'
        self._init_session()
    
    def _init_session(self):
        """Initialize session by visiting the main page first"""
        try:
            # First visit the main page
            response = self.scraper.get('https://www.fightcade.com/')
            response.raise_for_status()
            
            # Save debug information
            with open('debug_request.txt', 'w') as f:
                f.write(f"Main page request:\n")
                f.write(f"Status Code: {response.status_code}\n")
                f.write(f"Headers: {dict(response.headers)}\n")
                f.write(f"Cookies: {dict(response.cookies)}\n")
            
            time.sleep(2)  # Give time for any JS to execute
        except Exception as e:
            print(f"Error initializing session: {e}")
            raise

    def _make_request(self, data, max_retries=3):
        """Make an API request with retry logic"""
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                response = self.scraper.post(self.base_url, json=data)
                response.raise_for_status()
                
                # Save debug information
                with open(f'debug_response_{retry_count}.txt', 'w') as f:
                    f.write(f"Request data: {data}\n")
                    f.write(f"Status Code: {response.status_code}\n")
                    f.write(f"Headers: {dict(response.headers)}\n")
                    f.write(f"Content: {response.text}\n")
                
                result = response.json()
                return result
                
            except Exception as e:
                last_error = e
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(5 * retry_count)
                    self._init_session()  # Reinitialize session before retry
        
        raise Exception(f"Request failed after {max_retries} attempts. Last error: {str(last_error)}")

    def get_user(self, username):
        """Get user information"""
        data = {
            "req": "getuser",
            "username": username
        }
        return self._make_request(data)

    def search_rankings(self, offset=0, limit=15):
        """Search rankings with pagination"""
        data = {
            "req": "searchrankings",
            "offset": offset,
            "limit": limit,
            "gameid": "kof2002",
            "byElo": True,
            "recent": True
        }
        return self._make_request(data)

    def search_player(self, player_name, progress_callback=None):
        if not player_name:
            raise ValueError("Player name cannot be empty")

        try:
            total_players = self.get_total_players()
            if progress_callback:
                progress_callback(f"Searching through {total_players} players...")

            page = 0
            limit = 15
            max_retries = 3
            
            while page * limit < total_players:
                if progress_callback:
                    progress_callback(f"Searching page {page + 1}...")

                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = self.search_rankings(page * limit, limit)
                        if response.get('res') != 'OK':
                            raise Exception(f"API Error: {response.get('error', 'Unknown error')}")

                        players = response.get('results', {}).get('items', [])
                        for player in players:
                            if player.get('name', '').lower() == player_name.lower():
                                return {
                                    'name': player.get('name'),
                                    'rank': player.get('rank'),
                                    'elo': player.get('elo'),
                                    'wins': player.get('wins'),
                                    'losses': player.get('losses'),
                                    'country': player.get('country'),
                                    'total_games': player.get('wins', 0) + player.get('losses', 0),
                                    'page': page + 1,
                                    'total_pages': (total_players + limit - 1) // limit
                                }
                        break  # Success, move to next page
                        
                    except Exception as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            raise Exception(f"Error on page {page + 1}: {str(e)}")
                        time.sleep(2 * retry_count)
                        self._init_session()  # Create new scraper instance for retry

                page += 1
                time.sleep(0.5)  # Add delay between pages to prevent rate limiting

            return None
        except Exception as e:
            raise Exception(f"Error searching for player: {str(e)}")

    def get_total_players(self):
        try:
            response = self.search_rankings(0, 1)
            if response and response.get('res') == 'OK':
                return response.get('results', {}).get('total', 0)
            return 0
        except Exception as e:
            print(f"Error getting total players: {str(e)}")
            return 0

    def search_user(self, username):
        data = {
            "req": "searchuser",
            "username": username
        }
        response = self.scraper.post(self.base_url, json=data)
        response.raise_for_status()
        return response.json()

def search_player(player_name, progress_callback=None):
    def update_progress(message):
        if progress_callback:
            progress_callback(message)
        print(message)
    
    try:
        update_progress("Searching for player...")
        api = FightcadeAPI()
        
        # Get total number of players
        total_players = api.get_total_players()
        
        # First, get the rankings to find the player's rank
        rankings_data = []
        offset = 0
        limit = 15
        found_player = False
        player_info = None
        current_page = 1
        
        while not found_player:
            response = api.search_rankings(offset, limit)
            if not response or response.get('res') != 'OK':
                break
                
            results = response.get('results', {}).get('results', [])
            if not results:
                break
                
            for player in results:
                if player.get('name', '').lower() == player_name.lower():
                    found_player = True
                    player_info = player
                    break
                    
            if not found_player:
                offset += limit
                current_page += 1
                if offset > total_players:  # Search through all players
                    break
        
        if not found_player:
            # If not in rankings, try direct user search
            user_response = api.get_user(player_name)
            if not user_response or user_response.get('res') != 'OK':
                raise Exception(f"Player '{player_name}' not found")
            
            user_data = user_response.get('user', {})
            game_info = user_data.get('gameinfo', {}).get('kof2002', {})
            
            formatted_data = [{
                "rank": game_info.get('rank', 'N/A'),
                "username": user_data.get('name', ''),
                "country": user_data.get('country', ''),
                "matches": game_info.get('num_matches', 0),
                "wins": game_info.get('wins', 0),
                "losses": game_info.get('losses', 0),
                "time_played": game_info.get('time_played', 0),
                "page": "Not ranked",
                "total_pages": total_players // limit + 1
            }]
        else:
            # Use the data from rankings
            formatted_data = [{
                "rank": offset + results.index(player_info) + 1,
                "username": player_info.get('name', ''),
                "country": player_info.get('country', ''),
                "matches": player_info.get('gameinfo', {}).get('kof2002', {}).get('num_matches', 0),
                "wins": player_info.get('gameinfo', {}).get('kof2002', {}).get('wins', 0),
                "losses": player_info.get('gameinfo', {}).get('kof2002', {}).get('losses', 0),
                "time_played": player_info.get('gameinfo', {}).get('kof2002', {}).get('time_played', 0),
                "page": current_page,
                "total_pages": total_players // limit + 1
            }]
        
        update_progress(f"Search completed! Found on page {formatted_data[0]['page']}")
        return formatted_data
            
    except Exception as e:
        error_message = str(e)
        update_progress(f"Error during search: {error_message}")
        return []

class FCRankApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Fightcade KOF 2002 Rankings")
        self.geometry("1200x800")
        self.minsize(1000, 600)
        
        # Set theme and colors
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize variables
        self.search_thread = None
        self.user_data = []
        self.current_page = 0
        self.page_size = 15
        self.total_players = 0
        self.rankings_data = []
        
        # Configure main window grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create frames
        self.create_header_frame()
        self.create_content_frame()
        
        # Initialize API
        self.api = FightcadeAPI()
        
    def create_header_frame(self):
        # Header frame
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20,0))
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title = ctk.CTkLabel(self.header_frame, text="KOF 2002 Rankings", font=("Arial", 24, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Search frame
        search_frame = ctk.CTkFrame(self.header_frame)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        search_frame.grid_columnconfigure(0, weight=1)
        
        # Search entry
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Enter username")
        self.search_entry.grid(row=0, column=0, padx=(20,10), pady=10, sticky="ew")
        
        # Search button
        self.search_button = ctk.CTkButton(search_frame, text="Search", command=self.search_player)
        self.search_button.grid(row=0, column=1, padx=(10,20), pady=10)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(self.header_frame, text="")
        self.progress_label.grid(row=2, column=0, columnspan=2, pady=5)

    def create_content_frame(self):
        # Main content frame
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # Rankings frame
        self.rankings_frame = ctk.CTkScrollableFrame(self.content_frame)
        self.rankings_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.rankings_frame.grid_columnconfigure(0, weight=1)
        
        # Pagination frame
        self.pagination_frame = ctk.CTkFrame(self.content_frame)
        self.pagination_frame.grid(row=1, column=0, sticky="ew", pady=(10,0))
        
        # Previous page button
        self.prev_button = ctk.CTkButton(self.pagination_frame, text="Previous", command=self.prev_page)
        self.prev_button.grid(row=0, column=0, padx=10, pady=10)
        
        # Page info label
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Page 1")
        self.page_label.grid(row=0, column=1, padx=20)
        
        # Next page button
        self.next_button = ctk.CTkButton(self.pagination_frame, text="Next", command=self.next_page)
        self.next_button.grid(row=0, column=2, padx=10, pady=10)

    def display_rankings(self):
        # Clear previous rankings
        for widget in self.rankings_frame.winfo_children():
            widget.destroy()
            
        # Create headers
        headers = ["Rank", "Player", "Country", "ELO", "Matches", "Time Played"]
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(self.rankings_frame, text=header, font=("Arial", 12, "bold"))
            label.grid(row=0, column=i, padx=5, pady=5, sticky="w")
        
        # Calculate start and end indices for current page
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.rankings_data))
        
        # Display rankings for current page
        for i, player in enumerate(self.rankings_data[start_idx:end_idx], 1):
            # Rank number (calculated from position in data)
            rank_num = start_idx + i
            rank_label = ctk.CTkLabel(self.rankings_frame, text=str(rank_num))
            rank_label.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            
            # Player name
            name = player.get('name', 'N/A')
            name_label = ctk.CTkLabel(self.rankings_frame, 
                                    text=name,
                                    text_color="green" if name.lower() == self.search_entry.get().strip().lower() else None)
            name_label.grid(row=i, column=1, padx=5, pady=2, sticky="w")
            
            # Country
            country = player.get('country', {}).get('iso_code', 'N/A')
            country_label = ctk.CTkLabel(self.rankings_frame, text=country)
            country_label.grid(row=i, column=2, padx=5, pady=2, sticky="w")
            
            # Game info
            game_info = player.get('gameinfo', {}).get('kof2002', {})
            
            # ELO
            elo = game_info.get('elo', 'N/A')
            elo_label = ctk.CTkLabel(self.rankings_frame, text=str(elo))
            elo_label.grid(row=i, column=3, padx=5, pady=2, sticky="w")
            
            # Matches
            matches = game_info.get('num_matches', 'N/A')
            matches_label = ctk.CTkLabel(self.rankings_frame, text=str(matches))
            matches_label.grid(row=i, column=4, padx=5, pady=2, sticky="w")
            
            # Time played
            time_played = game_info.get('time_played', 0)
            if time_played:
                hours = int(float(time_played) / 3600)
                time_text = f"{hours}H"
            else:
                time_text = 'N/A'
            time_label = ctk.CTkLabel(self.rankings_frame, text=time_text)
            time_label.grid(row=i, column=5, padx=5, pady=2, sticky="w")
        
        # Update pagination
        total_pages = (len(self.rankings_data) + self.page_size - 1) // self.page_size
        self.page_label.configure(text=f"Page {self.current_page + 1} of {total_pages}")
        self.prev_button.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

    def search_player(self, username=None):
        if username is None:
            username = self.search_entry.get().strip()
        
        if not username:
            self.show_error("Please enter a username")
            return
            
        self.search_button.configure(state="disabled")
        self.progress_label.configure(text="Searching...")
        self.rankings_data = []  # Clear previous results
        
        def search_task():
            try:
                # First try to get user info
                user_data = {
                    "req": "getuser",
                    "username": username
                }
                
                response = self.api.scraper.post(self.api.base_url, json=user_data)
                response.raise_for_status()
                user_result = response.json()
                
                if user_result.get('res') != 'OK':
                    self.progress_label.configure(text=f"User '{username}' not found")
                    return
                
                def search_in_rankings(offset=0, limit=100):
                    self.progress_label.configure(text=f"Searching page {(offset//limit) + 1}...")
                    
                    # Get rankings for current page
                    rank_data = {
                        "req": "searchrankings",
                        "offset": offset,
                        "limit": limit,
                        "gameid": "kof2002",
                        "byElo": True,
                        "recent": True
                    }
                    
                    response = self.api.scraper.post(self.api.base_url, json=rank_data)
                    response.raise_for_status()
                    rank_result = response.json()
                    
                    if rank_result.get('res') == 'OK':
                        results = rank_result.get('results', {})
                        players = results.get('results', [])
                        total_count = results.get('count', 0)
                        
                        # Process current page results
                        for player in players:
                            self.rankings_data.append(player)
                            if player['name'].lower() == username.lower():
                                return True  # Player found
                        
                        # If player not found and there are more pages, continue searching
                        if len(self.rankings_data) < total_count and offset + limit < total_count:
                            return search_in_rankings(offset + limit, limit)
                        
                        return False  # Player not found in any page
                    
                    return False  # API error
                
                # Start the recursive search
                found = search_in_rankings()
                
                if found:
                    # Find the index of the player to calculate their page
                    player_index = next(i for i, p in enumerate(self.rankings_data) 
                                     if p['name'].lower() == username.lower())
                    self.current_page = player_index // self.page_size
                    self.after(0, self.display_rankings)
                    self.progress_label.configure(text=f"Player found on page {self.current_page + 1}")
                else:
                    self.progress_label.configure(text=f"Player '{username}' not found in rankings")
                
            except Exception as e:
                self.progress_label.configure(text=f"Error: {str(e)}")
                print(f"Search error: {str(e)}")  # Log the error for debugging
            finally:
                self.search_button.configure(state="normal")
        
        self.search_thread = threading.Thread(target=search_task)
        self.search_thread.daemon = True
        self.search_thread.start()

    def update_progress(self, message):
        self.progress_label.configure(text=message)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_rankings()

    def next_page(self):
        total_pages = (len(self.rankings_data) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_rankings()

    def show_error(self, message):
        self.progress_label.configure(text=message)

if __name__ == "__main__":
    try:
        app = FCRankApp()
        app.mainloop()
    except Exception as e:
        print(f"Error: {str(e)}")
