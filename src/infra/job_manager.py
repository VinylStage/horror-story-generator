"""
Job management module for trigger-based API layer.

Phase B+: File-based job storage in ./jobs/ directory.
v1.3.1: Centralized path management via data_paths module.
CLI remains source of truth - API triggers subprocess execution.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

from src.infra.data_paths import get_jobs_dir


# Job status types
# Note: "skipped" is for expected behaviors like duplicate detection (NOT a failure)
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "skipped"]
JobType = Literal["story_generation", "research"]

# Webhook event types
WebhookEvent = Literal["succeeded", "failed", "skipped"]
DEFAULT_WEBHOOK_EVENTS = ["succeeded", "failed", "skipped"]

# Jobs directory - v1.3.1: Use centralized path from data_paths
# Can be overridden via JOB_DIR environment variable
JOBS_DIR = get_jobs_dir()


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


# =============================================================================
# Job Pruning (v1.3.1)
# =============================================================================

def prune_old_jobs(
    days: Optional[int] = None,
    max_count: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    Prune old job files based on age and count.

    v1.3.1: Optional job history cleanup.

    This function is disabled by default. Enable via:
    - JOB_PRUNE_ENABLED=true environment variable
    - Or call directly with explicit parameters

    Args:
        days: Delete jobs older than this many days (default: from env or 30)
        max_count: Keep at most this many jobs (default: from env or 1000)
        dry_run: If True, only report what would be deleted

    Returns:
        dict with pruning results:
        - deleted_count: Number of jobs deleted
        - deleted_by_age: Jobs deleted due to age
        - deleted_by_count: Jobs deleted due to count limit
        - errors: List of error messages
        - dry_run: Whether this was a dry run
    """
    from src.infra.data_paths import get_job_prune_config

    config = get_job_prune_config()

    # Use provided values or fall back to config
    prune_days = days if days is not None else config["days"]
    prune_max_count = max_count if max_count is not None else config["max_count"]

    result = {
        "deleted_count": 0,
        "deleted_by_age": 0,
        "deleted_by_count": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    ensure_jobs_dir()

    try:
        # Get all job files sorted by modification time (oldest first)
        job_files = sorted(
            JOBS_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime
        )

        cutoff_time = datetime.now().timestamp() - (prune_days * 24 * 60 * 60)
        to_delete = []

        # Mark old jobs for deletion
        for job_file in job_files:
            try:
                mtime = job_file.stat().st_mtime
                if mtime < cutoff_time:
                    # Check if job is in terminal state
                    job = load_job(job_file.stem)
                    if job and job.status in ("succeeded", "failed", "cancelled", "skipped"):
                        to_delete.append(("age", job_file))
            except Exception as e:
                result["errors"].append(f"Error checking {job_file.name}: {e}")

        # If still over max_count, mark more for deletion
        remaining_count = len(job_files) - len(to_delete)
        if remaining_count > prune_max_count:
            # Get remaining files (those not already marked for deletion)
            marked_paths = {f[1] for f in to_delete}
            remaining_files = [f for f in job_files if f not in marked_paths]

            # Mark oldest ones until we're under max_count
            excess = remaining_count - prune_max_count
            for job_file in remaining_files[:excess]:
                try:
                    job = load_job(job_file.stem)
                    if job and job.status in ("succeeded", "failed", "cancelled", "skipped"):
                        to_delete.append(("count", job_file))
                except Exception as e:
                    result["errors"].append(f"Error checking {job_file.name}: {e}")

        # Delete marked jobs
        for reason, job_file in to_delete:
            if dry_run:
                result["deleted_count"] += 1
                if reason == "age":
                    result["deleted_by_age"] += 1
                else:
                    result["deleted_by_count"] += 1
            else:
                try:
                    job_file.unlink()
                    result["deleted_count"] += 1
                    if reason == "age":
                        result["deleted_by_age"] += 1
                    else:
                        result["deleted_by_count"] += 1
                except Exception as e:
                    result["errors"].append(f"Error deleting {job_file.name}: {e}")

    except Exception as e:
        result["errors"].append(f"Pruning error: {e}")

    return result


def auto_prune_if_enabled() -> Optional[dict]:
    """
    Automatically prune jobs if enabled via environment variable.

    v1.3.1: Called on job creation to keep history manageable.

    Returns:
        Pruning result dict if pruning was performed, None otherwise
    """
    from src.infra.data_paths import get_job_prune_config

    config = get_job_prune_config()
    if not config["enabled"]:
        return None

    return prune_old_jobs(
        days=config["days"],
        max_count=config["max_count"],
        dry_run=False
    )
