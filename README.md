# Fightcade KOF 2002 Rank

A Windows application to view and track King of Fighters 2002 rankings from Fightcade.

## Features

- Modern, dark-themed GUI
- User-friendly interface
- Real-time ranking search
- Pagination support
- Error handling
- Clean display of player rankings

## Installation

1. Make sure you have Python 3.8 or higher installed
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

Simply run the main.py file:
```bash
python main.py
```

## Usage

1. Launch the application
2. Enter your Fightcade username
3. Click "Login" to view rankings
4. Use "Previous" and "Next" buttons to navigate through pages
5. Click "Find Me" to refresh the rankings

## Dependencies

- customtkinter==5.2.0
- requests==2.31.0
- Pillow==10.0.0
- python-dotenv==1.0.0

## Notes

- The application requires an internet connection to fetch ranking data
- Rankings are fetched from the Fightcade API
- The interface displays 10 results per page
