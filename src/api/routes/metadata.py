"""
Metadata API routes.

This module defines the REST API endpoints for metadata
collection and retrieval operations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import HttpUrl

from ...core.exceptions import (
    URLCollectionError,
    URLValidationError,
)
from ...core.logging import logger
from ...models.metadata import (
    CreateMetadataRequest,
    ErrorResponse,
    MetadataAcceptedResponse,
    MetadataCreatedResponse,
    MetadataResponse,
    CollectionStatus,
)
from ...services.metadata_service import MetadataService
from ...workers.background_tasks import schedule_background_task
from ..dependencies import MetadataServiceDep


router = APIRouter(prefix="/metadata", tags=["Metadata"])


@router.post(
    "",
    response_model=MetadataCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Metadata successfully collected and stored",
            "model": MetadataCreatedResponse
        },
        400: {
            "description": "Invalid URL format",
            "model": ErrorResponse
        },
        500: {
            "description": "Failed to collect metadata",
            "model": ErrorResponse
        },
        503: {
            "description": "Service temporarily unavailable",
            "model": ErrorResponse
        }
    },
    summary="Create metadata record",
    description="""
    Collect and store metadata for a given URL.
    
    This endpoint performs synchronous metadata collection:
    - Fetches the URL
    - Extracts HTTP headers, cookies, and page source
    - Stores the data in MongoDB
    
    The operation blocks until collection is complete.
    """
)
async def create_metadata(
    request: CreateMetadataRequest,
    service: MetadataServiceDep
) -> MetadataCreatedResponse:
    """
    Create a metadata record for a URL.
    
    Collects headers, cookies, and page source from the URL
    and stores them in the database.
    """
    url_str = str(request.url)
    
    try:
        document = await service.create_metadata(url_str)
        
        return MetadataCreatedResponse(
            message="Metadata collected successfully",
            url=document.url,
            status=document.collection_status
        )
        
    except URLValidationError as e:
        logger.warning(f"URL validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": e.details
            }
        )
        
    except URLCollectionError as e:
        logger.error(f"URL collection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "CollectionError",
                "message": str(e),
                "details": e.details
            }
        )


@router.get(
    "",
    response_model=MetadataResponse,
    responses={
        200: {
            "description": "Metadata found and returned",
            "model": MetadataResponse
        },
        202: {
            "description": "Metadata not found, collection scheduled",
            "model": MetadataAcceptedResponse
        },
        400: {
            "description": "Invalid URL format",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Retrieve metadata for a URL",
    description="""
    Retrieve stored metadata for a given URL.
    
    **Workflow:**
    - If metadata exists in the database, return it immediately (200 OK)
    - If metadata doesn't exist, schedule background collection and return 202 Accepted
    
    The 202 response indicates the request has been logged and 
    metadata will be available for future requests.
    """
)
async def get_metadata(
    url: Annotated[HttpUrl, Query(description="URL to retrieve metadata for")],
    service: MetadataServiceDep
) -> MetadataResponse:
    """
    Retrieve metadata for a URL.
    
    Returns existing metadata if available, otherwise triggers
    background collection and returns 202 Accepted.
    """
    url_str = str(url)
    
    try:
        metadata_response, should_trigger_background = await service.get_metadata(url_str)
        
        if metadata_response is not None:
            # Metadata exists and is complete
            return metadata_response
        
        # Metadata not found - trigger background collection if needed
        if should_trigger_background:
            # Schedule background task for collection
            schedule_background_task(
                service.collect_metadata_background(url_str),
                task_name=f"collect:{url_str}"
            )
        
        # Return 202 Accepted
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                "message": "Request accepted. Metadata collection scheduled.",
                "url": url_str,
                "status": CollectionStatus.PENDING.value
            }
        )
        
    except URLValidationError as e:
        logger.warning(f"URL validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": e.details
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (like our 202)
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error retrieving metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )
