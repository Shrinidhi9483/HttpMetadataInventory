"""
MongoDB database connection management.

This module provides async database connection handling using Motor,
the async MongoDB driver for Python.
"""

import asyncio
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from ..core.config import get_settings
from ..core.exceptions import DatabaseConnectionError
from ..core.logging import logger


class Database:
    """
    Singleton class for managing MongoDB database connections.
    
    Provides connection pooling and lifecycle management for
    async MongoDB operations.
    """
    
    _instance: Optional["Database"] = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None
    _initialized: bool = False
    
    def __new__(cls) -> "Database":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def client(self) -> AsyncIOMotorClient:
        """Get the MongoDB client instance."""
        if self._client is None:
            raise DatabaseConnectionError("Database client not initialized")
        return self._client
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if self._database is None:
            raise DatabaseConnectionError("Database not initialized")
        return self._database
    
    async def connect(self, max_retries: int = 5, retry_delay: float = 2.0) -> None:
        """
        Establish connection to MongoDB with retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Delay between retries in seconds
            
        Raises:
            DatabaseConnectionError: If connection fails after all retries
        """
        if self._initialized:
            logger.debug("Database already connected")
            return
        
        settings = get_settings()
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Attempting to connect to MongoDB (attempt {attempt}/{max_retries})"
                )

                logger.info(f"MongoDB URL: {settings.mongodb_url}")
                
                self._client = AsyncIOMotorClient(
                    settings.mongodb_url,
                    maxPoolSize=settings.mongodb_max_pool_size,
                    minPoolSize=settings.mongodb_min_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                )
                
                # Verify connection by pinging the server
                await self._client.admin.command("ping")
                
                self._database = self._client[settings.mongodb_database]
                self._initialized = True
                
                logger.info(
                    f"Successfully connected to MongoDB: {settings.mongodb_database}"
                )
                
                # Create indexes after successful connection
                await self._create_indexes()
                
                return
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.warning(
                    f"MongoDB connection attempt {attempt} failed: {str(e)}"
                )
                
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise DatabaseConnectionError(
                        message="Failed to connect to MongoDB after all retries",
                        details={"attempts": max_retries, "error": str(e)}
                    )
    
    async def _create_indexes(self) -> None:
        """Create necessary indexes for optimal query performance."""
        try:
            # Create unique index on normalized_url for fast lookups
            await self._database.metadata.create_index(
                "normalized_url",
                unique=True,
                background=True
            )
            
            # Create index on collection_status for filtering
            await self._database.metadata.create_index(
                "collection_status",
                background=True
            )
            
            # Create compound index for status and timestamp queries
            await self._database.metadata.create_index(
                [("collection_status", 1), ("created_at", -1)],
                background=True
            )
            
            # Create index on created_at for time-based queries
            await self._database.metadata.create_index(
                "created_at",
                background=True
            )
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
            # Don't raise - indexes are optimization, not critical
    
    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            self._initialized = False
            logger.info("Disconnected from MongoDB")
    
    async def health_check(self) -> bool:
        """
        Check if database connection is healthy.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            if self._client is None:
                return False
            await self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False


# Global database instance
database = Database()


async def get_database() -> AsyncIOMotorDatabase:
    """
    Dependency function to get database instance.
    
    Returns:
        AsyncIOMotorDatabase: The database instance
    """
    return database.db
