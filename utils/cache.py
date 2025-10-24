"""Simple disk cache for HTML documents and other data."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Any, Union

logger = logging.getLogger(__name__)


class DiskCache:
    """Simple disk-based cache for storing fetched documents."""

    def __init__(self, cache_dir: Union[str, Path]):
        """Initialize cache.

        Args:
            cache_dir: Directory to store cached files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a safe filename from a cache key.

        Args:
            key: Original cache key (e.g., URL)

        Returns:
            Safe filename hash
        """
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, key: str, suffix: str = ".html") -> Optional[str]:
        """Retrieve cached content.

        Args:
            key: Cache key
            suffix: File suffix for cached file

        Returns:
            Cached content or None if not found
        """
        cache_key = self._get_cache_key(key)
        cache_file = self.cache_dir / f"{cache_key}{suffix}"

        if cache_file.exists():
            logger.info(f"Cache hit: {key}")
            return cache_file.read_text(encoding="utf-8")

        logger.info(f"Cache miss: {key}")
        return None

    def set(self, key: str, content: str, suffix: str = ".html"):
        """Store content in cache.

        Args:
            key: Cache key
            content: Content to cache
            suffix: File suffix for cached file
        """
        cache_key = self._get_cache_key(key)
        cache_file = self.cache_dir / f"{cache_key}{suffix}"

        cache_file.write_text(content, encoding="utf-8")
        logger.info(f"Cached: {key}")

    def get_json(self, key: str) -> Optional[Any]:
        """Retrieve cached JSON data.

        Args:
            key: Cache key

        Returns:
            Parsed JSON data or None
        """
        content = self.get(key, suffix=".json")
        if content:
            return json.loads(content)
        return None

    def set_json(self, key: str, data: Any):
        """Store JSON data in cache.

        Args:
            key: Cache key
            data: Data to cache (will be JSON serialized)
        """
        content = json.dumps(data, indent=2)
        self.set(key, content, suffix=".json")

    def exists(self, key: str, suffix: str = ".html") -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key
            suffix: File suffix

        Returns:
            True if cached, False otherwise
        """
        cache_key = self._get_cache_key(key)
        cache_file = self.cache_dir / f"{cache_key}{suffix}"
        return cache_file.exists()

    def clear(self):
        """Clear all cached files."""
        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                cache_file.unlink()
        logger.info("Cache cleared")

    def get_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of all cached files
        """
        return sum(f.stat().st_size for f in self.cache_dir.glob("*") if f.is_file())
