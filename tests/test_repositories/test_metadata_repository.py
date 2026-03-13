"""
Tests for MetadataRepository.

This module tests the data access layer for metadata documents,
including CRUD operations and error handling.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import DatabaseOperationError
from src.models.metadata import CollectionStatus, CookieInfo, MetadataDocument
from src.repositories.metadata_repository import MetadataRepository


class TestFindByUrl:
    """Tests for find_by_url operation."""
    
    @pytest.mark.asyncio
    async def test_find_existing_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test finding an existing document."""
        mock_doc = {
            "url": "https://example.com",
            "normalized_url": sample_normalized_url,
            "headers": {"content-type": "text/html"},
            "cookies": [],
            "page_source": "<html></html>",
            "status_code": 200,
            "collection_status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        mock_motor_database.metadata.find_one.return_value = mock_doc
        
        result = await metadata_repository.find_by_url(sample_normalized_url)
        
        assert result is not None
        assert result.normalized_url == sample_normalized_url
        mock_motor_database.metadata.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_nonexistent_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test finding a document that doesn't exist."""
        mock_motor_database.metadata.find_one.return_value = None
        
        result = await metadata_repository.find_by_url(sample_normalized_url)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_handles_database_error(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test that database errors are handled."""
        from pymongo.errors import PyMongoError
        
        mock_motor_database.metadata.find_one.side_effect = PyMongoError(
            "Connection error"
        )
        
        with pytest.raises(DatabaseOperationError):
            await metadata_repository.find_by_url(sample_normalized_url)


class TestCreate:
    """Tests for create operation."""
    
    @pytest.mark.asyncio
    async def test_create_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_metadata_document: MetadataDocument,
    ):
        """Test creating a new document."""
        mock_result = MagicMock()
        mock_result.inserted_id = "test_id"
        mock_motor_database.metadata.insert_one.return_value = mock_result
        
        created_doc = {
            "_id": "test_id",
            "url": sample_metadata_document.url,
            "normalized_url": sample_metadata_document.normalized_url,
            "headers": sample_metadata_document.headers,
            "cookies": [],
            "page_source": sample_metadata_document.page_source,
            "status_code": 200,
            "collection_status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_motor_database.metadata.find_one.return_value = created_doc
        
        result = await metadata_repository.create(sample_metadata_document)
        
        assert result is not None
        mock_motor_database.metadata.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_handles_duplicate_key(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_metadata_document: MetadataDocument,
    ):
        """Test handling of duplicate key errors."""
        from pymongo.errors import DuplicateKeyError
        
        mock_motor_database.metadata.insert_one.side_effect = DuplicateKeyError(
            "Duplicate key"
        )
        
        # Return existing document
        existing_doc = {
            "url": sample_metadata_document.url,
            "normalized_url": sample_metadata_document.normalized_url,
            "headers": {},
            "cookies": [],
            "page_source": "",
            "collection_status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_motor_database.metadata.find_one.return_value = existing_doc
        
        result = await metadata_repository.create(sample_metadata_document)
        
        # Should return existing document instead of raising
        assert result is not None


class TestUpdate:
    """Tests for update operation."""
    
    @pytest.mark.asyncio
    async def test_update_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test updating an existing document."""
        updated_doc = {
            "url": "https://example.com",
            "normalized_url": sample_normalized_url,
            "headers": {"new-header": "value"},
            "cookies": [],
            "page_source": "<html>Updated</html>",
            "status_code": 200,
            "collection_status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_motor_database.metadata.find_one_and_update.return_value = updated_doc
        
        result = await metadata_repository.update(
            sample_normalized_url,
            {"headers": {"new-header": "value"}}
        )
        
        assert result is not None
        mock_motor_database.metadata.find_one_and_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test updating a document that doesn't exist."""
        mock_motor_database.metadata.find_one_and_update.return_value = None
        
        result = await metadata_repository.update(
            sample_normalized_url,
            {"headers": {"new-header": "value"}}
        )
        
        assert result is None


class TestUpsert:
    """Tests for upsert operation."""
    
    @pytest.mark.asyncio
    async def test_upsert_new_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_metadata_document: MetadataDocument,
    ):
        """Test upserting a new document."""
        upserted_doc = {
            "url": sample_metadata_document.url,
            "normalized_url": sample_metadata_document.normalized_url,
            "headers": sample_metadata_document.headers,
            "cookies": [],
            "page_source": sample_metadata_document.page_source,
            "status_code": 200,
            "collection_status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_motor_database.metadata.find_one_and_update.return_value = upserted_doc
        
        result = await metadata_repository.upsert(sample_metadata_document)
        
        assert result is not None
        call_kwargs = mock_motor_database.metadata.find_one_and_update.call_args
        assert call_kwargs[1]["upsert"] is True


class TestExists:
    """Tests for exists operation."""
    
    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test exists returns True for existing documents."""
        mock_motor_database.metadata.count_documents.return_value = 1
        
        result = await metadata_repository.exists(sample_normalized_url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test exists returns False for missing documents."""
        mock_motor_database.metadata.count_documents.return_value = 0
        
        result = await metadata_repository.exists(sample_normalized_url)
        
        assert result is False


class TestDelete:
    """Tests for delete operation."""
    
    @pytest.mark.asyncio
    async def test_delete_existing_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test deleting an existing document."""
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_motor_database.metadata.delete_one.return_value = mock_result
        
        result = await metadata_repository.delete(sample_normalized_url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(
        self,
        metadata_repository: MetadataRepository,
        mock_motor_database: AsyncMock,
        sample_normalized_url: str,
    ):
        """Test deleting a document that doesn't exist."""
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_motor_database.metadata.delete_one.return_value = mock_result
        
        result = await metadata_repository.delete(sample_normalized_url)
        
        assert result is False
