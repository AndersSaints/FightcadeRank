# FightcadeRank

A desktop application for searching and viewing Fightcade KOF 2002 player rankings.

## Features

- Fast player search with caching
- Disk-based cache persistence
- Modern dark-themed UI
- Loading animations and progress indicators
- Status bar with cache information
- Keyboard shortcuts
- Structured logging
- Rate limit handling
- Error recovery

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AndersSaints/FightcadeRank.git
cd FightcadeRank
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

### Keyboard Shortcuts

- `Enter`: Search for player
- `Ctrl+F`: Focus search box

### Configuration

Settings can be modified in `src/config.py`:

- Cache duration
- Search batch size
- Rate limit delays
- UI settings
- Debug options

## Project Structure

```
FightcadeRank/
├── main.py           # Application entry point
├── requirements.txt  # Project dependencies
├── src/             # Source code
│   ├── __init__.py  # Package initialization
│   ├── api.py       # Fightcade API client
│   ├── cache.py     # Cache implementation
│   ├── config.py    # Configuration settings
│   ├── logger.py    # Logging setup
│   └── ui.py        # User interface
├── cache/           # Cache storage
└── logs/            # Application logs
```

## Development

The project uses:
- `customtkinter` for the modern UI
- `cloudscraper` for API requests
- `structlog` for structured logging
- `pydantic` for settings management

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
