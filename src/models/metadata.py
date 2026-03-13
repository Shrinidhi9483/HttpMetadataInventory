"""
Pydantic models for metadata-related data structures.

This module defines the data models used throughout the application
for URL metadata storage and API request/response handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CollectionStatus(str, Enum):
    """Status of metadata collection."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CookieInfo(BaseModel):
    """Model representing a single cookie."""
    
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., description="Cookie name")
    value: str = Field(..., description="Cookie value")
    domain: Optional[str] = Field(None, description="Cookie domain")
    path: Optional[str] = Field(None, description="Cookie path")
    expires: Optional[str] = Field(None, description="Cookie expiration")
    secure: bool = Field(False, description="Secure flag")
    http_only: bool = Field(False, description="HttpOnly flag", alias="httpOnly")


class MetadataDocument(BaseModel):
    """
    Complete metadata document stored in MongoDB.
    
    This model represents the full dataset collected from a URL,
    including headers, cookies, and page source.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "url": "https://example.com",
                "normalized_url": "https://example.com/",
                "headers": {"content-type": "text/html"},
                "cookies": [{"name": "session", "value": "abc123"}],
                "page_source": "<html>...</html>",
                "status_code": 200,
                "collection_status": "completed",
                "collected_at": "2024-01-01T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }
    )
    
    # URL information
    url: str = Field(..., description="Original URL")
    normalized_url: str = Field(..., description="Normalized URL for lookups")
    
    # Collected metadata
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP response headers"
    )
    cookies: list[CookieInfo] = Field(
        default_factory=list,
        description="Cookies set by the URL"
    )
    page_source: Optional[str] = Field(
        None,
        description="HTML page source content"
    )
    status_code: Optional[int] = Field(
        None,
        description="HTTP response status code"
    )
    
    # Collection metadata
    collection_status: CollectionStatus = Field(
        default=CollectionStatus.PENDING,
        description="Status of metadata collection"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if collection failed"
    )
    
    # Timestamps
    collected_at: Optional[datetime] = Field(
        None,
        description="When the metadata was collected"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Document creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Document last update timestamp"
    )


# Request/Response Models for API

class CreateMetadataRequest(BaseModel):
    """Request model for creating metadata."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com"
            }
        }
    )
    
    url: HttpUrl = Field(..., description="URL to collect metadata from")
    
    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, v: Any) -> Any:
        """Ensure URL is a string."""
        if isinstance(v, str):
            # Strip whitespace
            return v.strip()
        return v


class GetMetadataRequest(BaseModel):
    """Request model for retrieving metadata."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com"
            }
        }
    )
    
    url: HttpUrl = Field(..., description="URL to retrieve metadata for")


class MetadataResponse(BaseModel):
    """Response model for metadata retrieval."""
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "url": "https://example.com",
                "headers": {"content-type": "text/html; charset=utf-8"},
                "cookies": [{"name": "session", "value": "abc123"}],
                "page_source": "<html>...</html>",
                "status_code": 200,
                "collected_at": "2024-01-01T00:00:00Z"
            }
        }
    )
    
    url: str = Field(..., description="Original URL")
    headers: dict[str, str] = Field(..., description="HTTP response headers")
    cookies: list[CookieInfo] = Field(..., description="Cookies from the URL")
    page_source: Optional[str] = Field(None, description="HTML page source")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    collected_at: Optional[datetime] = Field(None, description="Collection timestamp")


class MetadataCreatedResponse(BaseModel):
    """Response model for successful metadata creation."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Metadata collected successfully",
                "url": "https://example.com",
                "status": "completed"
            }
        }
    )
    
    message: str = Field(..., description="Status message")
    url: str = Field(..., description="URL that was processed")
    status: CollectionStatus = Field(..., description="Collection status")


class MetadataAcceptedResponse(BaseModel):
    """Response model for accepted but pending metadata collection."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Request accepted. Metadata collection scheduled.",
                "url": "https://example.com",
                "status": "pending"
            }
        }
    )
    
    message: str = Field(
        default="Request accepted. Metadata collection scheduled.",
        description="Status message"
    )
    url: str = Field(..., description="URL scheduled for collection")
    status: CollectionStatus = Field(
        default=CollectionStatus.PENDING,
        description="Collection status"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid URL format",
                "details": {"url": "not-a-valid-url"}
            }
        }
    )
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database connection status")
    version: str = Field(..., description="Application version")
