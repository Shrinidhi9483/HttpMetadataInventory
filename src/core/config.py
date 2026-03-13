"""
Application configuration management using Pydantic Settings.

This module provides centralized configuration for the application,
loading values from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, MongoDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        app_name: Name of the application
        app_version: Current version of the application
        debug: Enable debug mode
        mongodb_url: MongoDB connection string
        mongodb_database: Name of the MongoDB database
        http_timeout: Timeout for HTTP requests in seconds
        max_retries: Maximum number of retries for failed requests
        worker_pool_size: Size of the background worker pool
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application settings
    app_name: str = Field(default="HTTP Metadata Inventory", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode flag")
    
    # MongoDB settings
    mongodb_url: str = Field(
        default="mongodb://mongodb:27017",
        description="MongoDB connection URL"
    )
    mongodb_database: str = Field(
        default="metadata_inventory",
        description="MongoDB database name"
    )
    mongodb_max_pool_size: int = Field(
        default=10,
        description="Maximum connection pool size for MongoDB"
    )
    mongodb_min_pool_size: int = Field(
        default=1,
        description="Minimum connection pool size for MongoDB"
    )
    
    # HTTP client settings
    http_timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds",
        ge=1.0,
        le=120.0
    )
    http_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for HTTP requests",
        ge=0,
        le=10
    )
    
    # Background worker settings
    worker_pool_size: int = Field(
        default=5,
        description="Number of concurrent background workers",
        ge=1,
        le=20
    )
    
    # API settings
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    
    @field_validator("mongodb_url")
    @classmethod
    def validate_mongodb_url(cls, v: str) -> str:
        """Validate MongoDB URL format."""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MongoDB URL must start with 'mongodb://' or 'mongodb+srv://'")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to avoid re-reading environment variables
    on every settings access.
    
    Returns:
        Settings: Application settings instance
    """
    return Settings()
