"""
Jobs router for trigger-based API.

Phase B+: Non-blocking job execution via CLI subprocess.

Endpoints:
- POST /jobs/story/trigger - Trigger story generation
- POST /jobs/research/trigger - Trigger research generation
- GET /jobs/{job_id} - Get job status
- GET /jobs - List all jobs
- POST /jobs/{job_id}/cancel - Cancel a running job
- POST /jobs/monitor - Monitor all running jobs
- POST /jobs/{job_id}/monitor - Monitor single job
- POST /jobs/{job_id}/dedup_check - Check dedup for research job
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..schemas.jobs import (
    StoryTriggerRequest,
    ResearchTriggerRequest,
    JobTriggerResponse,
    JobStatusResponse,
    JobListResponse,
    JobCancelResponse,
    JobMonitorResult,
    JobMonitorResponse,
    JobDedupCheckResponse,
)

# Import job manager from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_manager import (
    create_job,
    load_job,
    update_job_status,
    list_jobs as list_jobs_func,
)
from job_monitor import (
    monitor_job,
    monitor_all_running_jobs,
    cancel_job as cancel_job_func,
)

router = APIRouter()

# Project root for subprocess execution
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


def ensure_logs_dir() -> Path:
    """Ensure logs directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def build_story_command(params: dict) -> list[str]:
    """Build CLI command for story generation."""
    cmd = [sys.executable, str(PROJECT_ROOT / "main.py")]

    if params.get("max_stories"):
        cmd.extend(["--max-stories", str(params["max_stories"])])

    if params.get("duration_seconds"):
        cmd.extend(["--duration-seconds", str(params["duration_seconds"])])

    if params.get("interval_seconds"):
        cmd.extend(["--interval-seconds", str(params["interval_seconds"])])

    if params.get("enable_dedup"):
        cmd.append("--enable-dedup")

    if params.get("db_path"):
        cmd.extend(["--db-path", params["db_path"]])

    if params.get("load_history"):
        cmd.append("--load-history")

    return cmd


def build_research_command(params: dict) -> list[str]:
    """Build CLI command for research generation."""
    cmd = [sys.executable, "-m", "research_executor"]

    cmd.extend(["--topic", params["topic"]])

    for tag in params.get("tags", []):
        cmd.extend(["--tag", tag])

    if params.get("model"):
        cmd.extend(["--model", params["model"]])

    if params.get("timeout"):
        cmd.extend(["--timeout", str(params["timeout"])])

    return cmd


@router.post("/story/trigger", response_model=JobTriggerResponse, status_code=202)
async def trigger_story_generation(request: StoryTriggerRequest):
    """
    Trigger story generation job.

    Launches `python main.py` as background subprocess.
    Returns immediately with job_id for status tracking.
    """
    ensure_logs_dir()

    # Create job
    params = request.model_dump()
    job = create_job(job_type="story_generation", params=params)

    log_path = LOGS_DIR / f"story_{job.job_id}.log"
    update_job_status(job.job_id, "queued")

    # Build command
    cmd = build_story_command(params)

    try:
        # Launch subprocess
        with open(log_path, "w") as log_file:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        # Update job with pid
        update_job_status(
            job.job_id,
            "running",
            pid=process.pid,
        )

        # Update log path
        job_data = load_job(job.job_id)
        if job_data:
            job_data.log_path = str(log_path)
            from job_manager import save_job
            save_job(job_data)

        return JobTriggerResponse(
            job_id=job.job_id,
            type="story_generation",
            status="running",
            message=f"Story generation job started with PID {process.pid}",
        )

    except Exception as e:
        update_job_status(job.job_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start job: {e}")


@router.post("/research/trigger", response_model=JobTriggerResponse, status_code=202)
async def trigger_research_generation(request: ResearchTriggerRequest):
    """
    Trigger research generation job.

    Launches `python -m research_executor` as background subprocess.
    Returns immediately with job_id for status tracking.
    """
    ensure_logs_dir()

    # Create job
    params = request.model_dump()
    job = create_job(job_type="research", params=params)

    log_path = LOGS_DIR / f"research_{job.job_id}.log"
    update_job_status(job.job_id, "queued")

    # Build command
    cmd = build_research_command(params)

    try:
        # Launch subprocess
        with open(log_path, "w") as log_file:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        # Update job with pid
        update_job_status(
            job.job_id,
            "running",
            pid=process.pid,
        )

        # Update log path
        job_data = load_job(job.job_id)
        if job_data:
            job_data.log_path = str(log_path)
            from job_manager import save_job
            save_job(job_data)

        return JobTriggerResponse(
            job_id=job.job_id,
            type="research",
            status="running",
            message=f"Research job started with PID {process.pid}",
        )

    except Exception as e:
        update_job_status(job.job_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start job: {e}")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get job status by ID.

    Returns full job details including pid, artifacts, and error info.
    """
    job = load_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatusResponse(
        job_id=job.job_id,
        type=job.type,
        status=job.status,
        params=job.params,
        pid=job.pid,
        log_path=job.log_path,
        artifacts=job.artifacts,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        exit_code=job.exit_code,
        error=job.error,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    type: Optional[str] = Query(default=None, description="Filter by job type"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum jobs to return"),
):
    """
    List jobs with optional filtering.

    Supports filtering by status and job type.
    """
    jobs = list_jobs_func(status=status, job_type=type, limit=limit)

    job_responses = [
        JobStatusResponse(
            job_id=j.job_id,
            type=j.type,
            status=j.status,
            params=j.params,
            pid=j.pid,
            log_path=j.log_path,
            artifacts=j.artifacts,
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
            exit_code=j.exit_code,
            error=j.error,
        )
        for j in jobs
    ]

    return JobListResponse(
        jobs=job_responses,
        total=len(job_responses),
        message=f"Found {len(job_responses)} jobs",
    )


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(job_id: str):
    """
    Cancel a running job.

    Sends SIGTERM to the job's process for graceful shutdown.
    """
    result = cancel_job_func(job_id)

    return JobCancelResponse(
        job_id=job_id,
        success=result.get("success", False),
        message=result.get("message"),
        error=result.get("error"),
    )


@router.post("/monitor", response_model=JobMonitorResponse)
async def monitor_jobs():
    """
    Monitor all running jobs and update their status.

    Checks if processes are still running, collects artifacts,
    and updates job status to succeeded/failed as appropriate.
    """
    results = monitor_all_running_jobs()

    monitor_results = [
        JobMonitorResult(
            job_id=r.get("job_id", ""),
            status=r.get("status"),
            pid=r.get("pid"),
            artifacts=r.get("artifacts", []),
            error=r.get("error"),
            message=r.get("message"),
        )
        for r in results
    ]

    return JobMonitorResponse(
        monitored_count=len(monitor_results),
        results=monitor_results,
    )


@router.post("/{job_id}/monitor", response_model=JobMonitorResult)
async def monitor_single_job(job_id: str):
    """
    Monitor a single job and update its status.

    Checks if the job's process is still running and updates status.
    """
    result = monitor_job(job_id)

    return JobMonitorResult(
        job_id=result.get("job_id", job_id),
        status=result.get("status"),
        pid=result.get("pid"),
        artifacts=result.get("artifacts", []),
        error=result.get("error"),
        message=result.get("message"),
    )


@router.post("/{job_id}/dedup_check", response_model=JobDedupCheckResponse)
async def check_job_dedup(job_id: str):
    """
    Check dedup signal for a research job's artifact.

    If the job produced a research card artifact, evaluates its
    similarity against existing content using the dedup service.
    """
    job = load_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Only research jobs can have dedup checks
    if job.type != "research":
        return JobDedupCheckResponse(
            job_id=job_id,
            has_artifact=False,
            message="Dedup check only available for research jobs",
        )

    # Check if job has artifacts
    if not job.artifacts:
        return JobDedupCheckResponse(
            job_id=job_id,
            has_artifact=False,
            message="Job has no artifacts yet (still running or failed)",
        )

    # Get the first research card artifact
    artifact_path = job.artifacts[0]

    try:
        import json
        from pathlib import Path as PathLib

        artifact_file = PathLib(artifact_path)
        if not artifact_file.exists():
            return JobDedupCheckResponse(
                job_id=job_id,
                has_artifact=False,
                message=f"Artifact file not found: {artifact_path}",
            )

        # Load research card
        with open(artifact_file, "r", encoding="utf-8") as f:
            card_data = json.load(f)

        # Extract canonical affinity for dedup evaluation
        output = card_data.get("output", {})
        canonical = output.get("canonical_affinity", {})

        if not canonical:
            return JobDedupCheckResponse(
                job_id=job_id,
                has_artifact=True,
                artifact_path=artifact_path,
                message="Research card has no canonical affinity for dedup evaluation",
            )

        # Build canonical core from affinity
        # Convert lists to first item or comma-separated string
        canonical_core = {}
        for key in ["setting", "primary_fear", "antagonist", "mechanism"]:
            value = canonical.get(key, [])
            if isinstance(value, list) and value:
                canonical_core[key] = value[0] if len(value) == 1 else ", ".join(value)
            elif isinstance(value, str):
                canonical_core[key] = value

        # Use dedup service to evaluate
        from ..services import dedup_service

        result = await dedup_service.evaluate_dedup(
            canonical_core=canonical_core,
            title=output.get("title"),
        )

        return JobDedupCheckResponse(
            job_id=job_id,
            has_artifact=True,
            artifact_path=artifact_path,
            signal=result.get("signal", "LOW"),
            similarity_score=result.get("similarity_score", 0.0),
            message=result.get("message"),
        )

    except Exception as e:
        return JobDedupCheckResponse(
            job_id=job_id,
            has_artifact=True,
            artifact_path=artifact_path,
            message=f"Dedup evaluation error: {str(e)}",
        )
