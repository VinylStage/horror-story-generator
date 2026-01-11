"""
Background job monitoring module.

Phase B+: Poll running jobs by PID, update status on completion.
"""

import os
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.infra.job_manager import (
    load_job,
    update_job_status,
    get_running_jobs,
    Job,
)


# Artifact directories to scan for story/research outputs
PROJECT_ROOT = Path(__file__).parent.parent.parent
STORY_OUTPUT_DIR = PROJECT_ROOT / "data" / "stories"
RESEARCH_OUTPUT_DIR = PROJECT_ROOT / "data" / "research"


def is_process_running(pid: int) -> bool:
    """
    Check if a process is running by PID.

    Uses os.kill with signal 0, but also checks for zombie processes.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running (not zombie), False otherwise
    """
    if pid is None or pid <= 0:
        return False

    try:
        os.kill(pid, 0)
        # Process exists, but might be zombie - check state
        try:
            import subprocess
            result = subprocess.run(
                ["ps", "-o", "state=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=5
            )
            state = result.stdout.strip()
            # Z = zombie, check first character
            if state and state[0] == 'Z':
                return False
        except Exception:
            pass  # If we can't check state, assume running
        return True
    except OSError:
        return False


def get_process_exit_code(pid: int) -> Optional[int]:
    """
    Try to get exit code for a finished process.

    Note: This is limited - we can't reliably get exit codes
    for detached processes. We use 0 for success (not running)
    and assume failure otherwise based on error detection.

    Args:
        pid: Process ID

    Returns:
        Exit code if determinable, None otherwise
    """
    # For detached subprocesses, we can't reliably get exit codes
    # We'll infer from artifacts and log analysis
    return None


def collect_story_artifacts(job: Job) -> list[str]:
    """
    Collect story artifacts created after job started.

    Args:
        job: Job instance

    Returns:
        List of artifact file paths
    """
    artifacts = []

    if not job.started_at:
        return artifacts

    try:
        job_start = datetime.fromisoformat(job.started_at)

        if STORY_OUTPUT_DIR.exists():
            for story_file in STORY_OUTPUT_DIR.glob("**/*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(story_file.stat().st_mtime)
                    if file_mtime >= job_start:
                        artifacts.append(str(story_file))
                except Exception:
                    continue

    except Exception:
        pass

    return artifacts


def collect_research_artifacts(job: Job) -> list[str]:
    """
    Collect research artifacts created after job started.

    Args:
        job: Job instance

    Returns:
        List of artifact file paths
    """
    artifacts = []

    if not job.started_at:
        return artifacts

    try:
        job_start = datetime.fromisoformat(job.started_at)

        if RESEARCH_OUTPUT_DIR.exists():
            for research_file in RESEARCH_OUTPUT_DIR.glob("**/*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(research_file.stat().st_mtime)
                    if file_mtime >= job_start:
                        artifacts.append(str(research_file))
                except Exception:
                    continue

    except Exception:
        pass

    return artifacts


def collect_artifacts(job: Job) -> list[str]:
    """
    Collect artifacts for a job based on its type.

    Args:
        job: Job instance

    Returns:
        List of artifact file paths
    """
    if job.type == "story_generation":
        return collect_story_artifacts(job)
    elif job.type == "research":
        return collect_research_artifacts(job)
    return []


def check_job_log_for_errors(job: Job) -> Optional[str]:
    """
    Check job log file for error indicators.

    Args:
        job: Job instance

    Returns:
        Error message if found, None otherwise
    """
    if not job.log_path:
        return None

    log_path = Path(job.log_path)
    if not log_path.exists():
        return None

    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")

        # Check for common error indicators
        error_indicators = [
            "Traceback (most recent call last):",
            "Error:",
            "Exception:",
            "FAILED",
            "fatal:",
        ]

        for indicator in error_indicators:
            if indicator in content:
                # Extract last 500 chars around error
                idx = content.rfind(indicator)
                error_context = content[max(0, idx - 100):idx + 400]
                return error_context.strip()

    except Exception:
        pass

    return None


def monitor_job(job_id: str) -> dict:
    """
    Monitor a single job and update its status if completed.

    Args:
        job_id: Job ID to monitor

    Returns:
        Dict with monitoring result
    """
    job = load_job(job_id)

    if job is None:
        return {"job_id": job_id, "error": "Job not found"}

    if job.status != "running":
        return {"job_id": job_id, "status": job.status, "message": "Job not running"}

    if job.pid is None:
        return {"job_id": job_id, "error": "No PID recorded"}

    # Check if process is still running
    if is_process_running(job.pid):
        return {
            "job_id": job_id,
            "status": "running",
            "pid": job.pid,
            "message": "Process still running"
        }

    # Process has exited - determine success/failure
    artifacts = collect_artifacts(job)
    error = check_job_log_for_errors(job)

    if error:
        update_job_status(
            job_id,
            "failed",
            exit_code=1,
            error=error,
            artifacts=artifacts
        )
        return {
            "job_id": job_id,
            "status": "failed",
            "artifacts": artifacts,
            "error": error
        }
    else:
        # No errors found, assume success
        update_job_status(
            job_id,
            "succeeded",
            exit_code=0,
            artifacts=artifacts
        )
        return {
            "job_id": job_id,
            "status": "succeeded",
            "artifacts": artifacts
        }


def monitor_all_running_jobs() -> list[dict]:
    """
    Monitor all running jobs and update their status.

    Returns:
        List of monitoring results for each job
    """
    results = []

    for job in get_running_jobs():
        result = monitor_job(job.job_id)
        results.append(result)

    return results


def cancel_job(job_id: str) -> dict:
    """
    Cancel a running job by sending SIGTERM to its process.

    Args:
        job_id: Job ID to cancel

    Returns:
        Dict with cancellation result
    """
    job = load_job(job_id)

    if job is None:
        return {"job_id": job_id, "success": False, "error": "Job not found"}

    if job.status != "running":
        return {"job_id": job_id, "success": False, "error": f"Job not running (status: {job.status})"}

    if job.pid is None:
        return {"job_id": job_id, "success": False, "error": "No PID recorded"}

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(job.pid, signal.SIGTERM)

        # Update job status
        update_job_status(
            job_id,
            "cancelled",
            error="Cancelled by user"
        )

        return {
            "job_id": job_id,
            "success": True,
            "message": f"Sent SIGTERM to PID {job.pid}"
        }

    except ProcessLookupError:
        # Process already exited
        update_job_status(job_id, "cancelled", error="Process already exited")
        return {
            "job_id": job_id,
            "success": True,
            "message": "Process already exited"
        }

    except PermissionError:
        return {
            "job_id": job_id,
            "success": False,
            "error": f"Permission denied to kill PID {job.pid}"
        }

    except Exception as e:
        return {
            "job_id": job_id,
            "success": False,
            "error": str(e)
        }
