"""
Scheduler API schemas.

Phase 3: Scheduler-based execution model API schemas.
Supports /scheduler/* and /jobs CRUD endpoints.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Job Schemas (Scheduler-based)
# =============================================================================


class JobCreateRequest(BaseModel):
    """Request to create a new job."""

    type: Literal["story", "research"] = Field(
        ...,
        description="Job type: 'story' for story generation, 'research' for research generation"
    )
    params: dict = Field(
        default_factory=dict,
        description="Job parameters (type-specific)"
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Job priority (higher = dispatched sooner)"
    )


class JobUpdateRequest(BaseModel):
    """Request to update a job (QUEUED only)."""

    priority: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="New priority value"
    )


class JobResponse(BaseModel):
    """Response representing a Job."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Job type (story/research)")
    status: str = Field(..., description="Job status (QUEUED/RUNNING/CANCELLED)")
    params: dict = Field(default_factory=dict, description="Job parameters")
    priority: int = Field(default=0, description="Job priority")
    position: int = Field(default=0, description="Queue position")
    template_id: Optional[str] = Field(default=None, description="Source template ID")
    group_id: Optional[str] = Field(default=None, description="Job group ID")
    retry_of: Optional[str] = Field(default=None, description="Original job ID if retry")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    queued_at: str = Field(..., description="Queue entry timestamp (ISO format)")
    started_at: Optional[str] = Field(default=None, description="Execution start timestamp")
    finished_at: Optional[str] = Field(default=None, description="Completion timestamp")


class JobListResponse(BaseModel):
    """Response for job list endpoint."""

    jobs: List[JobResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of jobs")
    queued_count: int = Field(default=0, description="Number of QUEUED jobs")
    running_count: int = Field(default=0, description="Number of RUNNING jobs")


class JobDeleteResponse(BaseModel):
    """Response from job deletion."""

    job_id: str
    success: bool
    message: Optional[str] = None


# =============================================================================
# JobRun Schemas
# =============================================================================


class JobRunResponse(BaseModel):
    """Response representing a JobRun."""

    run_id: str = Field(..., description="Unique run identifier")
    job_id: str = Field(..., description="Associated job ID")
    status: Optional[str] = Field(default=None, description="Run status (COMPLETED/FAILED/SKIPPED)")
    params_snapshot: dict = Field(default_factory=dict, description="Parameters at execution time")
    template_id: Optional[str] = Field(default=None, description="Source template ID")
    started_at: str = Field(..., description="Execution start timestamp")
    finished_at: Optional[str] = Field(default=None, description="Completion timestamp")
    exit_code: Optional[int] = Field(default=None, description="Process exit code")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    artifacts: List[str] = Field(default_factory=list, description="Output artifact paths")
    log_path: Optional[str] = Field(default=None, description="Execution log path")


class JobRunListResponse(BaseModel):
    """Response for job runs list endpoint."""

    runs: List[JobRunResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of runs")


# =============================================================================
# Scheduler Control Schemas
# =============================================================================


class SchedulerStartRequest(BaseModel):
    """Request to start the scheduler."""

    run_recovery: bool = Field(
        default=True,
        description="Whether to run crash recovery on startup"
    )


class SchedulerStartResponse(BaseModel):
    """Response from scheduler start."""

    success: bool
    message: str
    recovery_stats: Optional[dict] = Field(
        default=None,
        description="Recovery statistics if recovery was run"
    )


class SchedulerStopRequest(BaseModel):
    """Request to stop the scheduler."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Maximum wait time for current job to complete (seconds)"
    )


class SchedulerStopResponse(BaseModel):
    """Response from scheduler stop."""

    success: bool
    message: str


class CumulativeStats(BaseModel):
    """Cumulative execution statistics."""

    total_executed: int = Field(default=0, description="Total JobRuns executed")
    succeeded: int = Field(default=0, description="COMPLETED JobRuns")
    failed: int = Field(default=0, description="FAILED JobRuns")
    cancelled: int = Field(default=0, description="CANCELLED Jobs")
    skipped: int = Field(default=0, description="SKIPPED JobRuns")


class SchedulerStatusResponse(BaseModel):
    """Response from scheduler status endpoint."""

    scheduler_running: bool = Field(..., description="Whether scheduler dispatch loop is running")
    current_job_id: Optional[str] = Field(
        default=None,
        description="Currently executing job ID (null if none)"
    )
    queue_length: int = Field(default=0, description="Number of QUEUED jobs")
    cumulative_stats: CumulativeStats = Field(
        default_factory=CumulativeStats,
        description="Cumulative execution statistics"
    )
    has_active_reservation: bool = Field(
        default=False,
        description="Whether a Direct API reservation is active"
    )
