# FightcadeRank 🎮

<div align="center">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/AndersSaints/FightcadeRank)
![GitHub](https://img.shields.io/github/license/AndersSaints/FightcadeRank)
![Python Version](https://img.shields.io/badge/python-3.10+-blue)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A sleek desktop application for tracking and analyzing Fightcade KOF 2002 player rankings with real-time updates and intelligent rank determination.

[Features](#features) •
[Installation](#installation) •
[Usage](#usage) •
[Development](#development) •
[Contributing](#contributing)

</div>

## ✨ Features

### Core Features
- 🔍 **Fast Player Search** with intelligent caching
- 🎯 **Smart Rank System**
  - Rank 6: Top 15 players (first page)
  - Rank 5: Players 16-110 (up to page 7)
  - Rank 4: Players 111-1250 (up to page 84)
  - Rank 3: Players 1251+ (page 84 onwards)
- 📊 **Detailed Statistics** including matches, wins, and time played
- 🌍 **Country Recognition** with flag display
- 📱 **Page Tracking** showing which page each player appears on

### Technical Features
- 💾 Disk-based cache persistence
- 🌙 Modern dark-themed UI using CustomTkinter
- ⚡ Loading animations and progress indicators
- 📈 Status bar with cache information
- ⌨️ Keyboard shortcuts for efficiency
- 📝 Structured logging system
- 🔄 Rate limit handling and error recovery

## 🚀 Installation

### Option 1: Direct Download (Recommended)
1. Download the latest release from [Releases](https://github.com/AndersSaints/FightcadeRank/releases)
2. Extract the ZIP file
3. Run `FightcadeRank.exe`

### Option 2: From Source
```bash
# Clone the repository
git clone https://github.com/AndersSaints/FightcadeRank.git
cd FightcadeRank

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m src.ui
```

## 🎮 Usage

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Enter` | Search for player |
| `Ctrl+F` | Focus search box |
| `Esc` | Clear search |

### Configuration
Settings can be modified in `src/config.py`:
```python
CACHE_DURATION = 3600  # Cache duration in seconds
BATCH_SIZE = 100      # Players per API request
REQUEST_DELAY = 0.5   # Delay between requests
UI_PAGE_SIZE = 15     # Players per UI page
```

## 🏗️ Project Structure

```
FightcadeRank/
├── src/                # Source code
│   ├── __init__.py    # Package initialization
│   ├── api.py         # Fightcade API client
│   ├── cache.py       # Cache implementation
│   ├── config.py      # Configuration settings
│   ├── logger.py      # Logging setup
│   └── ui.py          # User interface
├── cache/             # Cache storage
├── logs/              # Application logs
├── rank/              # Rank images
└── flags/             # Country flag images
```

## 🛠️ Development

### Tech Stack
- **UI**: `customtkinter` for modern theming
- **Networking**: `cloudscraper` for API requests
- **Logging**: `structlog` for structured logs
- **Settings**: `pydantic` for configuration
- **Distribution**: `pyinstaller` for executable building

### Building from Source
```bash
# Install development dependencies
pip install pyinstaller

# Build executable
pyinstaller fightcade_rank.spec
```

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Fightcade team for their amazing platform
- The KOF 2002 community for their continued support

---
<div align="center">
Made with ❤️ by <a href="https://github.com/AndersSaints">AndersSaints</a>
</div>
