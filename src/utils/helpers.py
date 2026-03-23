"""
Utility functions for MetricFlow.

Contains helper functions for common operations.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import json
import re
from functools import wraps


def parse_duration(duration: str) -> timedelta:
    """
    Parse duration string to timedelta.
    
    Examples:
        "1h" -> 1 hour
        "30m" -> 30 minutes
        "7d" -> 7 days
    
    Args:
        duration: Duration string
        
    Returns:
        timedelta object
    """
    pattern = r"(\d+)([smhd])"
    match = re.match(pattern, duration)
    
    if not match:
        raise ValueError(f"Invalid duration format: {duration}")
    
    value, unit = match.groups()
    value = int(value)
    
    units = {
        "s": lambda v: timedelta(seconds=v),
        "m": lambda v: timedelta(minutes=v),
        "h": lambda v: timedelta(hours=v),
        "d": lambda v: timedelta(days=v),
    }
    
    return units[unit](value)


def format_bytes(bytes: int) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        bytes: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"


def format_number(number: float, decimals: int = 2) -> str:
    """
    Format number with thousand separators.
    
    Args:
        number: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    if number is None:
        return "N/A"
    
    if abs(number) >= 1_000_000:
        return f"{number/1_000_000:.{decimals}f}M"
    elif abs(number) >= 1_000:
        return f"{number/1_000:.{decimals}f}K"
    else:
        return f"{number:.{decimals}f}"


def parse_tags(tag_string: str) -> Dict[str, str]:
    """
    Parse tag string to dictionary.
    
    Args:
        tag_string: Comma-separated key=value pairs
        
    Returns:
        Dictionary of tags
    """
    if not tag_string:
        return {}
    
    tags = {}
    for pair in tag_string.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            tags[key.strip()] = value.strip()
    
    return tags


def format_tags(tags: Dict[str, str]) -> str:
    """
    Format tags dictionary to string.
    
    Args:
        tags: Dictionary of tags
        
    Returns:
        Comma-separated key=value pairs
    """
    return ",".join(f"{k}={v}" for k, v in tags.items())


def safe_json_loads(data: str, default: Any = None) -> Any:
    """
    Safely parse JSON string.
    
    Args:
        data: JSON string
        default: Default value on error
        
    Returns:
        Parsed data or default
    """
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def chunks(items: List[Any], size: int) -> List[List[Any]]:
    """
    Split list into chunks.
    
    Args:
        items: List to chunk
        size: Chunk size
        
    Returns:
        List of chunks
    """
    return [items[i:i + size] for i in range(0, len(items), size)]


def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))
        
        return wrapper
    return decorator


def rate_limit(calls: int, period: float):
    """
    Rate limit decorator.
    
    Args:
        calls: Maximum number of calls
        period: Time period in seconds
    """
    import time
    import threading
    
    def decorator(func):
        call_times = []
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal call_times
            
            now = time.time()
            call_times = [t for t in call_times if now - t < period]
            
            if len(call_times) >= calls:
                sleep_time = period - (now - call_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    call_times = [t for t in call_times if time.time() - t < period]
            
            call_times.append(time.time())
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def memoize(func):
    """
    Simple memoization decorator.
    
    Args:
        func: Function to memoize
    """
    cache = {}
    
    @wraps(func)
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    
    wrapper.cache = cache
    return wrapper


class Timer:
    """Context manager for timing code blocks."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, *args):
        self.elapsed = datetime.now() - self.start_time
    
    @property
    def seconds(self) -> float:
        return self.elapsed.total_seconds() if self.elapsed else 0


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID.
    
    Args:
        prefix: Optional prefix
        
    Returns:
        Unique ID string
    """
    import uuid
    return f"{prefix}{uuid.uuid4().hex[:12]}"