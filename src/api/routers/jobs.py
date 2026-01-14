"""
Jobs router for trigger-based API.

Phase B+: Non-blocking job execution via CLI subprocess.
v1.3.0: Webhook notifications on job completion.
v1.4.0: Batch job support.

Endpoints:
- POST /jobs/story/trigger - Trigger story generation
- POST /jobs/research/trigger - Trigger research generation
- POST /jobs/batch/trigger - Trigger multiple jobs as a batch
- GET /jobs/batch/{batch_id} - Get batch status
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
    # Batch schemas (v1.4.0)
    BatchTriggerRequest,
    BatchTriggerResponse,
    BatchStatusResponse,
    BatchJobStatus,
)

# Import job manager from src.infra
from src.infra.job_manager import (
    create_job,
    load_job,
    update_job_status,
    list_jobs as list_jobs_func,
    # Batch functions (v1.4.0)
    create_batch,
    get_batch_status,
)
from src.infra.job_monitor import (
    monitor_job,
    monitor_all_running_jobs,
    cancel_job as cancel_job_func,
)

router = APIRouter()

# Project root for subprocess execution
# File is at src/api/routers/jobs.py, so project root is 4 levels up
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
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

    if params.get("model"):
        cmd.extend(["--model", params["model"]])

    return cmd


def build_research_command(params: dict) -> list[str]:
    """Build CLI command for research generation."""
    cmd = [sys.executable, "-m", "src.research.executor", "run"]

    # Topic is positional argument
    cmd.append(params["topic"])

    # Tags use --tags with multiple values
    tags = params.get("tags", [])
    if tags:
        cmd.append("--tags")
        cmd.extend(tags)

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

    v1.3.0: Supports webhook_url and webhook_events for completion notifications.
    """
    ensure_logs_dir()

    # Create job
    params = request.model_dump()
    job = create_job(job_type="story_generation", params=params)

    log_path = LOGS_DIR / f"story_{job.job_id}.log"
    update_job_status(job.job_id, "queued")

    # v1.3.0: Set webhook configuration
    job_data = load_job(job.job_id)
    if job_data:
        if request.webhook_url:
            job_data.webhook_url = request.webhook_url
            job_data.webhook_events = request.webhook_events
        from src.infra.job_manager import save_job
        save_job(job_data)

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
            from src.infra.job_manager import save_job
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

    Launches `python -m src.research.executor` as background subprocess.
    Returns immediately with job_id for status tracking.

    v1.3.0: Supports webhook_url and webhook_events for completion notifications.
    """
    ensure_logs_dir()

    # Create job
    params = request.model_dump()
    job = create_job(job_type="research", params=params)

    log_path = LOGS_DIR / f"research_{job.job_id}.log"
    update_job_status(job.job_id, "queued")

    # v1.3.0: Set webhook configuration
    job_data = load_job(job.job_id)
    if job_data:
        if request.webhook_url:
            job_data.webhook_url = request.webhook_url
            job_data.webhook_events = request.webhook_events
        from src.infra.job_manager import save_job
        save_job(job_data)

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
            from src.infra.job_manager import save_job
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


# =============================================================================
# Batch Job Endpoints (v1.4.0)
# =============================================================================


@router.post("/batch/trigger", response_model=BatchTriggerResponse, status_code=202)
async def trigger_batch_jobs(request: BatchTriggerRequest):
    """
    Trigger multiple jobs as a batch.

    v1.4.0: Batch job support for triggering multiple jobs at once.

    Accepts an array of job specifications and returns a batch_id
    for tracking the aggregate status of all jobs.
    """
    ensure_logs_dir()

    job_ids = []
    errors = []

    for idx, job_spec in enumerate(request.jobs):
        try:
            if job_spec.type == "research":
                if not job_spec.topic:
                    errors.append(f"Job {idx}: Research job requires 'topic'")
                    continue

                params = {
                    "topic": job_spec.topic,
                    "tags": job_spec.tags,
                    "model": job_spec.model,
                    "timeout": job_spec.timeout,
                }
                job = create_job(job_type="research", params=params)
                log_path = LOGS_DIR / f"research_{job.job_id}.log"
                cmd = build_research_command(params)

            elif job_spec.type == "story":
                params = {
                    "max_stories": job_spec.max_stories,
                    "enable_dedup": job_spec.enable_dedup,
                    "model": job_spec.model,
                }
                job = create_job(job_type="story_generation", params=params)
                log_path = LOGS_DIR / f"story_{job.job_id}.log"
                cmd = build_story_command(params)

            else:
                errors.append(f"Job {idx}: Unknown job type '{job_spec.type}'")
                continue

            # Launch subprocess
            with open(log_path, "w") as log_file:
                process = subprocess.Popen(
                    cmd,
                    cwd=PROJECT_ROOT,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )

            # Update job with pid and log path
            update_job_status(job.job_id, "running", pid=process.pid)
            job_data = load_job(job.job_id)
            if job_data:
                job_data.log_path = str(log_path)
                from src.infra.job_manager import save_job
                save_job(job_data)

            job_ids.append(job.job_id)

        except Exception as e:
            errors.append(f"Job {idx}: {str(e)}")

    if not job_ids:
        raise HTTPException(
            status_code=400,
            detail=f"No jobs were created. Errors: {'; '.join(errors)}"
        )

    # Create batch record
    batch = create_batch(
        job_ids=job_ids,
        webhook_url=request.webhook_url,
        webhook_events=request.webhook_events,
    )

    message = f"Batch triggered with {len(job_ids)} jobs"
    if errors:
        message += f" ({len(errors)} failed: {'; '.join(errors)})"

    return BatchTriggerResponse(
        batch_id=batch.batch_id,
        job_ids=job_ids,
        job_count=len(job_ids),
        status="running",
        message=message,
    )


@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_job_status(batch_id: str):
    """
    Get batch status by ID.

    v1.4.0: Returns aggregate status and individual job statuses.
    """
    status = get_batch_status(batch_id)

    if status is None:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    return BatchStatusResponse(
        batch_id=status["batch_id"],
        status=status["status"],
        total_jobs=status["total_jobs"],
        completed_jobs=status["completed_jobs"],
        succeeded_jobs=status["succeeded_jobs"],
        failed_jobs=status["failed_jobs"],
        running_jobs=status["running_jobs"],
        queued_jobs=status["queued_jobs"],
        jobs=[
            BatchJobStatus(
                job_id=j["job_id"],
                type=j["type"],
                status=j["status"],
                error=j.get("error"),
            )
            for j in status["jobs"]
        ],
        created_at=status["created_at"],
        finished_at=status.get("finished_at"),
        webhook_url=status.get("webhook_url"),
        webhook_sent=status.get("webhook_sent", False),
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get job status by ID.

    Returns full job details including pid, artifacts, error info, and webhook status.
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
        # v1.3.0: Webhook fields
        webhook_url=job.webhook_url,
        webhook_events=job.webhook_events,
        webhook_sent=job.webhook_sent,
        webhook_error=job.webhook_error,
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
            # v1.3.0: Webhook fields
            webhook_url=j.webhook_url,
            webhook_events=j.webhook_events,
            webhook_sent=j.webhook_sent,
            webhook_error=j.webhook_error,
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
    and updates job status to succeeded/failed/skipped as appropriate.
    v1.3.0: Includes webhook processing for completed jobs.
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
            # v1.3.0: New fields
            reason=r.get("reason"),
            webhook_processed=r.get("webhook_processed", False),
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
    v1.3.0: Includes webhook processing status and skip reason.
    """
    result = monitor_job(job_id)

    return JobMonitorResult(
        job_id=result.get("job_id", job_id),
        status=result.get("status"),
        pid=result.get("pid"),
        artifacts=result.get("artifacts", []),
        error=result.get("error"),
        message=result.get("message"),
        # v1.3.0: New fields
        reason=result.get("reason"),
        webhook_processed=result.get("webhook_processed", False),
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
