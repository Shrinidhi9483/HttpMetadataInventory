"""
Custom exception classes for the application.

This module defines application-specific exceptions that provide
meaningful error information throughout the codebase.
"""

from typing import Any, Optional


class BaseAppException(Exception):
    """Base exception class for all application exceptions."""
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class URLCollectionError(BaseAppException):
    """Exception raised when URL metadata collection fails."""
    
    def __init__(
        self,
        url: str,
        message: str = "Failed to collect metadata from URL",
        details: Optional[dict[str, Any]] = None
    ) -> None:
        self.url = url
        super().__init__(message=message, details={"url": url, **(details or {})})


class URLValidationError(BaseAppException):
    """Exception raised when URL validation fails."""
    
    def __init__(
        self,
        url: str,
        reason: str = "Invalid URL format"
    ) -> None:
        self.url = url
        self.reason = reason
        super().__init__(
            message=f"URL validation failed: {reason}",
            details={"url": url, "reason": reason}
        )


class DatabaseConnectionError(BaseAppException):
    """Exception raised when database connection fails."""
    
    def __init__(
        self,
        message: str = "Failed to connect to database",
        details: Optional[dict[str, Any]] = None
    ) -> None:
        super().__init__(message=message, details=details)


class DatabaseOperationError(BaseAppException):
    """Exception raised when a database operation fails."""
    
    def __init__(
        self,
        operation: str,
        message: str = "Database operation failed",
        details: Optional[dict[str, Any]] = None
    ) -> None:
        self.operation = operation
        super().__init__(
            message=message,
            details={"operation": operation, **(details or {})}
        )


class MetadataNotFoundError(BaseAppException):
    """Exception raised when metadata for a URL is not found."""
    
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(
            message="Metadata not found for URL",
            details={"url": url}
        )


class HTTPTimeoutError(URLCollectionError):
    """Exception raised when HTTP request times out."""
    
    def __init__(self, url: str, timeout: float) -> None:
        super().__init__(
            url=url,
            message=f"HTTP request timed out after {timeout} seconds",
            details={"timeout": timeout}
        )


class HTTPConnectionError(URLCollectionError):
    """Exception raised when HTTP connection fails."""
    
    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            url=url,
            message="Failed to establish HTTP connection",
            details={"reason": reason}
        )
