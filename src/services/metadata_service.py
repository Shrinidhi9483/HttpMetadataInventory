"""
Metadata service - Business logic layer.

This module orchestrates metadata collection and storage,
coordinating between the collector and repository layers.
"""

from datetime import datetime
from typing import Optional

from ..core.exceptions import URLCollectionError
from ..core.logging import logger
from ..models.metadata import (
    CollectionStatus,
    MetadataDocument,
    MetadataResponse,
)
from ..repositories.metadata_repository import MetadataRepository
from .collector import URLCollector


class MetadataService:
    """
    Service class for metadata operations.
    
    Provides business logic for metadata collection, storage,
    and retrieval, abstracting the underlying data operations.
    """
    
    def __init__(
        self,
        repository: MetadataRepository,
        collector: Optional[URLCollector] = None
    ) -> None:
        """
        Initialize the metadata service.
        
        Args:
            repository: MetadataRepository instance
            collector: URLCollector instance (optional, creates default if not provided)
        """
        self._repository = repository
        self._collector = collector or URLCollector()
    
    async def create_metadata(self, url: str) -> MetadataDocument:
        """
        Create metadata record for a URL by collecting and storing data.
        
        This is a synchronous operation that collects metadata
        and stores it before returning.
        
        Args:
            url: URL to collect metadata from
            
        Returns:
            Created MetadataDocument
            
        Raises:
            URLCollectionError: If collection fails
        """
        # Validate and normalize URL
        validated_url = self._collector.validate_url(url)
        normalized_url = self._collector.normalize_url(validated_url)
        
        logger.info(f"Creating metadata for URL: {normalized_url}")
        
        # Check if already exists
        existing = await self._repository.find_by_url(normalized_url)
        if existing and existing.collection_status == CollectionStatus.COMPLETED:
            logger.info(f"Metadata already exists for URL: {normalized_url}")
            # Update with fresh data
            return await self._collect_and_store(validated_url, normalized_url)
        
        # Collect and store metadata
        return await self._collect_and_store(validated_url, normalized_url)
    
    async def get_metadata(
        self,
        url: str
    ) -> tuple[Optional[MetadataResponse], bool]:
        """
        Retrieve metadata for a URL.
        
        Returns the metadata if it exists and is complete,
        otherwise returns None and indicates whether background
        collection should be triggered.
        
        Args:
            url: URL to retrieve metadata for
            
        Returns:
            Tuple of (MetadataResponse or None, should_trigger_background)
        """
        # Validate and normalize URL
        validated_url = self._collector.validate_url(url)
        normalized_url = self._collector.normalize_url(validated_url)
        
        logger.info(f"Retrieving metadata for URL: {normalized_url}")
        
        # Look up in database
        existing = await self._repository.find_by_url(normalized_url)
        
        if existing is None:
            logger.info(f"No metadata found for URL: {normalized_url}")
            # Create pending record for background collection
            await self._create_pending_record(validated_url, normalized_url)
            return None, True
        
        if existing.collection_status == CollectionStatus.COMPLETED:
            logger.info(f"Returning existing metadata for URL: {normalized_url}")
            return self._to_response(existing), False
        
        if existing.collection_status == CollectionStatus.IN_PROGRESS:
            logger.info(f"Collection in progress for URL: {normalized_url}")
            return None, False  # Don't trigger again
        
        if existing.collection_status == CollectionStatus.FAILED:
            logger.info(f"Previous collection failed for URL: {normalized_url}")
            # Retry collection
            return None, True
        
        # PENDING status - collection should be triggered
        return None, True
    
    async def collect_metadata_background(self, url: str) -> None:
        """
        Collect metadata for a URL (for background processing).
        
        This method is designed to be called by background workers
        and handles its own error handling.
        
        Args:
            url: URL to collect metadata from
        """
        validated_url = self._collector.validate_url(url)
        normalized_url = self._collector.normalize_url(validated_url)
        
        logger.info(f"Starting background collection for URL: {normalized_url}")
        
        try:
            # Update status to in_progress
            await self._repository.update(
                normalized_url,
                {"collection_status": CollectionStatus.IN_PROGRESS.value}
            )
            
            # Collect metadata
            collected_data = await self._collector.collect(validated_url)
            
            # Update with collected data
            await self._repository.update(
                normalized_url,
                {
                    "headers": collected_data["headers"],
                    "cookies": [c.model_dump(by_alias=True) for c in collected_data["cookies"]],
                    "page_source": collected_data["page_source"],
                    "status_code": collected_data["status_code"],
                    "collection_status": CollectionStatus.COMPLETED.value,
                    "collected_at": datetime.utcnow(),
                    "error_message": None
                }
            )
            
            logger.info(f"Background collection completed for URL: {normalized_url}")
            
        except URLCollectionError as e:
            logger.error(f"Background collection failed for {normalized_url}: {str(e)}")
            await self._repository.update(
                normalized_url,
                {
                    "collection_status": CollectionStatus.FAILED.value,
                    "error_message": str(e)
                }
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in background collection for {normalized_url}: {str(e)}"
            )
            await self._repository.update(
                normalized_url,
                {
                    "collection_status": CollectionStatus.FAILED.value,
                    "error_message": f"Unexpected error: {str(e)}"
                }
            )
    
    async def _collect_and_store(
        self,
        url: str,
        normalized_url: str
    ) -> MetadataDocument:
        """
        Collect metadata and store in database.
        
        Args:
            url: Original URL
            normalized_url: Normalized URL for storage
            
        Returns:
            Stored MetadataDocument
        """
        try:
            # Collect metadata from URL
            collected_data = await self._collector.collect(url)
            
            # Create document
            metadata = MetadataDocument(
                url=url,
                normalized_url=normalized_url,
                headers=collected_data["headers"],
                cookies=collected_data["cookies"],
                page_source=collected_data["page_source"],
                status_code=collected_data["status_code"],
                collection_status=CollectionStatus.COMPLETED,
                collected_at=datetime.utcnow()
            )
            
            # Store in database
            return await self._repository.upsert(metadata)
            
        except URLCollectionError:
            # Re-raise collection errors
            raise
        except Exception as e:
            logger.error(f"Failed to collect and store metadata: {str(e)}")
            raise URLCollectionError(
                url=url,
                message="Failed to collect and store metadata",
                details={"error": str(e)}
            )
    
    async def _create_pending_record(
        self,
        url: str,
        normalized_url: str
    ) -> MetadataDocument:
        """
        Create a pending metadata record for background collection.
        
        Args:
            url: Original URL
            normalized_url: Normalized URL
            
        Returns:
            Created pending MetadataDocument
        """
        metadata = MetadataDocument(
            url=url,
            normalized_url=normalized_url,
            collection_status=CollectionStatus.PENDING
        )
        
        return await self._repository.upsert(metadata)
    
    def _to_response(self, document: MetadataDocument) -> MetadataResponse:
        """Convert document to response model."""
        return MetadataResponse(
            url=document.url,
            headers=document.headers,
            cookies=document.cookies,
            page_source=document.page_source,
            status_code=document.status_code,
            collected_at=document.collected_at
        )
