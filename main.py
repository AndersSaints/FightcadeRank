"""
Main entry point for the FightcadeRank application.
"""
import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.append(str(src_dir))

from src.ui import FCRankApp
from src.logger import setup_logging

logger = setup_logging()

def main():
    try:
        app = FCRankApp()
        app.mainloop()
    except Exception as e:
        logger.error("application_error", error=str(e))
        raise

if __name__ == "__main__":
    main()
