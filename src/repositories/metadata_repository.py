"""
Repository for metadata document operations.

This module provides the data access layer for metadata documents,
abstracting MongoDB operations from the service layer.
"""

from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..core.exceptions import DatabaseOperationError
from ..core.logging import logger
from ..models.metadata import CollectionStatus, CookieInfo, MetadataDocument


class MetadataRepository:
    """
    Repository class for metadata document CRUD operations.
    
    Provides an abstraction layer over MongoDB operations for
    metadata documents, ensuring consistent data handling and
    error management.
    """
    
    COLLECTION_NAME = "metadata"
    
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        """
        Initialize the repository with a database instance.
        
        Args:
            database: AsyncIOMotorDatabase instance
        """
        self._db = database
        self._collection = database[self.COLLECTION_NAME]
    
    async def find_by_url(self, normalized_url: str) -> Optional[MetadataDocument]:
        """
        Find metadata document by normalized URL.
        
        Args:
            normalized_url: Normalized URL to search for
            
        Returns:
            MetadataDocument if found, None otherwise
        """
        try:
            doc = await self._collection.find_one(
                {"normalized_url": normalized_url}
            )
            
            if doc is None:
                return None
            
            # Convert MongoDB document to Pydantic model
            return self._document_to_model(doc)
            
        except PyMongoError as e:
            logger.error(f"Failed to find metadata by URL: {str(e)}")
            raise DatabaseOperationError(
                operation="find_by_url",
                message="Failed to retrieve metadata",
                details={"url": normalized_url, "error": str(e)}
            )
    
    async def create(self, metadata: MetadataDocument) -> MetadataDocument:
        """
        Create a new metadata document.
        
        Args:
            metadata: MetadataDocument to create
            
        Returns:
            Created MetadataDocument
            
        Raises:
            DatabaseOperationError: If creation fails
        """
        try:
            doc = self._model_to_document(metadata)
            result = await self._collection.insert_one(doc)
            
            logger.info(
                f"Created metadata document for URL: {metadata.normalized_url}"
            )
            
            # Return the created document with _id
            created_doc = await self._collection.find_one(
                {"_id": result.inserted_id}
            )
            return self._document_to_model(created_doc)
            
        except DuplicateKeyError:
            # Document already exists - this shouldn't happen with proper checks
            logger.warning(
                f"Duplicate metadata document for URL: {metadata.normalized_url}"
            )
            # Return existing document
            existing = await self.find_by_url(metadata.normalized_url)
            if existing:
                return existing
            raise DatabaseOperationError(
                operation="create",
                message="Duplicate key error but document not found",
                details={"url": metadata.normalized_url}
            )
            
        except PyMongoError as e:
            logger.error(f"Failed to create metadata document: {str(e)}")
            raise DatabaseOperationError(
                operation="create",
                message="Failed to create metadata document",
                details={"url": metadata.normalized_url, "error": str(e)}
            )
    
    async def update(
        self,
        normalized_url: str,
        update_data: dict
    ) -> Optional[MetadataDocument]:
        """
        Update an existing metadata document.
        
        Args:
            normalized_url: URL of the document to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated MetadataDocument if found, None otherwise
        """
        try:
            # Always update the updated_at timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            result = await self._collection.find_one_and_update(
                {"normalized_url": normalized_url},
                {"$set": update_data},
                return_document=True
            )
            
            if result is None:
                logger.warning(
                    f"No metadata document found to update: {normalized_url}"
                )
                return None
            
            logger.info(f"Updated metadata document for URL: {normalized_url}")
            return self._document_to_model(result)
            
        except PyMongoError as e:
            logger.error(f"Failed to update metadata document: {str(e)}")
            raise DatabaseOperationError(
                operation="update",
                message="Failed to update metadata document",
                details={"url": normalized_url, "error": str(e)}
            )
    
    async def upsert(self, metadata: MetadataDocument) -> MetadataDocument:
        """
        Insert or update a metadata document.
        
        Args:
            metadata: MetadataDocument to upsert
            
        Returns:
            Upserted MetadataDocument
        """
        try:
            # Exclude timestamp fields - they're handled by MongoDB operators
            doc = self._model_to_document(metadata, exclude={"created_at", "updated_at"})
            
            result = await self._collection.find_one_and_update(
                {"normalized_url": metadata.normalized_url},
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                    "$currentDate": {"updated_at": True}
                },
                upsert=True,
                return_document=True
            )
            
            logger.info(
                f"Upserted metadata document for URL: {metadata.normalized_url}"
            )
            return self._document_to_model(result)
            
        except PyMongoError as e:
            logger.error(f"Failed to upsert metadata document: {str(e)}")
            raise DatabaseOperationError(
                operation="upsert",
                message="Failed to upsert metadata document",
                details={"url": metadata.normalized_url, "error": str(e)}
            )
    
    async def delete(self, normalized_url: str) -> bool:
        """
        Delete a metadata document by URL.
        
        Args:
            normalized_url: URL of the document to delete
            
        Returns:
            True if document was deleted, False if not found
        """
        try:
            result = await self._collection.delete_one(
                {"normalized_url": normalized_url}
            )
            
            if result.deleted_count > 0:
                logger.info(
                    f"Deleted metadata document for URL: {normalized_url}"
                )
                return True
            
            return False
            
        except PyMongoError as e:
            logger.error(f"Failed to delete metadata document: {str(e)}")
            raise DatabaseOperationError(
                operation="delete",
                message="Failed to delete metadata document",
                details={"url": normalized_url, "error": str(e)}
            )
    
    async def exists(self, normalized_url: str) -> bool:
        """
        Check if metadata exists for a URL.
        
        Args:
            normalized_url: URL to check
            
        Returns:
            True if metadata exists, False otherwise
        """
        try:
            count = await self._collection.count_documents(
                {"normalized_url": normalized_url},
                limit=1
            )
            return count > 0
            
        except PyMongoError as e:
            logger.error(f"Failed to check metadata existence: {str(e)}")
            raise DatabaseOperationError(
                operation="exists",
                message="Failed to check metadata existence",
                details={"url": normalized_url, "error": str(e)}
            )
    
    async def find_by_status(
        self,
        status: CollectionStatus,
        limit: int = 100
    ) -> list[MetadataDocument]:
        """
        Find metadata documents by collection status.
        
        Args:
            status: Collection status to filter by
            limit: Maximum number of documents to return
            
        Returns:
            List of matching MetadataDocuments
        """
        try:
            cursor = self._collection.find(
                {"collection_status": status.value}
            ).limit(limit).sort("created_at", 1)
            
            documents = []
            async for doc in cursor:
                documents.append(self._document_to_model(doc))
            
            return documents
            
        except PyMongoError as e:
            logger.error(f"Failed to find metadata by status: {str(e)}")
            raise DatabaseOperationError(
                operation="find_by_status",
                message="Failed to find metadata by status",
                details={"status": status.value, "error": str(e)}
            )
    
    def _model_to_document(
        self,
        model: MetadataDocument,
        exclude: set[str] | None = None
    ) -> dict:
        """Convert Pydantic model to MongoDB document."""
        doc = model.model_dump(by_alias=True, exclude_none=False, exclude=exclude)
        
        # Convert enum to string value
        if "collection_status" in doc and isinstance(doc["collection_status"], CollectionStatus):
            doc["collection_status"] = doc["collection_status"].value
        
        # Convert cookies to dicts
        if "cookies" in doc:
            doc["cookies"] = [
                c.model_dump(by_alias=True) if isinstance(c, CookieInfo) else c
                for c in doc["cookies"]
            ]
        
        return doc
    
    def _document_to_model(self, doc: dict) -> MetadataDocument:
        """Convert MongoDB document to Pydantic model."""
        # Remove MongoDB _id field
        doc.pop("_id", None)
        
        # Convert cookies from dicts to CookieInfo
        if "cookies" in doc and doc["cookies"]:
            doc["cookies"] = [
                CookieInfo(**c) if isinstance(c, dict) else c
                for c in doc["cookies"]
            ]
        
        # Convert collection_status string to enum
        if "collection_status" in doc and isinstance(doc["collection_status"], str):
            doc["collection_status"] = CollectionStatus(doc["collection_status"])
        
        return MetadataDocument(**doc)
