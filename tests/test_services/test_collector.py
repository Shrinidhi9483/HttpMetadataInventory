"""
Tests for URLCollector service.

This module tests URL collection functionality including
validation, normalization, and HTTP fetching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import (
    HTTPConnectionError,
    HTTPTimeoutError,
    URLCollectionError,
    URLValidationError,
)
from src.models.metadata import CookieInfo
from src.services.collector import URLCollector


class TestURLNormalization:
    """Tests for URL normalization."""
    
    @pytest.mark.parametrize("input_url,expected", [
        # Basic normalization
        ("https://EXAMPLE.COM", "https://example.com/"),
        ("https://Example.Com/Path", "https://example.com/Path"),
        
        # Default port removal
        ("http://example.com:80", "http://example.com/"),
        ("https://example.com:443", "https://example.com/"),
        ("http://example.com:8080", "http://example.com:8080/"),
        
        # Path handling
        ("https://example.com", "https://example.com/"),
        ("https://example.com/", "https://example.com/"),
        ("https://example.com/path", "https://example.com/path"),
        
        # Query string preservation
        ("https://example.com?q=test", "https://example.com/?q=test"),
        ("https://example.com/path?q=test", "https://example.com/path?q=test"),
        
        # Fragment removal
        ("https://example.com#section", "https://example.com/"),
        ("https://example.com/path#section", "https://example.com/path"),
    ])
    def test_normalize_url(self, input_url: str, expected: str):
        """Test URL normalization produces expected results."""
        result = URLCollector.normalize_url(input_url)
        assert result == expected
    
    def test_normalize_preserves_query_params(self):
        """Test that query parameters are preserved."""
        url = "https://example.com/search?q=python&page=1"
        result = URLCollector.normalize_url(url)
        assert "q=python" in result
        assert "page=1" in result


class TestURLValidation:
    """Tests for URL validation."""
    
    @pytest.mark.parametrize("valid_url", [
        "http://example.com",
        "https://example.com",
        "https://example.com/path",
        "https://example.com/path/to/resource",
        "https://example.com:8080",
        "https://sub.example.com",
        "https://example.com?query=value",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ])
    def test_valid_urls_pass_validation(self, valid_url: str):
        """Test that valid URLs pass validation."""
        result = URLCollector.validate_url(valid_url)
        assert result == valid_url.strip()
    
    @pytest.mark.parametrize("invalid_url,error_contains", [
        ("", "empty"),
        ("   ", "empty"),
        ("not-a-url", "scheme"),
        ("ftp://example.com", "scheme"),
        ("file:///path", "scheme"),
        ("://example.com", "scheme"),
        ("http://", "domain"),
    ])
    def test_invalid_urls_raise_error(
        self,
        invalid_url: str,
        error_contains: str
    ):
        """Test that invalid URLs raise URLValidationError."""
        with pytest.raises(URLValidationError) as exc_info:
            URLCollector.validate_url(invalid_url)
        
        assert error_contains.lower() in str(exc_info.value).lower()
    
    def test_validate_url_strips_whitespace(self):
        """Test that validation strips whitespace."""
        url = "  https://example.com  "
        result = URLCollector.validate_url(url)
        assert result == "https://example.com"


class TestURLCollection:
    """Tests for URL metadata collection."""
    
    @pytest.fixture
    def collector(self) -> URLCollector:
        """Create a URLCollector for testing."""
        return URLCollector(timeout=5.0, max_retries=1)
    
    @pytest.mark.asyncio
    async def test_collect_success(self, collector: URLCollector):
        """Test successful URL collection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html",
            "server": "nginx",
        }
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = []
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await collector.collect("https://example.com")
        
        assert "headers" in result
        assert "cookies" in result
        assert "page_source" in result
        assert "status_code" in result
        assert result["status_code"] == 200
    
    @pytest.mark.asyncio
    async def test_collect_timeout(self, collector: URLCollector):
        """Test collection timeout handling."""
        import httpx
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            with pytest.raises(URLCollectionError):
                await collector.collect("https://example.com")
    
    @pytest.mark.asyncio
    async def test_collect_connection_error(self, collector: URLCollector):
        """Test collection connection error handling."""
        import httpx
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            with pytest.raises(URLCollectionError):
                await collector.collect("https://example.com")
    
    @pytest.mark.asyncio
    async def test_collect_extracts_cookies(self, collector: URLCollector):
        """Test that cookies are properly extracted."""
        mock_cookie = MagicMock()
        mock_cookie.name = "session"
        mock_cookie.value = "abc123"
        mock_cookie.domain = "example.com"
        mock_cookie.path = "/"
        mock_cookie.expires = None
        mock_cookie.secure = True
        mock_cookie.has_nonstandard_attr = MagicMock(return_value=True)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html></html>"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = [mock_cookie]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await collector.collect("https://example.com")
        
        assert len(result["cookies"]) == 1
        assert result["cookies"][0].name == "session"
        assert result["cookies"][0].value == "abc123"


class TestRetryLogic:
    """Tests for retry logic in collection."""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that collection retries on transient failures."""
        import httpx
        
        collector = URLCollector(timeout=5.0, max_retries=3)
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Temporary failure")
            
            response = MagicMock()
            response.status_code = 200
            response.headers = {"content-type": "text/html"}
            response.text = "<html></html>"
            response.cookies = MagicMock()
            response.cookies.jar = []
            return response
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = mock_get
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await collector.collect("https://example.com")
        
        assert call_count == 3
        assert result["status_code"] == 200
