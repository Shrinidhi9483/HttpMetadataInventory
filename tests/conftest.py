"""
Pytest configuration and fixtures for the test suite.

This module provides shared fixtures and configuration for
all tests in the application.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import Settings, get_settings
from src.models.metadata import CollectionStatus, CookieInfo, MetadataDocument
from src.repositories.database import Database, database
from src.repositories.metadata_repository import MetadataRepository
from src.services.collector import URLCollector
from src.services.metadata_service import MetadataService
from src.workers.background_tasks import BackgroundTaskManager, task_manager


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Test App with Mocked Lifespan
# ============================================================================

@asynccontextmanager
async def mock_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Mock lifespan that doesn't connect to database."""
    yield


def create_test_app() -> FastAPI:
    """Create a test application with mocked lifespan and dependencies."""
    from src.api.routes import health, metadata
    from src.api.dependencies import get_metadata_service
    from src.core.config import get_settings
    from src.main import register_exception_handlers
    from src.repositories.metadata_repository import MetadataRepository
    from src.services.collector import URLCollector
    from src.services.metadata_service import MetadataService
    
    settings = get_settings()
    
    test_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=mock_lifespan
    )
    
    register_exception_handlers(test_app)
    test_app.include_router(health.router)
    test_app.include_router(metadata.router, prefix=settings.api_prefix)
    
    # Override the metadata service dependency with a mock
    mock_db = MagicMock(spec=AsyncIOMotorDatabase)
    mock_collection = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.insert_one = AsyncMock()
    mock_collection.update_one = AsyncMock()
    
    async def mock_get_metadata_service() -> MetadataService:
        mock_repository = MetadataRepository(mock_db)
        collector = URLCollector()
        return MetadataService(mock_repository, collector)
    
    test_app.dependency_overrides[get_metadata_service] = mock_get_metadata_service
    
    return test_app


# ============================================================================
# Settings Fixtures
# ============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with defaults."""
    return Settings(
        app_name="Test Metadata Inventory",
        app_version="1.0.0-test",
        debug=True,
        mongodb_url="mongodb://localhost:27017",
        mongodb_database="test_metadata_inventory",
        http_timeout=10.0,
        http_max_retries=2,
        worker_pool_size=2,
    )


@pytest.fixture
def mock_settings(test_settings: Settings) -> Generator[Settings, None, None]:
    """Mock the get_settings function to return test settings."""
    with patch("src.core.config.get_settings", return_value=test_settings):
        yield test_settings


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def mock_database() -> MagicMock:
    """Create a mock database instance."""
    mock_db = MagicMock(spec=AsyncIOMotorDatabase)
    mock_collection = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db


@pytest_asyncio.fixture
async def mock_motor_database() -> AsyncGenerator[AsyncMock, None]:
    """Create an async mock for motor database."""
    mock_db = AsyncMock(spec=AsyncIOMotorDatabase)
    mock_collection = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.metadata = mock_collection
    yield mock_db


@pytest.fixture
def mock_database_instance() -> MagicMock:
    """Create a mock Database singleton."""
    mock = MagicMock(spec=Database)
    mock.health_check = AsyncMock(return_value=True)
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    return mock


# ============================================================================
# Repository Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def metadata_repository(
    mock_motor_database: AsyncMock
) -> MetadataRepository:
    """Create a MetadataRepository with mock database."""
    return MetadataRepository(mock_motor_database)


@pytest.fixture
def mock_metadata_repository() -> AsyncMock:
    """Create a mock MetadataRepository."""
    mock = AsyncMock(spec=MetadataRepository)
    return mock


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def url_collector() -> URLCollector:
    """Create a URLCollector instance for testing."""
    return URLCollector(timeout=5.0, max_retries=1)


@pytest.fixture
def mock_url_collector() -> AsyncMock:
    """Create a mock URLCollector."""
    mock = AsyncMock(spec=URLCollector)
    mock.validate_url = URLCollector.validate_url
    mock.normalize_url = URLCollector.normalize_url
    return mock


@pytest_asyncio.fixture
async def metadata_service(
    mock_metadata_repository: AsyncMock,
    mock_url_collector: AsyncMock
) -> MetadataService:
    """Create a MetadataService with mocks."""
    return MetadataService(mock_metadata_repository, mock_url_collector)


# ============================================================================
# Worker Fixtures
# ============================================================================

@pytest.fixture
def mock_task_manager() -> MagicMock:
    """Create a mock BackgroundTaskManager."""
    mock = MagicMock(spec=BackgroundTaskManager)
    mock.add_task = MagicMock(return_value=None)
    mock.pending_count = 0
    mock.is_shutdown = False
    return mock


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_url() -> str:
    """Sample URL for testing."""
    return "https://example.com"


@pytest.fixture
def sample_normalized_url() -> str:
    """Sample normalized URL for testing."""
    return "https://example.com/"


@pytest.fixture
def sample_headers() -> dict[str, str]:
    """Sample HTTP headers."""
    return {
        "content-type": "text/html; charset=utf-8",
        "server": "nginx",
        "date": "Thu, 01 Jan 2024 00:00:00 GMT",
        "content-length": "1234",
    }


@pytest.fixture
def sample_cookies() -> list[CookieInfo]:
    """Sample cookies."""
    return [
        CookieInfo(
            name="session_id",
            value="abc123",
            domain="example.com",
            path="/",
            secure=True,
            http_only=True,
        ),
        CookieInfo(
            name="tracking",
            value="xyz789",
            domain="example.com",
            path="/",
            secure=False,
            http_only=False,
        ),
    ]


@pytest.fixture
def sample_page_source() -> str:
    """Sample HTML page source."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Example Domain</title></head>
    <body>
        <h1>Example Domain</h1>
        <p>This domain is for use in illustrative examples.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_metadata_document(
    sample_url: str,
    sample_normalized_url: str,
    sample_headers: dict[str, str],
    sample_cookies: list[CookieInfo],
    sample_page_source: str
) -> MetadataDocument:
    """Create a sample MetadataDocument."""
    return MetadataDocument(
        url=sample_url,
        normalized_url=sample_normalized_url,
        headers=sample_headers,
        cookies=sample_cookies,
        page_source=sample_page_source,
        status_code=200,
        collection_status=CollectionStatus.COMPLETED,
    )


@pytest.fixture
def sample_pending_document(
    sample_url: str,
    sample_normalized_url: str
) -> MetadataDocument:
    """Create a sample pending MetadataDocument."""
    return MetadataDocument(
        url=sample_url,
        normalized_url=sample_normalized_url,
        collection_status=CollectionStatus.PENDING,
    )


@pytest.fixture
def sample_collected_data(
    sample_headers: dict[str, str],
    sample_cookies: list[CookieInfo],
    sample_page_source: str
) -> dict:
    """Sample collected data from URL."""
    return {
        "headers": sample_headers,
        "cookies": sample_cookies,
        "page_source": sample_page_source,
        "status_code": 200,
    }


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for synchronous tests with mocked lifespan."""
    test_app = create_test_app()
    with TestClient(test_app) as client:
        yield client


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    test_app = create_test_app()
    async with AsyncClient(
        app=test_app,
        base_url="http://test"
    ) as client:
        yield client


# ============================================================================
# Mock HTTP Responses
# ============================================================================

@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {
        "content-type": "text/html; charset=utf-8",
        "server": "nginx",
    }
    response.text = "<html><body>Test</body></html>"
    response.cookies = MagicMock()
    response.cookies.jar = []
    return response
