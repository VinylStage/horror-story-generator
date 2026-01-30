"""
Scheduler state management for API integration.

Provides singleton access to SchedulerService instance.
Initialized during FastAPI lifespan, NOT auto-started.

Usage:
    from ._scheduler_state import get_scheduler_service, init_scheduler_service

    # In lifespan:
    init_scheduler_service(db_path, project_root, logs_dir)

    # In routers:
    service = get_scheduler_service()
"""

from pathlib import Path
from typing import Optional

from src.scheduler.service import SchedulerService


# Global scheduler service instance
_scheduler_service: Optional[SchedulerService] = None


def init_scheduler_service(
    db_path: str | Path,
    project_root: Path,
    logs_dir: Path,
    poll_interval: float = 1.0,
) -> SchedulerService:
    """
    Initialize the scheduler service singleton.

    Called during FastAPI lifespan startup.
    Does NOT start the scheduler; explicit /scheduler/start required.

    Args:
        db_path: Path to SQLite database
        project_root: Project root for subprocess execution
        logs_dir: Directory for execution logs
        poll_interval: Dispatcher poll interval in seconds

    Returns:
        Initialized SchedulerService
    """
    global _scheduler_service

    if _scheduler_service is not None:
        return _scheduler_service

    _scheduler_service = SchedulerService.create(
        db_path=db_path,
        project_root=project_root,
        logs_dir=logs_dir,
        poll_interval=poll_interval,
    )

    return _scheduler_service


def get_scheduler_service() -> SchedulerService:
    """
    Get the scheduler service singleton.

    Raises:
        RuntimeError: If scheduler service not initialized
    """
    if _scheduler_service is None:
        raise RuntimeError(
            "Scheduler service not initialized. "
            "Ensure init_scheduler_service() is called during startup."
        )

    return _scheduler_service


def shutdown_scheduler_service() -> None:
    """
    Shutdown the scheduler service.

    Called during FastAPI lifespan shutdown.
    Gracefully stops the scheduler if running.
    """
    global _scheduler_service

    if _scheduler_service is not None:
        if _scheduler_service.is_running:
            _scheduler_service.stop()

        _scheduler_service = None
