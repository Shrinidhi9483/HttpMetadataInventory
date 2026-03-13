# HTTP Metadata Inventory

A production-ready FastAPI service for collecting and storing HTTP metadata from URLs, including headers, cookies, and page source content.

## 🚀 Features

- **POST /api/v1/metadata**: Collect and store metadata for a given URL synchronously
- **GET /api/v1/metadata**: Retrieve stored metadata, with automatic background collection for cache misses
- **Background Processing**: Asynchronous metadata collection that doesn't block API responses
- **MongoDB Storage**: Persistent storage with optimized indexing for fast lookups
- **Docker Compose**: One-command deployment with `docker-compose up`
- **Comprehensive Tests**: Unit and integration tests with pytest
- **Production Ready**: Type hints, proper error handling, logging, and health checks

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [API Documentation](#-api-documentation)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [Project Structure](#-project-structure)

## 🏃 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Running with Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd httpMetadataInventory

# Start the services
docker-compose up

# Or run in detached mode
docker-compose up -d
```

The API will be available at `http://localhost:8000`

### Running Locally

```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Start MongoDB (ensure it's running on localhost:27017)
# You can use Docker for just MongoDB:
docker run -d -p 27017:27017 --name mongodb mongo:7.0

# Copy environment file and configure
cp .env.example .env
# Edit .env to set MONGODB_URL=mongodb://localhost:27017

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 🏗 Architecture

The application follows a clean architecture pattern with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                       API Layer                             │
│  (FastAPI routes, request/response handling, validation)    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Service Layer                            │
│  (Business logic, orchestration, background task mgmt)      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Repository Layer                          │
│  (Data access, MongoDB operations, document mapping)        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      MongoDB                                │
│       (Document storage, indexing)                          │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **API Layer** (`src/api/`): FastAPI routes and dependency injection
- **Services** (`src/services/`): Business logic and URL collection
- **Repositories** (`src/repositories/`): Data access layer with MongoDB
- **Workers** (`src/workers/`): Background task management
- **Models** (`src/models/`): Pydantic models for validation
- **Core** (`src/core/`): Configuration, exceptions, and logging

## 📚 API Documentation

Once the service is running, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Endpoints

#### POST /api/v1/metadata

Create a metadata record for a given URL.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response (201 Created):**
```json
{
  "message": "Metadata collected successfully",
  "url": "https://example.com",
  "status": "completed"
}
```

#### GET /api/v1/metadata

Retrieve metadata for a given URL.

**Request:**
```
GET /api/v1/metadata?url=https://example.com
```

**Response (200 OK)** - When metadata exists:
```json
{
  "url": "https://example.com",
  "headers": {
    "content-type": "text/html; charset=utf-8",
    "server": "nginx"
  },
  "cookies": [
    {
      "name": "session",
      "value": "abc123",
      "domain": "example.com",
      "path": "/",
      "secure": true,
      "httpOnly": true
    }
  ],
  "page_source": "<!DOCTYPE html>...",
  "status_code": 200,
  "collected_at": "2024-01-01T00:00:00Z"
}
```

**Response (202 Accepted)** - When metadata doesn't exist:
```json
{
  "message": "Request accepted. Metadata collection scheduled.",
  "url": "https://example.com",
  "status": "pending"
}
```

#### Health Endpoints

- **GET /health**: Full health check (service + database)
- **GET /live**: Liveness probe (is service running?)
- **GET /ready**: Readiness probe (is service ready to accept traffic?)

## ⚙️ Configuration

Configuration is managed through environment variables. See `.env.example` for all options.

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | HTTP Metadata Inventory |
| `APP_VERSION` | Application version | 1.0.0 |
| `DEBUG` | Enable debug mode | false |
| `MONGODB_URL` | MongoDB connection URL | mongodb://mongodb:27017 |
| `MONGODB_DATABASE` | Database name | metadata_inventory |
| `MONGODB_MAX_POOL_SIZE` | Max connection pool size | 10 |
| `HTTP_TIMEOUT` | HTTP request timeout (seconds) | 30.0 |
| `HTTP_MAX_RETRIES` | Max retry attempts | 3 |
| `WORKER_POOL_SIZE` | Background worker pool size | 5 |
| `API_PREFIX` | API route prefix | /api/v1 |

## 🛠 Development

### Setting Up Development Environment

```bash
# Clone and enter directory
git clone <repository-url>
cd httpMetadataInventory

# Create virtual environment with uv
uv venv
source .venv/bin/activate

# Install all dependencies including dev
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Quality

```bash
# Run linting
ruff check src tests

# Run type checking
mypy src

# Format code
ruff format src tests
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_services/test_collector.py

# Run with verbose output
pytest -v

# Run only unit tests (exclude integration)
pytest -m "not integration"
```

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_api/
│   └── test_metadata_routes.py    # API endpoint tests
├── test_services/
│   ├── test_collector.py          # URL collector tests
│   └── test_metadata_service.py   # Service layer tests
├── test_repositories/
│   └── test_metadata_repository.py # Repository tests
└── test_workers/
    └── test_background_tasks.py   # Background worker tests
```

## 📁 Project Structure

```
httpMetadataInventory/
├── src/
│   ├── main.py                 # Application entry point
│   ├── api/
│   │   ├── dependencies.py     # FastAPI dependency injection
│   │   └── routes/
│   │       ├── metadata.py     # Metadata API routes
│   │       └── health.py       # Health check routes
│   ├── core/
│   │   ├── config.py           # Application configuration
│   │   ├── exceptions.py       # Custom exceptions
│   │   └── logging.py          # Logging configuration
│   ├── models/
│   │   └── metadata.py         # Pydantic models
│   ├── repositories/
│   │   ├── database.py         # MongoDB connection
│   │   └── metadata_repository.py # Data access layer
│   ├── services/
│   │   ├── collector.py        # URL collection service
│   │   └── metadata_service.py # Business logic service
│   └── workers/
│       └── background_tasks.py # Background task management
├── tests/                      # Test suite
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Docker build configuration
├── pyproject.toml              # Project configuration
├── .env.example                # Environment template
└── README.md                   # This file
```

## 🐳 Docker

### Building the Image

```bash
docker build -t metadata-inventory .
```

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild and start
docker-compose up --build
```

> 💡 **Optional SSL certs:** If you want to use your own TLS certificate/key, place `certs/cert.pem` and `certs/key.pem` in the project `certs/` folder **before** running `docker-compose up`. If those files are not present, the container will generate a self-signed certificate automatically.

## 📊 Database Schema

The MongoDB collection uses the following document structure:

```javascript
{
  "url": "https://example.com",           // Original URL
  "normalized_url": "https://example.com/", // Normalized for lookups
  "headers": {                             // HTTP response headers
    "content-type": "text/html",
    "server": "nginx"
  },
  "cookies": [{                            // Cookies from response
    "name": "session",
    "value": "abc123",
    "domain": "example.com",
    "path": "/",
    "secure": true,
    "httpOnly": true
  }],
  "page_source": "<!DOCTYPE html>...",     // HTML content
  "status_code": 200,                      // HTTP status code
  "collection_status": "completed",        // pending|in_progress|completed|failed
  "error_message": null,                   // Error details if failed
  "collected_at": ISODate("..."),          // When metadata was collected
  "created_at": ISODate("..."),            // Document creation time
  "updated_at": ISODate("...")             // Last update time
}
```

### Indexes

- `normalized_url` (unique): Fast lookups by URL
- `collection_status`: Filter by status
- `collection_status, created_at`: Compound index for status queries
- `created_at`: Time-based queries

## 🔒 Security Considerations

- Non-root Docker user
- Environment-based configuration
- Input validation with Pydantic
- Error message sanitization in production

## 📝 License

MIT License - See LICENSE file for details.
