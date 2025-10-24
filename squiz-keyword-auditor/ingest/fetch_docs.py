"""Fetch and cache Squiz Matrix documentation."""

import logging
from pathlib import Path
from typing import List, Dict, Union
import httpx
from bs4 import BeautifulSoup
import html2text

from utils.cache import DiskCache

logger = logging.getLogger(__name__)

# Official Squiz Matrix documentation URLs
SQUIZ_DOC_URLS = [
    "https://matrix.squiz.net/manuals/keyword-replacements/chapters/common-keywords",
    "https://matrix.squiz.net/manuals/keyword-replacements/chapters/global-keywords",
    "https://matrix.squiz.net/manuals/keyword-replacements/chapters/frontend-asset-keywords",
    "https://matrix.squiz.net/manuals/keyword-replacements/chapters/keyword-modifiers",
]


class DocFetcher:
    """Fetches and caches Squiz documentation."""

    def __init__(self, cache_dir: Union[str, Path]):
        """Initialize doc fetcher.

        Args:
            cache_dir: Directory to cache downloaded docs
        """
        self.cache = DiskCache(cache_dir)
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def fetch_all(self, refresh: bool = False) -> List[Dict[str, str]]:
        """Fetch all Squiz documentation pages.

        Args:
            refresh: If True, re-download even if cached

        Returns:
            List of documents with url, title, html, and text
        """
        docs = []
        for url in SQUIZ_DOC_URLS:
            logger.info(f"Processing: {url}")
            doc = self.fetch_doc(url, refresh=refresh)
            if doc:
                docs.append(doc)
        return docs

    def fetch_doc(self, url: str, refresh: bool = False) -> Dict[str, str]:
        """Fetch a single documentation page.

        Args:
            url: URL to fetch
            refresh: If True, re-download even if cached

        Returns:
            Document dict with url, title, html, and text
        """
        # Check cache first
        if not refresh and self.cache.exists(url):
            html_content = self.cache.get(url)
            logger.info(f"Using cached version of {url}")
        else:
            # Fetch from web
            try:
                response = self.client.get(url)
                response.raise_for_status()
                html_content = response.text
                self.cache.set(url, html_content)
                logger.info(f"Downloaded and cached: {url}")
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return None

        # Extract title and clean content
        soup = BeautifulSoup(html_content, 'lxml')

        # Extract title
        title = url.split('/')[-1].replace('-', ' ').title()
        if soup.title:
            title = soup.title.string or title

        # Extract main content (remove navigation, footer, etc.)
        main_content = soup.find('main') or soup.find('article') or soup.find('body')

        if main_content:
            # Remove script and style tags
            for script in main_content(['script', 'style', 'nav', 'footer']):
                script.decompose()

            # Convert to markdown-like text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0  # Don't wrap lines
            text_content = h.handle(str(main_content))
        else:
            text_content = html_content

        return {
            "url": url,
            "title": title,
            "html": html_content,
            "text": text_content,
        }

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
