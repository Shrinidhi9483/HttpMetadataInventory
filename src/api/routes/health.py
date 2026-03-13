"""
Health check API routes.

This module provides health check endpoints for monitoring
service and database status.
"""

from fastapi import APIRouter, HTTPException, status

from ...core.config import get_settings
from ...core.logging import logger
from ...models.metadata import HealthCheckResponse
from ...repositories.database import database


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    responses={
        200: {
            "description": "Service is healthy",
            "model": HealthCheckResponse
        },
        503: {
            "description": "Service is unhealthy",
            "model": HealthCheckResponse
        }
    },
    summary="Health check endpoint",
    description="Check the health status of the API and database connection."
)
async def health_check() -> HealthCheckResponse:
    """
    Check service health status.
    
    Returns the status of the API service and database connection.
    """
    settings = get_settings()
    
    # Check database connection
    db_healthy = await database.health_check()
    
    if not db_healthy:
        logger.warning("Health check failed: Database unhealthy")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=HealthCheckResponse(
                status="unhealthy",
                database="disconnected",
                version=settings.app_version
            ).model_dump()
        )
    
    return HealthCheckResponse(
        status="healthy",
        database="connected",
        version=settings.app_version
    )


@router.get(
    "/ready",
    response_model=dict,
    summary="Readiness check",
    description="Check if the service is ready to accept requests."
)
async def readiness_check() -> dict:
    """
    Check if service is ready.
    
    Used by container orchestrators to determine if the
    service should receive traffic.
    """
    db_healthy = await database.health_check()
    
    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ready": False, "reason": "Database not available"}
        )
    
    return {"ready": True}


@router.get(
    "/live",
    response_model=dict,
    summary="Liveness check",
    description="Check if the service is alive."
)
async def liveness_check() -> dict:
    """
    Check if service is alive.
    
    Used by container orchestrators to determine if the
    service should be restarted.
    """
    return {"alive": True}
