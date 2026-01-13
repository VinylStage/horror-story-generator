"""
Job operation schemas.

Phase B+: Trigger-based API layer schemas.
v1.3.0: Added webhook notification support.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


# Default webhook events (all terminal states except cancelled)
DEFAULT_WEBHOOK_EVENTS = ["succeeded", "failed", "skipped"]


class StoryTriggerRequest(BaseModel):
    """Request to trigger story generation job."""

    max_stories: int = Field(default=1, ge=1, le=100, description="Maximum stories to generate")
    duration_seconds: Optional[int] = Field(default=None, ge=1, description="Duration limit in seconds")
    interval_seconds: int = Field(default=0, ge=0, description="Interval between stories")
    enable_dedup: bool = Field(default=False, description="Enable deduplication check")
    db_path: Optional[str] = Field(default=None, description="Custom database path")
    load_history: bool = Field(default=False, description="Load story history on startup")
    model: Optional[str] = Field(
        default=None,
        description="Model selection. Default: Claude Sonnet. Format: 'ollama:llama3', 'ollama:qwen', or Claude model name"
    )
    # Webhook fields (v1.3.0)
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL to POST webhook notification on job completion"
    )
    webhook_events: List[str] = Field(
        default=DEFAULT_WEBHOOK_EVENTS,
        description="Events that trigger webhook: succeeded, failed, skipped"
    )


class ResearchTriggerRequest(BaseModel):
    """Request to trigger research generation job."""

    topic: str = Field(..., description="Research topic to analyze")
    tags: List[str] = Field(default=[], description="Optional tags for categorization")
    model: Optional[str] = Field(default=None, description="Ollama model override")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")
    # Webhook fields (v1.3.0)
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL to POST webhook notification on job completion"
    )
    webhook_events: List[str] = Field(
        default=DEFAULT_WEBHOOK_EVENTS,
        description="Events that trigger webhook: succeeded, failed, skipped"
    )


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
    # Webhook fields (v1.3.0)
    webhook_url: Optional[str] = None
    webhook_events: List[str] = Field(default=[])
    webhook_sent: bool = False
    webhook_error: Optional[str] = None


class JobListResponse(BaseModel):
    """Response from job list endpoint."""

    jobs: List[JobStatusResponse] = Field(default=[])
    total: int
    message: Optional[str] = None


class JobCancelResponse(BaseModel):
    """Response from job cancel endpoint."""

    job_id: str
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class JobMonitorResult(BaseModel):
    """Result of monitoring a single job."""

    job_id: str
    status: Optional[str] = None
    pid: Optional[int] = None
    artifacts: List[str] = Field(default=[])
    error: Optional[str] = None
    message: Optional[str] = None
    reason: Optional[str] = None  # v1.3.0: Skip reason for skipped jobs
    webhook_processed: bool = False  # v1.3.0: Whether webhook was processed


class JobMonitorResponse(BaseModel):
    """Response from job monitor endpoint."""

    monitored_count: int
    results: List[JobMonitorResult] = Field(default=[])


class JobDedupCheckResponse(BaseModel):
    """Response from job dedup check endpoint."""

    job_id: str
    has_artifact: bool = Field(default=False, description="Whether job produced an artifact")
    artifact_path: Optional[str] = None
    signal: Optional[str] = Field(default=None, description="Dedup signal (LOW/MEDIUM/HIGH)")
    similarity_score: Optional[float] = Field(default=None, description="Similarity score")
    message: Optional[str] = None
