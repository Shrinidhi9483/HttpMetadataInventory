"""
FastAPI dependency injection functions.

This module provides dependency functions that can be injected
into route handlers for database connections and services.
"""

from typing import Annotated

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..repositories.database import get_database
from ..repositories.metadata_repository import MetadataRepository
from ..services.collector import URLCollector
from ..services.metadata_service import MetadataService


async def get_metadata_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
) -> MetadataRepository:
    """
    Get metadata repository instance.
    
    Args:
        db: Database instance from dependency injection
        
    Returns:
        MetadataRepository instance
    """
    return MetadataRepository(db)


async def get_url_collector() -> URLCollector:
    """
    Get URL collector instance.
    
    Returns:
        URLCollector instance
    """
    return URLCollector()


async def get_metadata_service(
    repository: Annotated[MetadataRepository, Depends(get_metadata_repository)],
    collector: Annotated[URLCollector, Depends(get_url_collector)]
) -> MetadataService:
    """
    Get metadata service instance.
    
    Args:
        repository: MetadataRepository from dependency injection
        collector: URLCollector from dependency injection
        
    Returns:
        MetadataService instance
    """
    return MetadataService(repository, collector)


# Type aliases for cleaner route signatures
MetadataRepositoryDep = Annotated[MetadataRepository, Depends(get_metadata_repository)]
MetadataServiceDep = Annotated[MetadataService, Depends(get_metadata_service)]
URLCollectorDep = Annotated[URLCollector, Depends(get_url_collector)]
