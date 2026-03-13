"""
HTTP Metadata Inventory - Main Application Entry Point.

This module initializes and configures the FastAPI application,
including routes, middleware, exception handlers, and lifecycle
management.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import health, metadata
from .core.config import get_settings
from .core.exceptions import (
    BaseAppException,
    DatabaseConnectionError,
    URLCollectionError,
    URLValidationError,
)
from .core.logging import logger
from .repositories.database import database
from .workers.background_tasks import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events, including database
    connection management and background task cleanup.
    """
    # Startup
    logger.info("Starting HTTP Metadata Inventory service...")
    
    try:
        # Connect to database with retry logic
        await database.connect(max_retries=10, retry_delay=3.0)
        logger.info("Application startup complete")
    except DatabaseConnectionError as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        # Allow app to start even if DB is temporarily unavailable
        # The health check will reflect the actual status
    
    yield
    
    # Shutdown
    logger.info("Shutting down HTTP Metadata Inventory service...")
    
    # Gracefully shutdown background tasks
    await task_manager.shutdown(timeout=30.0)
    
    # Disconnect from database
    await database.disconnect()
    
    logger.info("Application shutdown complete")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        HTTP Metadata Inventory API
        
        A service for collecting and storing HTTP metadata from URLs,
        including headers, cookies, and page source content.
        
        ## Features
        
        - **POST /api/v1/metadata**: Collect and store metadata for a URL
        - **GET /api/v1/metadata**: Retrieve stored metadata for a URL
        - Background collection for efficient request handling
        - MongoDB storage with optimized indexing
        
        ## Background Collection
        
        When requesting metadata for a URL not in the database, the service
        returns a 202 Accepted response and schedules background collection.
        The metadata will be available for subsequent requests.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Register routes
    app.include_router(health.router)
    app.include_router(metadata.router, prefix=settings.api_prefix)
    
    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        )
    
    @app.exception_handler(URLValidationError)
    async def url_validation_exception_handler(
        request: Request,
        exc: URLValidationError
    ) -> JSONResponse:
        """Handle URL validation errors."""
        logger.warning(f"URL validation error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "URLValidationError",
                "message": exc.message,
                "details": exc.details
            }
        )
    
    @app.exception_handler(URLCollectionError)
    async def url_collection_exception_handler(
        request: Request,
        exc: URLCollectionError
    ) -> JSONResponse:
        """Handle URL collection errors."""
        logger.error(f"URL collection error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "URLCollectionError",
                "message": exc.message,
                "details": exc.details
            }
        )
    
    @app.exception_handler(DatabaseConnectionError)
    async def database_exception_handler(
        request: Request,
        exc: DatabaseConnectionError
    ) -> JSONResponse:
        """Handle database connection errors."""
        logger.error(f"Database error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "DatabaseError",
                "message": "Database service temporarily unavailable",
                "details": {}
            }
        )
    
    @app.exception_handler(BaseAppException)
    async def base_exception_handler(
        request: Request,
        exc: BaseAppException
    ) -> JSONResponse:
        """Handle all other application exceptions."""
        logger.error(f"Application error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "ApplicationError",
                "message": exc.message,
                "details": exc.details
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(f"Unexpected error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "details": {}
            }
        )


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    
    settings = get_settings()
    
    # SSL certificate paths
    cert_dir = Path(__file__).parent.parent / "certs"
    ssl_keyfile = cert_dir / "key.pem"
    ssl_certfile = cert_dir / "cert.pem"
    
    # Check if SSL certificates exist
    ssl_config = {}
    if ssl_keyfile.exists() and ssl_certfile.exists():
        ssl_config = {
            "ssl_keyfile": str(ssl_keyfile),
            "ssl_certfile": str(ssl_certfile),
        }
        logger.info("Starting server with HTTPS (SSL enabled)")
    else:
        logger.warning("SSL certificates not found, starting with HTTP")
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        **ssl_config
    )