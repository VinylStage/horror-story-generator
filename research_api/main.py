"""
FastAPI application entry point.

Local-only server for research operations.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .routers import research, dedup

# Tag metadata for Swagger UI
tags_metadata = [
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
    description="""
## Horror Story Research API

Local-only API server for research card management and deduplication signal evaluation.

### Features
- **Research Cards**: Generate horror research cards using local Ollama LLM
- **Validation**: Validate existing research card quality
- **Listing**: Browse and filter research cards
- **Dedup Signals**: Evaluate story similarity (LOW/MEDIUM/HIGH)

### Usage
```bash
# Start server
poetry run uvicorn research_api.main:app --host 127.0.0.1 --port 8000

# Generate research
curl -X POST http://localhost:8000/research/run -H "Content-Type: application/json" -d '{"topic": "Korean apartment horror"}'
```

### Note
This API is designed for **local use only**. All operations connect to local Ollama instance.
    """,
    version="0.1.0",
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

# Include routers
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(dedup.router, prefix="/dedup", tags=["dedup"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
