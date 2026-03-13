"""
URL metadata collector service.

This module handles the collection of HTTP metadata from URLs,
including headers, cookies, and page source content.
"""

import asyncio
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import httpx

from ..core.config import get_settings
from ..core.exceptions import (
    HTTPConnectionError,
    HTTPTimeoutError,
    URLCollectionError,
    URLValidationError,
)
from ..core.logging import logger
from ..models.metadata import CookieInfo


class URLCollector:
    """
    Service for collecting metadata from URLs.
    
    Handles HTTP requests to fetch headers, cookies, and page
    source from target URLs with proper timeout and retry handling.
    """
    
    # Default headers to send with requests
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    def __init__(
        self,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ) -> None:
        """
        Initialize the URL collector.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        settings = get_settings()
        self._timeout = timeout or settings.http_timeout
        self._max_retries = max_retries or settings.http_max_retries
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize a URL for consistent storage and lookup.
        
        Normalizes the URL by:
        - Converting scheme and host to lowercase
        - Removing default ports (80 for http, 443 for https)
        - Ensuring trailing slash for root paths
        - Removing fragments
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL string
        """
        parsed = urlparse(url)
        
        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Remove default ports
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]
        
        # Ensure path has at least a slash
        path = parsed.path or "/"
        
        # Reconstruct URL without fragment
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ""  # Remove fragment
        ))
        
        return normalized
    
    @staticmethod
    def validate_url(url: str) -> str:
        """
        Validate and clean a URL.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated URL string
            
        Raises:
            URLValidationError: If URL is invalid
        """
        url = url.strip()
        
        if not url:
            raise URLValidationError(url, "URL cannot be empty")
        
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ("http", "https"):
            raise URLValidationError(
                url,
                f"Invalid URL scheme: {parsed.scheme or 'none'}. "
                "Only http and https are supported."
            )
        
        # Check netloc (domain)
        if not parsed.netloc:
            raise URLValidationError(url, "URL must have a valid domain")
        
        # Basic domain validation - extract host without port
        netloc = parsed.netloc.lower()
        host = netloc.split(":")[0]
        
        if host in ("localhost", "127.0.0.1", "0.0.0.0"):
            # Allow localhost for testing
            pass
        elif "." not in host:
            raise URLValidationError(
                url,
                "Invalid domain format"
            )
        
        return url
    
    async def collect(self, url: str) -> dict[str, Any]:
        """
        Collect metadata from a URL.
        
        Fetches the URL and extracts headers, cookies, and page source.
        
        Args:
            url: URL to collect metadata from
            
        Returns:
            Dictionary containing:
                - headers: Response headers
                - cookies: List of cookie dictionaries
                - page_source: HTML content
                - status_code: HTTP status code
                
        Raises:
            URLCollectionError: If collection fails
            HTTPTimeoutError: If request times out
            HTTPConnectionError: If connection fails
        """
        validated_url = self.validate_url(url)
        
        last_error: Optional[Exception] = None
        
        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._fetch_url(validated_url, attempt)
            except (HTTPTimeoutError, HTTPConnectionError) as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                    logger.warning(
                        f"Retry {attempt}/{self._max_retries} for {url} "
                        f"after {delay}s delay"
                    )
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise URLCollectionError(
            url=url,
            message="Failed to collect URL after all retries",
            details={"attempts": self._max_retries, "last_error": str(last_error)}
        )
    
    async def _fetch_url(self, url: str, attempt: int = 1) -> dict[str, Any]:
        """
        Execute the HTTP request and extract metadata.
        
        Args:
            url: URL to fetch
            attempt: Current attempt number (for logging)
            
        Returns:
            Dictionary with collected metadata
        """
        logger.info(f"Fetching URL (attempt {attempt}): {url}")
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS
        ) as client:
            try:
                response = await client.get(url)
                
                # Extract headers (convert to regular dict with string values)
                headers = {
                    key: value
                    for key, value in response.headers.items()
                }
                
                # Extract cookies
                cookies = self._extract_cookies(response)
                
                # Get page source
                page_source = response.text
                
                logger.info(
                    f"Successfully collected metadata from {url} "
                    f"(status: {response.status_code})"
                )
                
                return {
                    "headers": headers,
                    "cookies": cookies,
                    "page_source": page_source,
                    "status_code": response.status_code
                }
                
            except httpx.TimeoutException as e:
                logger.error(f"Timeout fetching {url}: {str(e)}")
                raise HTTPTimeoutError(url, self._timeout)
                
            except httpx.ConnectError as e:
                logger.error(f"Connection error for {url}: {str(e)}")
                raise HTTPConnectionError(url, str(e))
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error for {url}: {str(e)}")
                raise URLCollectionError(
                    url=url,
                    message="HTTP request failed",
                    details={"error": str(e)}
                )
    
    def _extract_cookies(self, response: httpx.Response) -> list[CookieInfo]:
        """
        Extract cookies from response.
        
        Args:
            response: httpx Response object
            
        Returns:
            List of CookieInfo objects
        """
        cookies = []
        
        for cookie in response.cookies.jar:
            cookie_info = CookieInfo(
                name=cookie.name,
                value=cookie.value,
                domain=cookie.domain,
                path=cookie.path,
                expires=str(cookie.expires) if cookie.expires else None,
                secure=cookie.secure,
                http_only=bool(cookie.has_nonstandard_attr("HttpOnly")),
            )
            cookies.append(cookie_info)
        
        return cookies


# Singleton instance
url_collector = URLCollector()
