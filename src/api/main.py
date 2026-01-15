"""
FastAPI application entry point.

Local-only server for research operations.

Phase B+: Includes Ollama resource management with auto-cleanup.
Phase C: Optional API key authentication.
"""

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI

from src import __version__
from .routers import research, dedup, jobs, story
from .services.ollama_resource import (
    startup_resource_manager,
    shutdown_resource_manager,
    get_resource_manager,
)
from .dependencies.auth import verify_api_key, API_AUTH_ENABLED


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown of resources:
    - Ollama resource manager for model lifecycle
    """
    # Startup
    await startup_resource_manager()

    yield

    # Shutdown - cleanup Ollama models
    await shutdown_resource_manager()

# Tag metadata for Swagger UI
tags_metadata = [
    {
        "name": "story",
        "description": "Story generation and listing - direct (blocking) story generation and registry queries",
    },
    {
        "name": "jobs",
        "description": "Trigger-based job execution - non-blocking story and research generation via CLI subprocess",
    },
    {
        "name": "research",
        "description": "Research card operations - generate, validate, and list research cards via Ollama LLM",
    },
    {
        "name": "dedup",
        "description": "Deduplication signal evaluation - check story similarity against existing registry",
    },
]

app = FastAPI(
    title="Horror Story Research API",
    lifespan=lifespan,
    description="""
## Horror Story Research API

Local-only API server for research card management and deduplication signal evaluation.

### Authentication
When `API_AUTH_ENABLED=true`, all endpoints except `/health` and `/resource/status` require
an `X-API-Key` header matching the `API_KEY` environment variable.

### Features
- **Research Cards**: Generate horror research cards using local Ollama LLM
- **Validation**: Validate existing research card quality
- **Listing**: Browse and filter research cards
- **Dedup Signals**: Evaluate story similarity (LOW/MEDIUM/HIGH)

### Usage
```bash
# Start server
poetry run uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# Generate research (with auth)
curl -X POST http://localhost:8000/research/run \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{"topic": "Korean apartment horror"}'
```

### Note
This API is designed for **local use only**. All operations connect to local Ollama instance.
    """,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "VinylStage",
        "email": "mcpe9869@gmail.com",
    },
    license_info={
        "name": "Private",
    },
)

# Health check - NO authentication (operational endpoints)
@app.get("/health")
async def health_check():
    """Health check endpoint. Not authenticated."""
    return {"status": "ok", "version": __version__}


@app.get("/resource/status")
async def resource_status():
    """
    Get Ollama resource manager status.

    Shows active models, idle timeout configuration, and cleanup status.
    Not authenticated (operational endpoint).
    """
    manager = get_resource_manager()
    return manager.get_status()


# Include routers WITH authentication dependency (when enabled)
auth_dependency = [Depends(verify_api_key)] if API_AUTH_ENABLED else []

app.include_router(
    story.router, prefix="/story", tags=["story"], dependencies=auth_dependency
)
app.include_router(
    jobs.router, prefix="/jobs", tags=["jobs"], dependencies=auth_dependency
)
app.include_router(
    research.router, prefix="/research", tags=["research"], dependencies=auth_dependency
)
app.include_router(
    dedup.router, prefix="/dedup", tags=["dedup"], dependencies=auth_dependency
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
