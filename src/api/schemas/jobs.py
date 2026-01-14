"""
Job operation schemas.

Phase B+: Trigger-based API layer schemas.
v1.3.0: Added webhook notification support.
v1.4.0: Added batch job support.
"""

from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field


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
        description="Model selection. Options: null (Claude Sonnet default), 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101', 'ollama:qwen3:30b' (local Ollama)",
        json_schema_extra={"examples": [None, "claude-sonnet-4-5-20250929", "ollama:qwen3:30b"]}
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

    topic: str = Field(..., description="Research topic to analyze", json_schema_extra={"examples": ["Korean apartment horror", "Urban isolation fear"]})
    tags: List[str] = Field(default=[], description="Optional tags for categorization", json_schema_extra={"examples": [["urban", "isolation"], ["supernatural"]]})
    model: Optional[str] = Field(
        default=None,
        description="Model selection. Options: null/'qwen3:30b' (Ollama default), 'gemini' (Gemini API), 'deep-research' (Gemini Deep Research Agent - recommended for high quality). Gemini requires GEMINI_ENABLED=true",
        json_schema_extra={"examples": ["qwen3:30b", "gemini", "deep-research"]}
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds. Recommended: 60 (Ollama), 120 (gemini), 300-600 (deep-research)",
        json_schema_extra={"examples": [60, 120, 300]}
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


# =============================================================================
# Batch Job Schemas (v1.4.0)
# =============================================================================


class BatchJobSpec(BaseModel):
    """Specification for a single job in a batch."""

    type: Literal["research", "story"] = Field(..., description="Job type")
    # Research job fields
    topic: Optional[str] = Field(default=None, description="Research topic (required for research jobs)")
    tags: List[str] = Field(default=[], description="Tags for research job")
    # Story job fields
    max_stories: int = Field(default=1, ge=1, le=100, description="Max stories for story job")
    enable_dedup: bool = Field(default=False, description="Enable dedup for story job")
    # Common fields
    model: Optional[str] = Field(default=None, description="Model override")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")


class BatchTriggerRequest(BaseModel):
    """Request to trigger multiple jobs as a batch."""

    jobs: List[BatchJobSpec] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of job specifications"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL to POST when all batch jobs complete"
    )
    webhook_events: List[str] = Field(
        default=DEFAULT_WEBHOOK_EVENTS,
        description="Events that trigger webhook"
    )


class BatchTriggerResponse(BaseModel):
    """Response from batch trigger endpoint."""

    batch_id: str = Field(..., description="Created batch ID")
    job_ids: List[str] = Field(..., description="List of created job IDs")
    job_count: int = Field(..., description="Number of jobs in batch")
    status: str = Field(default="queued", description="Initial batch status")
    message: str = Field(default="Batch triggered successfully")


class BatchJobStatus(BaseModel):
    """Status of a single job within a batch."""

    job_id: str
    type: str
    status: str
    error: Optional[str] = None


class BatchStatusResponse(BaseModel):
    """Response from batch status endpoint."""

    batch_id: str
    status: str = Field(..., description="Aggregate batch status")
    total_jobs: int
    completed_jobs: int
    succeeded_jobs: int
    failed_jobs: int
    running_jobs: int
    queued_jobs: int
    jobs: List[BatchJobStatus] = Field(default=[], description="Individual job statuses")
    created_at: str
    finished_at: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_sent: bool = False
    message: Optional[str] = None
