"""
FastAPI application entry point.

Local-only server for research operations.
"""

from fastapi import FastAPI

from .routers import research, dedup

app = FastAPI(
    title="Horror Story Research API",
    description="Local API for research card management and dedup evaluation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
