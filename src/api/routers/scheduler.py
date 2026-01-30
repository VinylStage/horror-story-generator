"""
Scheduler router for scheduler control APIs.

Phase 3: Independent scheduler control plane.
Endpoints under /scheduler/* for start, stop, and status operations.

Design rationale (from Phase 3 design):
- Scheduler is a system-level control plane, NOT a sub-resource of Job
- Separate namespace avoids route conflicts with /jobs/{job_id}
- Enables future extensibility (/scheduler/config, /scheduler/metrics)
"""

from fastapi import APIRouter, HTTPException

from ..schemas.scheduler import (
    SchedulerStartRequest,
    SchedulerStartResponse,
    SchedulerStopRequest,
    SchedulerStopResponse,
    SchedulerStatusResponse,
    CumulativeStats,
)
from .._scheduler_state import get_scheduler_service


router = APIRouter()


@router.post("/start", response_model=SchedulerStartResponse)
async def start_scheduler(request: SchedulerStartRequest = SchedulerStartRequest()):
    """
    Start the scheduler dispatch loop.

    Idempotent: If scheduler is already running, returns success with message.
    Does NOT auto-start on server boot; explicit call required.
    """
    service = get_scheduler_service()

    if service.is_running:
        return SchedulerStartResponse(
            success=True,
            message="Scheduler is already running",
            recovery_stats=None,
        )

    try:
        recovery_stats = service.start(
            run_recovery=request.run_recovery,
            blocking=False,
        )

        return SchedulerStartResponse(
            success=True,
            message="Scheduler started successfully",
            recovery_stats=recovery_stats if recovery_stats else None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start scheduler: {str(e)}"
        )


@router.post("/stop", response_model=SchedulerStopResponse)
async def stop_scheduler(request: SchedulerStopRequest = SchedulerStopRequest()):
    """
    Stop the scheduler dispatch loop gracefully.

    Waits for currently running job to complete (no preemption).
    Idempotent: If scheduler is already stopped, returns success.
    """
    service = get_scheduler_service()

    if not service.is_running:
        return SchedulerStopResponse(
            success=True,
            message="Scheduler is already stopped",
        )

    try:
        service.stop(timeout=request.timeout)

        return SchedulerStopResponse(
            success=True,
            message="Scheduler stopped successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop scheduler: {str(e)}"
        )


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    Get comprehensive scheduler status.

    Returns:
    - scheduler_running: Whether dispatch loop is active
    - current_job_id: ID of currently executing job (null if none)
    - queue_length: Number of QUEUED jobs waiting
    - cumulative_stats: Execution statistics (total, succeeded, failed, etc.)
    - has_active_reservation: Whether Direct API reservation is active
    """
    service = get_scheduler_service()

    try:
        status = service.get_scheduler_status()

        return SchedulerStatusResponse(
            scheduler_running=status["scheduler_running"],
            current_job_id=status["current_job_id"],
            queue_length=status["queue_length"],
            cumulative_stats=CumulativeStats(
                total_executed=status["cumulative_stats"]["total_executed"],
                succeeded=status["cumulative_stats"]["succeeded"],
                failed=status["cumulative_stats"]["failed"],
                cancelled=status["cumulative_stats"]["cancelled"],
                skipped=status["cumulative_stats"]["skipped"],
            ),
            has_active_reservation=status["has_active_reservation"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduler status: {str(e)}"
        )
