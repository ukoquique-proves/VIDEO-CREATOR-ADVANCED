"""
JSON Logging Formatter for Structured Logs

Provides JSON formatted output for structured logging with request IDs,
timestamps, and contextual data for better observability and debugging.
"""

import json
import logging
import traceback
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                # Skip standard logging attributes
                if key not in {
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'message', 'pathname', 'process', 'processName', 'relativeCreated',
                    'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                    'asctime', 'taskName'
                }:
                    log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, default=str)


def setup_json_logging(log_file: str = None, log_level: int = logging.INFO) -> None:
    """
    Configure JSON logging for the application.
    
    Args:
        log_file: Path to write JSON logs. If None, only console logging.
        log_level: Logging level (default: INFO)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create JSON formatter
    json_formatter = JSONFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(json_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"Could not create file handler for {log_file}: {e}")


def get_structured_logger(name: str) -> logging.Logger:
    """Get a logger configured for structured JSON output."""
    return logging.getLogger(name)
