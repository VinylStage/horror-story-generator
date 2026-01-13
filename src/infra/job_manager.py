"""
Job management module for trigger-based API layer.

Phase B+: File-based job storage in ./jobs/ directory.
CLI remains source of truth - API triggers subprocess execution.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal


# Job status types
# Note: "skipped" is for expected behaviors like duplicate detection (NOT a failure)
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "skipped"]
JobType = Literal["story_generation", "research"]

# Webhook event types
WebhookEvent = Literal["succeeded", "failed", "skipped"]
DEFAULT_WEBHOOK_EVENTS = ["succeeded", "failed", "skipped"]

# Jobs directory (project_root/jobs/)
JOBS_DIR = Path(__file__).parent.parent.parent / "jobs"


@dataclass
class Job:
    """
    Job model for tracking CLI subprocess executions.

    Stored as JSON in ./jobs/{job_id}.json

    Webhook Integration (v1.3.0):
    - webhook_url: If set, sends HTTP POST on job completion
    - webhook_events: Which events trigger webhook (default: all terminal states)
    - webhook_sent: Whether webhook was successfully sent
    - webhook_error: Error message if webhook failed
    """
    job_id: str
    type: JobType
    status: JobStatus
    params: dict = field(default_factory=dict)
    pid: Optional[int] = None
    log_path: Optional[str] = None
    artifacts: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    # Webhook fields (v1.3.0)
    webhook_url: Optional[str] = None
    webhook_events: list = field(default_factory=lambda: DEFAULT_WEBHOOK_EVENTS.copy())
    webhook_sent: bool = False
    webhook_error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert job to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Create job from dictionary."""
        return cls(**data)


def ensure_jobs_dir() -> Path:
    """Ensure jobs directory exists."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return JOBS_DIR


def get_job_path(job_id: str) -> Path:
    """Get path to job JSON file."""
    return JOBS_DIR / f"{job_id}.json"


def create_job(
    job_type: JobType,
    params: dict,
    log_path: Optional[str] = None
) -> Job:
    """
    Create a new job and save to disk.

    Args:
        job_type: Type of job (story_generation or research)
        params: CLI parameters for the job
        log_path: Optional path to log file

    Returns:
        Created Job instance
    """
    ensure_jobs_dir()

    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        type=job_type,
        status="queued",
        params=params,
        log_path=log_path,
    )

    save_job(job)
    return job


def save_job(job: Job) -> bool:
    """
    Save job to disk.

    Args:
        job: Job instance to save

    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_jobs_dir()
        job_path = get_job_path(job.job_id)

        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job.to_dict(), f, indent=2, ensure_ascii=False)

        return True
    except Exception:
        return False


def load_job(job_id: str) -> Optional[Job]:
    """
    Load job from disk.

    Args:
        job_id: Job ID to load

    Returns:
        Job instance if found, None otherwise
    """
    try:
        job_path = get_job_path(job_id)

        if not job_path.exists():
            return None

        with open(job_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Job.from_dict(data)
    except Exception:
        return None


def update_job_status(
    job_id: str,
    status: JobStatus,
    pid: Optional[int] = None,
    exit_code: Optional[int] = None,
    error: Optional[str] = None,
    artifacts: Optional[list] = None
) -> bool:
    """
    Update job status and related fields.

    Args:
        job_id: Job ID to update
        status: New status
        pid: Process ID (set when status becomes 'running')
        exit_code: Exit code (set when job finishes)
        error: Error message (set on failure)
        artifacts: List of artifact paths

    Returns:
        True if successful, False otherwise
    """
    job = load_job(job_id)
    if job is None:
        return False

    job.status = status

    if status == "running" and job.started_at is None:
        job.started_at = datetime.now().isoformat()

    if status in ("succeeded", "failed", "cancelled", "skipped"):
        job.finished_at = datetime.now().isoformat()

    if pid is not None:
        job.pid = pid

    if exit_code is not None:
        job.exit_code = exit_code

    if error is not None:
        job.error = error

    if artifacts is not None:
        job.artifacts = artifacts

    return save_job(job)


def list_jobs(
    status: Optional[JobStatus] = None,
    job_type: Optional[JobType] = None,
    limit: int = 100
) -> list[Job]:
    """
    List jobs with optional filtering.

    Args:
        status: Filter by status
        job_type: Filter by job type
        limit: Maximum number of jobs to return

    Returns:
        List of Job instances
    """
    ensure_jobs_dir()
    jobs = []

    try:
        for job_file in sorted(JOBS_DIR.glob("*.json"), reverse=True):
            if len(jobs) >= limit:
                break

            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                job = Job.from_dict(data)

                # Apply filters
                if status is not None and job.status != status:
                    continue
                if job_type is not None and job.type != job_type:
                    continue

                jobs.append(job)
            except Exception:
                continue
    except Exception:
        pass

    return jobs


def delete_job(job_id: str) -> bool:
    """
    Delete job from disk.

    Args:
        job_id: Job ID to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        job_path = get_job_path(job_id)

        if job_path.exists():
            job_path.unlink()
            return True

        return False
    except Exception:
        return False


def get_running_jobs() -> list[Job]:
    """Get all currently running jobs."""
    return list_jobs(status="running")


def get_queued_jobs() -> list[Job]:
    """Get all queued jobs."""
    return list_jobs(status="queued")
