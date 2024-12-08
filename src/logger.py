"""
Logging configuration for the application.
"""
import structlog
import sys
from datetime import datetime
from pathlib import Path
from .config import settings

def setup_logging():
    """Configure structured logging for the application."""
    
    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = settings.LOG_DIR / f"fightcade_rank_{timestamp}.log"
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create file handler
    file_handler = open(log_file, "a")
    
    # Create console handler
    console_handler = sys.stdout
    
    def log_processor(logger, method_name, event_dict):
        """Process log messages and route them to appropriate outputs."""
        # Format the message
        message = structlog.processors.JSONRenderer()(logger, method_name, event_dict)
        
        # Write to file
        file_handler.write(message + "\n")
        file_handler.flush()
        
        # Write to console if in debug mode
        if settings.DEBUG:
            console_handler.write(message + "\n")
            console_handler.flush()
        
        return event_dict
    
    # Add our custom processor
    structlog.configure(processors=[log_processor])
    
    return structlog.get_logger()
