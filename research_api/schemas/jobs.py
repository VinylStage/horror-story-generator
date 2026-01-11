"""
Job operation schemas.

Phase B+: Trigger-based API layer schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class StoryTriggerRequest(BaseModel):
    """Request to trigger story generation job."""

    max_stories: int = Field(default=1, ge=1, le=100, description="Maximum stories to generate")
    duration_seconds: Optional[int] = Field(default=None, ge=1, description="Duration limit in seconds")
    interval_seconds: int = Field(default=0, ge=0, description="Interval between stories")
    enable_dedup: bool = Field(default=False, description="Enable deduplication check")
    db_path: Optional[str] = Field(default=None, description="Custom database path")
    load_history: bool = Field(default=False, description="Load story history on startup")


class ResearchTriggerRequest(BaseModel):
    """Request to trigger research generation job."""

    topic: str = Field(..., description="Research topic to analyze")
    tags: List[str] = Field(default=[], description="Optional tags for categorization")
    model: Optional[str] = Field(default=None, description="Ollama model override")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")


class JobTriggerResponse(BaseModel):
    """Response from job trigger endpoint."""

    job_id: str = Field(..., description="Created job ID")
    type: str = Field(..., description="Job type (story_generation or research)")
    status: str = Field(..., description="Initial job status")
    message: str = Field(default="Job triggered successfully", description="Status message")


class JobStatusResponse(BaseModel):
    """Response from job status endpoint."""

    job_id: str
    type: str
    status: str
    params: dict = Field(default_factory=dict)
    pid: Optional[int] = None
    log_path: Optional[str] = None
    artifacts: List[str] = Field(default=[])
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None


class JobListResponse(BaseModel):
    """Response from job list endpoint."""

    jobs: List[JobStatusResponse] = Field(default=[])
    total: int
    message: Optional[str] = None
