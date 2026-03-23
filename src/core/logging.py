"""
Logging configuration and utilities for MetricFlow.

Provides structured logging with JSON support, log levels, and formatters.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime
import json
import threading


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Outputs logs as JSON for easy parsing by log aggregation systems.
    """
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if self.include_extra:
            extra = {k: v for k, v in record.__dict__.items() 
                    if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__}
            if extra:
                log_data["extra"] = extra
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output.
    
    Adds color coding based on log level.
    """
    
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.name = f"{color}{record.name}{self.RESET}"
        return super().format(record)


class ContextFilter(logging.Filter):
    """
    Context filter for adding request-specific information.
    
    Allows adding contextual information to all log records.
    """
    
    _context: Dict[str, Any] = {}
    _lock = threading.Lock()
    
    @classmethod
    def set_context(cls, key: str, value: Any) -> None:
        """Set context value."""
        with cls._lock:
            cls._context[key] = value
    
    @classmethod
    def clear_context(cls) -> None:
        """Clear all context."""
        with cls._lock:
            cls._context.clear()
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to record."""
        for key, value in self._context.items():
            setattr(record, key, value)
        return True


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    json_logs: bool = False,
    debug: bool = False
) -> logging.Logger:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging
        json_logs: Use JSON format for logs
        debug: Enable debug mode
    
    Returns:
        Configured logger instance
    """
    if debug:
        level = "DEBUG"
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if json_logs:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_formatter = ColoredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
    
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        if json_logs:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            )
            file_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
    
    # Add context filter
    logger.addFilter(ContextFilter())
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for adding temporary context to logs.
    
    Usage:
        with LogContext(request_id="123"):
            logger.info("Processing request")
    """
    
    def __init__(self, **kwargs: Any):
        self.context = kwargs
    
    def __enter__(self) -> None:
        for key, value in self.context.items():
            ContextFilter.set_context(key, value)
    
    def __exit__(self, *args: Any) -> None:
        ContextFilter.clear_context()


def log_function_call(func):
    """
    Decorator to log function calls with arguments and results.
    
    Usage:
        @log_function_call
        def my_function(a, b):
            return a + b
    """
    import functools
    import traceback
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(
            f"Calling {func.__name__} with args={args}, kwargs={kwargs}"
        )
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(
                f"{func.__name__} raised {type(e).__name__}: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            raise
    
    return wrapper