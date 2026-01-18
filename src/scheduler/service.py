"""
Scheduler Service - Main entry point for the Job Scheduler.

This service orchestrates all scheduler components:
- PersistenceAdapter (storage)
- QueueManager (queue operations)
- Dispatcher (job dispatch loop)
- Executor (job execution)
- RetryController (retry management)
- RecoveryManager (crash recovery)

Usage:
    service = SchedulerService.create(db_path, project_root, logs_dir)
    service.start()
    # ... service runs dispatch loop in background ...
    service.stop()
"""

import logging
from pathlib import Path
from typing import Optional, Callable

from .entities import (
    Job,
    JobRun,
    JobRunStatus,
    JobTemplate,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager
from .dispatcher import Dispatcher
from .executor import Executor, SubprocessJobHandler
from .retry_controller import RetryController
from .recovery import RecoveryManager


logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Main service that coordinates all scheduler components.

    Provides:
    - Component initialization and wiring
    - Startup with recovery
    - Graceful shutdown
    - API-friendly methods for job operations
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        executor: Executor,
        retry_controller: RetryController,
        recovery_manager: RecoveryManager,
    ):
        """
        Initialize SchedulerService with all components.

        Use SchedulerService.create() for convenient construction.
        """
        self.persistence = persistence
        self.queue_manager = queue_manager
        self.dispatcher = dispatcher
        self.executor = executor
        self.retry_controller = retry_controller
        self.recovery_manager = recovery_manager

        self._started = False

    @classmethod
    def create(
        cls,
        db_path: str | Path,
        project_root: Path,
        logs_dir: Path,
        poll_interval: float = 1.0,
    ) -> "SchedulerService":
        """
        Create a SchedulerService with all components wired together.

        Args:
            db_path: Path to SQLite database
            project_root: Project root for subprocess execution
            logs_dir: Directory for execution logs
            poll_interval: Dispatcher poll interval in seconds

        Returns:
            Configured SchedulerService
        """
        # Create persistence
        persistence = PersistenceAdapter(db_path)

        # Create queue manager
        queue_manager = QueueManager(persistence)

        # Create dispatcher
        dispatcher = Dispatcher(
            persistence=persistence,
            queue_manager=queue_manager,
            poll_interval=poll_interval,
        )

        # Create executor with subprocess handler
        handler = SubprocessJobHandler(
            project_root=project_root,
            logs_dir=logs_dir,
        )
        executor = Executor(persistence=persistence, handler=handler)

        # Create retry controller
        retry_controller = RetryController(
            persistence=persistence,
            queue_manager=queue_manager,
        )

        # Create recovery manager
        recovery_manager = RecoveryManager(
            persistence=persistence,
            queue_manager=queue_manager,
            retry_controller=retry_controller,
        )

        # Wire components
        dispatcher.set_executor(executor)

        # Set up completion callback for retry handling
        def on_job_completed(job: Job, job_run: JobRun):
            if job_run.status == JobRunStatus.FAILED:
                retry_controller.on_job_failed(job, job_run)

        dispatcher.set_on_job_completed(on_job_completed)

        return cls(
            persistence=persistence,
            queue_manager=queue_manager,
            dispatcher=dispatcher,
            executor=executor,
            retry_controller=retry_controller,
            recovery_manager=recovery_manager,
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self, run_recovery: bool = True, blocking: bool = False) -> dict:
        """
        Start the scheduler service.

        Args:
            run_recovery: Whether to run crash recovery first
            blocking: Whether to block on dispatch loop

        Returns:
            Recovery statistics if recovery was run
        """
        if self._started:
            raise RuntimeError("Scheduler already started")

        logger.info("Starting scheduler service...")

        # Run crash recovery
        recovery_stats = {}
        if run_recovery:
            recovery_stats = self.recovery_manager.recover_on_startup()

        # Start dispatch loop
        self.dispatcher.start(blocking=blocking)
        self._started = True

        logger.info("Scheduler service started")
        return recovery_stats

    def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the scheduler service gracefully.

        Waits for current job to complete (no preemption).

        Args:
            timeout: Maximum wait time for current job
        """
        if not self._started:
            return

        logger.info("Stopping scheduler service...")
        self.dispatcher.stop(timeout=timeout)
        self._started = False
        logger.info("Scheduler service stopped")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._started and self.dispatcher.is_running()

    # =========================================================================
    # Template Operations
    # =========================================================================

    def create_template(
        self,
        name: str,
        job_type: str,
        default_params: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> JobTemplate:
        """Create a new job template."""
        template = JobTemplate.create(
            name=name,
            job_type=job_type,
            default_params=default_params,
            retry_policy=retry_policy,
            description=description,
        )
        return self.persistence.create_template(template)

    def get_template(self, template_id: str) -> Optional[JobTemplate]:
        """Get a job template by ID."""
        return self.persistence.get_template(template_id)

    def list_templates(self) -> list[JobTemplate]:
        """List all job templates."""
        return self.persistence.list_templates()

    # =========================================================================
    # Job Operations (API-friendly)
    # =========================================================================

    def enqueue_job(
        self,
        job_type: str,
        params: dict,
        priority: int = 0,
        template_id: Optional[str] = None,
    ) -> Job:
        """
        Enqueue a new job for execution.

        Args:
            job_type: Type of work ("story" or "research")
            params: Execution parameters
            priority: Dispatch priority (higher = sooner)
            template_id: Optional source template

        Returns:
            The created Job
        """
        return self.queue_manager.enqueue(
            job_type=job_type,
            params=params,
            priority=priority,
            template_id=template_id,
        )

    def enqueue_from_template(
        self,
        template_id: str,
        priority: int = 0,
        param_overrides: Optional[dict] = None,
    ) -> Job:
        """
        Create and enqueue a job from a template.

        Args:
            template_id: Source template ID
            priority: Dispatch priority
            param_overrides: Override template default params

        Returns:
            The created Job
        """
        return self.queue_manager.enqueue_from_template(
            template_id=template_id,
            priority=priority,
            param_overrides=param_overrides,
        )

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.persistence.get_job(job_id)

    def get_job_run(self, run_id: str) -> Optional[JobRun]:
        """Get a job run by ID."""
        return self.persistence.get_job_run(run_id)

    def get_job_run_for_job(self, job_id: str) -> Optional[JobRun]:
        """Get the job run for a job."""
        return self.persistence.get_job_run_for_job(job_id)

    def list_queued_jobs(self, limit: int = 100) -> list[Job]:
        """List all queued jobs in dispatch order."""
        return self.queue_manager.list_queued(limit=limit)

    def list_running_jobs(self, limit: int = 100) -> list[Job]:
        """List all running jobs."""
        return self.queue_manager.list_running(limit=limit)

    def list_job_runs(self, limit: int = 100) -> list[JobRun]:
        """List recent job runs."""
        return self.persistence.list_job_runs(limit=limit)

    def cancel_job(self, job_id: str) -> Job:
        """
        Cancel a queued job.

        Only QUEUED jobs can be cancelled from queue.
        RUNNING jobs must wait for completion.

        Args:
            job_id: Job to cancel

        Returns:
            The cancelled Job
        """
        return self.queue_manager.cancel(job_id)

    def retry_job_run(
        self,
        run_id: str,
        priority: Optional[int] = None,
    ) -> Job:
        """
        Manually retry a failed job run.

        Args:
            run_id: JobRun ID to retry
            priority: Optional priority for retry job

        Returns:
            The new retry Job
        """
        return self.retry_controller.manual_retry(run_id, priority=priority)

    # =========================================================================
    # Queue Status
    # =========================================================================

    def get_queue_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dict with queued_count, running_count, has_reservation
        """
        return {
            "queued_count": self.queue_manager.count_queued(),
            "running_count": self.queue_manager.count_running(),
            "has_active_reservation": self.queue_manager.has_active_reservation(),
            "is_running": self.is_running,
        }

    # =========================================================================
    # Direct API Support
    # =========================================================================

    def execute_direct(
        self,
        job_type: str,
        params: dict,
        reserved_by: str,
        timeout: Optional[float] = None,
    ) -> JobRun:
        """
        Execute a direct API request with next-slot reservation.

        From DEC-004:
        1. Reserve next slot
        2. Wait for current job to complete
        3. Execute direct request
        4. Release reservation

        Args:
            job_type: Type of work
            params: Execution parameters
            reserved_by: Identifier for reservation
            timeout: Maximum wait for current job

        Returns:
            The completed JobRun
        """
        return self.dispatcher.execute_direct(
            job_type=job_type,
            params=params,
            reserved_by=reserved_by,
            timeout=timeout,
        )
