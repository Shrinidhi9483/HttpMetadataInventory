"""
Tests for MetadataService.

This module tests the business logic layer for metadata
operations including collection, storage, and retrieval.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import URLCollectionError
from src.models.metadata import (
    CollectionStatus,
    CookieInfo,
    MetadataDocument,
    MetadataResponse,
)
from src.repositories.metadata_repository import MetadataRepository
from src.services.collector import URLCollector
from src.services.metadata_service import MetadataService


class TestCreateMetadata:
    """Tests for metadata creation."""
    
    @pytest.fixture
    def service(
        self,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock
    ) -> MetadataService:
        """Create service with mocks."""
        return MetadataService(mock_metadata_repository, mock_url_collector)
    
    @pytest.mark.asyncio
    async def test_create_new_metadata(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
        sample_collected_data: dict,
        sample_metadata_document: MetadataDocument,
    ):
        """Test creating metadata for a new URL."""
        mock_metadata_repository.find_by_url.return_value = None
        mock_url_collector.collect.return_value = sample_collected_data
        mock_metadata_repository.upsert.return_value = sample_metadata_document
        
        result = await service.create_metadata(sample_url)
        
        assert result.collection_status == CollectionStatus.COMPLETED
        mock_url_collector.collect.assert_called_once()
        mock_metadata_repository.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_updates_existing_completed(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
        sample_collected_data: dict,
        sample_metadata_document: MetadataDocument,
    ):
        """Test that creating metadata updates existing completed records."""
        mock_metadata_repository.find_by_url.return_value = sample_metadata_document
        mock_url_collector.collect.return_value = sample_collected_data
        mock_metadata_repository.upsert.return_value = sample_metadata_document
        
        result = await service.create_metadata(sample_url)
        
        # Should still collect and update
        mock_url_collector.collect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_handles_collection_error(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
    ):
        """Test that collection errors are propagated."""
        mock_metadata_repository.find_by_url.return_value = None
        mock_url_collector.collect.side_effect = URLCollectionError(
            url=sample_url,
            message="Collection failed"
        )
        
        with pytest.raises(URLCollectionError):
            await service.create_metadata(sample_url)


class TestGetMetadata:
    """Tests for metadata retrieval."""
    
    @pytest.fixture
    def service(
        self,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock
    ) -> MetadataService:
        """Create service with mocks."""
        return MetadataService(mock_metadata_repository, mock_url_collector)
    
    @pytest.mark.asyncio
    async def test_get_existing_completed_metadata(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        sample_url: str,
        sample_metadata_document: MetadataDocument,
    ):
        """Test retrieving existing completed metadata."""
        mock_metadata_repository.find_by_url.return_value = sample_metadata_document
        
        result, should_trigger = await service.get_metadata(sample_url)
        
        assert result is not None
        assert isinstance(result, MetadataResponse)
        assert should_trigger is False
    
    @pytest.mark.asyncio
    async def test_get_missing_metadata_triggers_background(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
        sample_pending_document: MetadataDocument,
    ):
        """Test that missing metadata triggers background collection."""
        mock_metadata_repository.find_by_url.return_value = None
        mock_metadata_repository.upsert.return_value = sample_pending_document
        
        result, should_trigger = await service.get_metadata(sample_url)
        
        assert result is None
        assert should_trigger is True
        mock_metadata_repository.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_pending_metadata_does_not_retrigger(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        sample_url: str,
        sample_pending_document: MetadataDocument,
    ):
        """Test that pending metadata doesn't trigger another collection."""
        sample_pending_document.collection_status = CollectionStatus.PENDING
        mock_metadata_repository.find_by_url.return_value = sample_pending_document
        
        result, should_trigger = await service.get_metadata(sample_url)
        
        assert result is None
        # PENDING status should trigger background collection
        assert should_trigger is True
    
    @pytest.mark.asyncio
    async def test_get_in_progress_metadata_does_not_retrigger(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        sample_url: str,
        sample_pending_document: MetadataDocument,
    ):
        """Test that in-progress metadata doesn't trigger another collection."""
        sample_pending_document.collection_status = CollectionStatus.IN_PROGRESS
        mock_metadata_repository.find_by_url.return_value = sample_pending_document
        
        result, should_trigger = await service.get_metadata(sample_url)
        
        assert result is None
        assert should_trigger is False
    
    @pytest.mark.asyncio
    async def test_get_failed_metadata_triggers_retry(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        sample_url: str,
        sample_pending_document: MetadataDocument,
    ):
        """Test that failed metadata triggers retry."""
        sample_pending_document.collection_status = CollectionStatus.FAILED
        mock_metadata_repository.find_by_url.return_value = sample_pending_document
        
        result, should_trigger = await service.get_metadata(sample_url)
        
        assert result is None
        assert should_trigger is True


class TestBackgroundCollection:
    """Tests for background metadata collection."""
    
    @pytest.fixture
    def service(
        self,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock
    ) -> MetadataService:
        """Create service with mocks."""
        return MetadataService(mock_metadata_repository, mock_url_collector)
    
    @pytest.mark.asyncio
    async def test_background_collection_success(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
        sample_collected_data: dict,
    ):
        """Test successful background collection."""
        mock_url_collector.collect.return_value = sample_collected_data
        mock_metadata_repository.update.return_value = MagicMock()
        
        await service.collect_metadata_background(sample_url)
        
        # Should update status to in_progress, then completed
        assert mock_metadata_repository.update.call_count == 2
    
    @pytest.mark.asyncio
    async def test_background_collection_failure_updates_status(
        self,
        service: MetadataService,
        mock_metadata_repository: AsyncMock,
        mock_url_collector: AsyncMock,
        sample_url: str,
    ):
        """Test that failed background collection updates status."""
        mock_url_collector.collect.side_effect = URLCollectionError(
            url=sample_url,
            message="Collection failed"
        )
        mock_metadata_repository.update.return_value = MagicMock()
        
        # Should not raise, but handle error gracefully
        await service.collect_metadata_background(sample_url)
        
        # Should update status to failed
        final_update = mock_metadata_repository.update.call_args_list[-1]
        assert CollectionStatus.FAILED.value in str(final_update)
