"""
Minimal in-memory TTL cache for analysis results.
"""
import time
from typing import Any, Optional


class TTLCache:
    """
    Minimal Time-To-Live cache with dict storage of {key: (expires_at, value)}.
    Purges expired entries on get/set operations.
    """
    
    def __init__(self):
        """Initialize TTL cache with empty storage."""
        self._storage = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        
        Args:
            key: Cache key.
        
        Returns:
            Cached value if found and not expired, otherwise None.
        """
        # Purge expired entries
        self._purge_expired()
        
        if key not in self._storage:
            return None
        
        expires_at, value = self._storage[key]
        
        # Check if this specific entry is expired
        if time.time() > expires_at:
            del self._storage[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        """
        Store value in cache with TTL.
        
        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds.
        """
        # Purge expired entries
        self._purge_expired()
        
        expires_at = time.time() + ttl
        self._storage[key] = (expires_at, value)
    
    def delete(self, key: str) -> None:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key to delete.
        """
        if key in self._storage:
            del self._storage[key]
    
    def _purge_expired(self) -> None:
        """Remove all expired entries from storage."""
        current_time = time.time()
        expired_keys = [
            key for key, (expires_at, _) in self._storage.items()
            if current_time > expires_at
        ]
        for key in expired_keys:
            del self._storage[key]


# Module-level instance
analysis_cache = TTLCache()
