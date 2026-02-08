"""
Scheduler API schemas.

Phase 3: Scheduler-based execution model API schemas.
Supports /scheduler/* and /tasks CRUD endpoints.
"""

from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field


# =============================================================================
# Task Schemas (was Job)
# =============================================================================


class TaskCreateRequest(BaseModel):
    """Request to create a new task."""
    type: Literal["story", "research"] = Field(..., description="Task type")
    params: dict = Field(default_factory=dict, description="Task parameters")
    priority: int = Field(default=0, ge=0, le=100, description="Task priority")


class TaskUpdateRequest(BaseModel):
    """Request to update a task (QUEUED only)."""
    priority: Optional[int] = Field(default=None, ge=0, le=100, description="New priority")


class TaskResponse(BaseModel):
    """Response representing a Task."""
    task_id: str = Field(..., description="Unique task identifier")
    task_type: str = Field(..., description="Task type (story/research)")
    status: str = Field(..., description="Task status (QUEUED/RUNNING/CANCELLED)")
    params: dict = Field(default_factory=dict)
    priority: int = Field(default=0)
    position: int = Field(default=0)
    template_id: Optional[str] = None
    group_id: Optional[str] = None
    retry_of: Optional[str] = None
    created_at: str
    queued_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """Response for task list endpoint."""
    tasks: List[TaskResponse] = Field(default_factory=list)
    total: int
    queued_count: int = 0
    running_count: int = 0


class TaskBatchResponse(BaseModel):
    """Response when creating multiple tasks at once."""
    tasks: List[TaskResponse] = Field(default_factory=list)
    total: int


class TaskDeleteResponse(BaseModel):
    """Response from task deletion."""
    task_id: str
    success: bool
    message: Optional[str] = None


# =============================================================================
# TaskRun Schemas
# =============================================================================

class TaskRunResponse(BaseModel):
    """Response representing a TaskRun."""
    run_id: str
    task_id: str
    status: Optional[str] = None
    params_snapshot: dict = Field(default_factory=dict)
    template_id: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)
    log_path: Optional[str] = None


class TaskRunListResponse(BaseModel):
    """Response for task runs list endpoint."""
    runs: List[TaskRunResponse] = Field(default_factory=list)
    total: int


# =============================================================================
# TaskGroup Schemas (new)
# =============================================================================

class TaskGroupCreateRequest(BaseModel):
    """Request to create a concurrent task group from existing QUEUED tasks."""
    task_ids: List[str] = Field(..., min_length=1, description="IDs of QUEUED tasks to group")
    mode: Literal["concurrent", "sequential"] = Field(default="concurrent", description="Execution mode")
    name: Optional[str] = Field(default=None, description="Optional group name")


class TaskGroupResponse(BaseModel):
    """Response representing a TaskGroup."""
    group_id: str
    name: Optional[str] = None
    status: str
    execution_mode: str
    tasks: List[TaskResponse] = Field(default_factory=list)
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# =============================================================================
# Scheduler Control Schemas (unchanged)
# =============================================================================

class SchedulerStartRequest(BaseModel):
    run_recovery: bool = Field(default=True)

class SchedulerStartResponse(BaseModel):
    success: bool
    message: str
    recovery_stats: Optional[dict] = None

class SchedulerStopRequest(BaseModel):
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)

class SchedulerStopResponse(BaseModel):
    success: bool
    message: str

class CumulativeStats(BaseModel):
    total_executed: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    skipped: int = 0

class SchedulerStatusResponse(BaseModel):
    scheduler_running: bool
    current_task_id: Optional[str] = None
    queue_length: int = 0
    cumulative_stats: CumulativeStats = Field(default_factory=CumulativeStats)
    has_active_reservation: bool = False


# Backward compatibility aliases
JobCreateRequest = TaskCreateRequest
JobUpdateRequest = TaskUpdateRequest
JobResponse = TaskResponse
JobListResponse = TaskListResponse
JobDeleteResponse = TaskDeleteResponse
JobRunResponse = TaskRunResponse
JobRunListResponse = TaskRunListResponse
