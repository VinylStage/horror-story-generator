"""
Scheduler Domain Entities.

Follows DOMAIN_MODEL.md exactly:
- JobTemplate: Reusable specification for work
- Schedule: Temporal pattern for automated execution
- Job: Single unit of work queued for execution
- JobRun: Historical record of a single execution attempt
- DirectReservation: Next-slot reservation for Direct API (DEC-004)

Status values follow API_CONTRACT.md Section 2 (Canonical Status Model).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import json
import uuid


class JobStatus(str, Enum):
    """
    Job status values (queue-level, external).

    From API_CONTRACT.md Section 2.1:
    - QUEUED: Waiting in queue
    - RUNNING: Currently executing
    - CANCELLED: Cancelled before completion
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"


class JobRunStatus(str, Enum):
    """
    JobRun status values (execution result, external).

    From API_CONTRACT.md Section 2.2:
    - COMPLETED: Execution finished successfully
    - FAILED: Execution failed
    - SKIPPED: Execution intentionally skipped
    """

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ReservationStatus(str, Enum):
    """
    Direct API reservation status.

    From PERSISTENCE_SCHEMA.md Section 2.5:
    - ACTIVE: Reservation is active, queue dispatch paused
    - RELEASED: Reservation completed normally
    - EXPIRED: Reservation timed out (stale)
    """

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Get current time as ISO format string."""
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class JobTemplate:
    """
    Reusable specification for work that can be executed.

    From DOMAIN_MODEL.md Section 1.
    Captures the "what" and "how" without committing to "when" or "how many times."
    """

    template_id: str
    name: str
    job_type: str  # "story" | "research"
    default_params: dict = field(default_factory=dict)
    retry_policy: dict = field(default_factory=lambda: {"max_attempts": 3})
    description: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        name: str,
        job_type: str,
        default_params: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> "JobTemplate":
        """Create a new JobTemplate with generated ID."""
        return cls(
            template_id=generate_uuid(),
            name=name,
            job_type=job_type,
            default_params=default_params or {},
            retry_policy=retry_policy or {"max_attempts": 3},
            description=description,
        )


@dataclass
class Schedule:
    """
    Defines when work should be executed.

    From DOMAIN_MODEL.md Section 2.
    Binds a JobTemplate to a temporal pattern.
    """

    schedule_id: str
    template_id: str
    name: str
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True
    param_overrides: Optional[dict] = None
    last_triggered_at: Optional[str] = None
    next_trigger_at: Optional[str] = None
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        template_id: str,
        name: str,
        cron_expression: str,
        timezone: str = "UTC",
        enabled: bool = True,
        param_overrides: Optional[dict] = None,
    ) -> "Schedule":
        """Create a new Schedule with generated ID."""
        return cls(
            schedule_id=generate_uuid(),
            template_id=template_id,
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            enabled=enabled,
            param_overrides=param_overrides,
        )


@dataclass
class Job:
    """
    Single unit of work queued for execution.

    From DOMAIN_MODEL.md Section 3.
    Ephemeral entity from request to completion.

    Mutability rules (from PERSISTENCE_SCHEMA.md Section 2.1):
    - job_id, template_id, schedule_id, group_id, job_type, retry_of, created_at, queued_at: Immutable
    - params: Immutable after RUNNING (INV-001)
    - status, priority, position: Mutable while QUEUED
    - started_at, finished_at: Write-once
    """

    job_id: str
    job_type: str
    params: dict
    status: JobStatus
    priority: int = 0
    position: int = 0
    template_id: Optional[str] = None
    schedule_id: Optional[str] = None
    group_id: Optional[str] = None
    retry_of: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    queued_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @classmethod
    def create(
        cls,
        job_type: str,
        params: dict,
        priority: int = 0,
        position: int = 0,
        template_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        group_id: Optional[str] = None,
        retry_of: Optional[str] = None,
    ) -> "Job":
        """Create a new Job with generated ID and QUEUED status."""
        now = now_iso()
        return cls(
            job_id=generate_uuid(),
            job_type=job_type,
            params=params,
            status=JobStatus.QUEUED,
            priority=priority,
            position=position,
            template_id=template_id,
            schedule_id=schedule_id,
            group_id=group_id,
            retry_of=retry_of,
            created_at=now,
            queued_at=now,
        )

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        # CANCELLED is terminal; QUEUED and RUNNING are not
        # Note: Job completion is indicated by finished_at being set,
        # with actual outcome in JobRun
        return self.status == JobStatus.CANCELLED or self.finished_at is not None


@dataclass
class JobRun:
    """
    Historical record of a single execution attempt.

    From DOMAIN_MODEL.md Section 4.
    Immutable audit trail of what happened.

    Mutability rules (from PERSISTENCE_SCHEMA.md Section 2.2, INV-002):
    - run_id, job_id, template_id, params_snapshot, started_at: Immutable
    - status, finished_at, exit_code, error, artifacts, log_path: Write-once after creation
    """

    run_id: str
    job_id: str
    params_snapshot: dict
    started_at: str
    template_id: Optional[str] = None
    status: Optional[JobRunStatus] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    artifacts: list = field(default_factory=list)
    log_path: Optional[str] = None

    @classmethod
    def create(
        cls,
        job_id: str,
        params_snapshot: dict,
        template_id: Optional[str] = None,
        log_path: Optional[str] = None,
    ) -> "JobRun":
        """Create a new JobRun with generated ID."""
        return cls(
            run_id=generate_uuid(),
            job_id=job_id,
            params_snapshot=params_snapshot,
            started_at=now_iso(),
            template_id=template_id,
            log_path=log_path,
        )

    def is_terminal(self) -> bool:
        """Check if run has a terminal status."""
        return self.status in (
            JobRunStatus.COMPLETED,
            JobRunStatus.FAILED,
            JobRunStatus.SKIPPED,
        )


@dataclass
class DirectReservation:
    """
    Next-slot reservation for Direct API execution (DEC-004).

    From PERSISTENCE_SCHEMA.md Section 2.5.
    Persisted to survive crashes during Direct API handling.

    Single Reservation Rule: At most ONE reservation may be ACTIVE at any time.
    """

    reservation_id: str
    reserved_by: str
    reserved_at: str
    expires_at: str
    status: ReservationStatus

    @classmethod
    def create(
        cls,
        reserved_by: str,
        expires_at: str,
    ) -> "DirectReservation":
        """Create a new ACTIVE reservation."""
        return cls(
            reservation_id=generate_uuid(),
            reserved_by=reserved_by,
            reserved_at=now_iso(),
            expires_at=expires_at,
            status=ReservationStatus.ACTIVE,
        )
