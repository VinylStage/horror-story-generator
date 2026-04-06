"""
Scheduler Service - Main entry point for the Task Scheduler.

This service orchestrates all scheduler components:
- PersistenceAdapter (storage)
- QueueManager (queue operations)
- Dispatcher (task dispatch loop)
- Executor (task execution)
- RetryController (retry management)
- RecoveryManager (crash recovery)

Usage:
    service = SchedulerService.create(db_path, project_root, logs_dir)
    service.start()
    # ... service runs dispatch loop in background ...
    service.stop()
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from .entities import (
    Task,
    TaskRun,
    TaskRunStatus,
    TaskStatus,
    TaskTemplate,
)
from .persistence import PersistenceAdapter
from src.infra.webhook import (
    resolve_webhook_url,
    is_discord_webhook_url,
    build_task_discord_embed_payload,
    build_sync_webhook_payload,
    _send_webhook_in_thread,
)
from .queue_manager import QueueManager
from .dispatcher import Dispatcher
from .executor import Executor, DirectTaskHandler
from .retry_controller import RetryController
from .recovery import RecoveryManager


logger = logging.getLogger(__name__)


def _extract_rich_webhook_result(
    task_type: str,
    task_run: "TaskRun",
    project_root: Path,
) -> dict:
    """
    Extract rich result data from generated output files for webhook notification.

    Reads the newest output file created during task execution and parses
    metadata to build a webhook payload matching direct API endpoints
    (/story/generate, /research/run).
    """
    try:
        started_ts = datetime.fromisoformat(
            task_run.started_at.replace("Z", "+00:00")
        ).timestamp()

        if task_type == "story":
            return _extract_story_result(started_ts, project_root)
        elif task_type == "research":
            return _extract_research_result(started_ts, project_root)
    except Exception as e:
        logger.warning(f"Failed to extract rich webhook result: {e}")
    return {}


def _extract_story_result(started_ts: float, project_root: Path) -> dict:
    """Extract story metadata from the newest metadata JSON file."""
    novel_dir = project_root / "data" / "novel"
    if not novel_dir.exists():
        return {}

    candidates = [
        f for f in novel_dir.glob("*_metadata.json")
        if f.stat().st_mtime >= started_ts - 1  # 1s tolerance
    ]
    if not candidates:
        return {}

    newest = max(candidates, key=lambda f: f.stat().st_mtime)
    with open(newest) as fh:
        meta = json.load(fh)

    story_file = str(newest).replace("_metadata.json", ".md")

    return {
        "story_id": meta.get("story_id"),
        "title": meta.get("title"),
        "file_path": story_file,
        "word_count": meta.get("word_count"),
        "thumbnail_url": meta.get("thumbnail_url"),
        "thumbnail_provider": meta.get("thumbnail_provider"),
    }


def _extract_research_result(started_ts: float, project_root: Path) -> dict:
    """Extract research card data from the newest research JSON file."""
    research_dir = project_root / "data" / "research"
    if not research_dir.exists():
        return {}

    candidates = [
        f for f in research_dir.rglob("RC-*.json")
        if f.stat().st_mtime >= started_ts - 1
    ]
    if not candidates:
        return {}

    newest = max(candidates, key=lambda f: f.stat().st_mtime)
    with open(newest) as fh:
        card = json.load(fh)

    return {
        "card_id": card.get("card_id", ""),
        "output_path": str(newest),
        "message": f"Research completed: {card.get('output', {}).get('title', '')}",
    }


class SchedulerService:
    """
    Main service that coordinates all scheduler components.

    Provides:
    - Component initialization and wiring
    - Startup with recovery
    - Graceful shutdown
    - API-friendly methods for task operations
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
            project_root: Project root for task execution
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

        # Create executor with direct in-process handler
        handler = DirectTaskHandler(
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

        # Set up completion callback for retry handling and TaskGroup logic
        def on_task_completed(task: Task, task_run: TaskRun):
            # Handle retry logic first
            if task_run.status == TaskRunStatus.FAILED:
                retry_controller.on_task_failed(task, task_run)

            # Handle TaskGroup completion (DEC-012)
            # This checks for stop-on-failure and updates group status
            queue_manager.handle_group_job_completion(task, task_run)

            # Send webhook notification if configured
            webhook_url = resolve_webhook_url()
            if webhook_url and task_run.is_terminal():
                import threading

                status = "success" if task_run.status == TaskRunStatus.COMPLETED else "error"

                # Build result with base fields
                result = {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "run_id": task_run.run_id,
                    "status": task_run.status.value,
                    "exit_code": task_run.exit_code,
                    "error": task_run.error,
                }

                # Enrich with output file metadata for success cases
                if status == "success":
                    rich = _extract_rich_webhook_result(
                        task.task_type, task_run, project_root,
                    )
                    result.update(rich)

                # Build payload: scheduler-specific format for Discord
                if is_discord_webhook_url(webhook_url):
                    payload = build_task_discord_embed_payload(
                        task_id=task.task_id,
                        task_type=task.task_type,
                        status=status,
                        result=result,
                    )
                else:
                    payload = build_sync_webhook_payload(
                        endpoint=f"/tasks/{task.task_id}",
                        status=status,
                        result=result,
                    )

                logger.info(
                    f"Triggering task webhook for {task.task_id} ({task.task_type})"
                )
                thread = threading.Thread(
                    target=_send_webhook_in_thread,
                    args=(webhook_url, payload),
                    daemon=True,
                )
                thread.start()

        dispatcher.set_on_job_completed(on_task_completed)

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

        Waits for current task to complete (no preemption).

        Args:
            timeout: Maximum wait time for current task
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
        task_type: str,
        default_params: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> TaskTemplate:
        """Create a new task template."""
        template = TaskTemplate.create(
            name=name,
            task_type=task_type,
            default_params=default_params,
            retry_policy=retry_policy,
            description=description,
        )
        return self.persistence.create_template(template)

    def get_template(self, template_id: str) -> Optional[TaskTemplate]:
        """Get a task template by ID."""
        return self.persistence.get_template(template_id)

    def list_templates(self) -> list[TaskTemplate]:
        """List all task templates."""
        return self.persistence.list_templates()

    # =========================================================================
    # Task Operations (API-friendly)
    # =========================================================================

    def enqueue_task(
        self,
        task_type: str,
        params: dict,
        priority: int = 0,
        template_id: Optional[str] = None,
    ) -> Task:
        """
        Enqueue a new task for execution.

        Args:
            task_type: Type of work ("story" or "research")
            params: Execution parameters
            priority: Dispatch priority (higher = sooner)
            template_id: Optional source template

        Returns:
            The created Task
        """
        return self.queue_manager.enqueue(
            task_type=task_type,
            params=params,
            priority=priority,
            template_id=template_id,
        )

    def enqueue_from_template(
        self,
        template_id: str,
        priority: int = 0,
        param_overrides: Optional[dict] = None,
    ) -> Task:
        """
        Create and enqueue a task from a template.

        Args:
            template_id: Source template ID
            priority: Dispatch priority
            param_overrides: Override template default params

        Returns:
            The created Task
        """
        return self.queue_manager.enqueue_from_template(
            template_id=template_id,
            priority=priority,
            param_overrides=param_overrides,
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.persistence.get_task(task_id)

    def get_task_run(self, run_id: str) -> Optional[TaskRun]:
        """Get a task run by ID."""
        return self.persistence.get_task_run(run_id)

    def get_task_run_for_task(self, task_id: str) -> Optional[TaskRun]:
        """Get the task run for a task."""
        return self.persistence.get_task_run_for_task(task_id)

    def list_queued_tasks(self, limit: int = 100) -> list[Task]:
        """List all queued tasks in dispatch order."""
        return self.queue_manager.list_queued(limit=limit)

    def list_running_tasks(self, limit: int = 100) -> list[Task]:
        """List all running tasks."""
        return self.queue_manager.list_running(limit=limit)

    def list_task_runs(self, limit: int = 100) -> list[TaskRun]:
        """List recent task runs."""
        return self.persistence.list_task_runs(limit=limit)

    def cancel_task(self, task_id: str) -> Task:
        """
        Cancel a queued task.

        Only QUEUED tasks can be cancelled from queue.
        RUNNING tasks must wait for completion.

        Args:
            task_id: Task to cancel

        Returns:
            The cancelled Task
        """
        return self.queue_manager.cancel(task_id)

    def retry_task_run(
        self,
        run_id: str,
        priority: Optional[int] = None,
    ) -> Task:
        """
        Manually retry a failed task run.

        Args:
            run_id: TaskRun ID to retry
            priority: Optional priority for retry task

        Returns:
            The new retry Task
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

    def get_current_task_id(self) -> Optional[str]:
        """Get the ID of the currently executing task, if any."""
        current_task = self.dispatcher.current_job
        return current_task.task_id if current_task else None

    def get_scheduler_status(self) -> dict:
        """
        Get comprehensive scheduler status for API response.

        Returns:
            Dict containing:
            - scheduler_running: bool
            - current_task_id: Optional[str]
            - queue_length: int
            - cumulative_stats: dict
            - has_active_reservation: bool
        """
        # Get task run statistics
        run_stats = self.persistence.get_task_run_stats()
        cancelled_count = self.persistence.count_cancelled_tasks()

        return {
            "scheduler_running": self.is_running,
            "current_task_id": self.get_current_task_id(),
            "queue_length": self.queue_manager.count_queued(),
            "cumulative_stats": {
                "total_executed": run_stats["total_executed"],
                "succeeded": run_stats["succeeded"],
                "failed": run_stats["failed"],
                "cancelled": cancelled_count,
                "skipped": run_stats["skipped"],
            },
            "has_active_reservation": self.queue_manager.has_active_reservation(),
        }

    def update_task_priority(self, task_id: str, priority: int) -> Task:
        """
        Update task priority (QUEUED tasks only).

        Args:
            task_id: Task to update
            priority: New priority value

        Returns:
            Updated Task

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidOperationError: If task is not QUEUED
        """
        task = self.persistence.get_task(task_id)
        if task is None:
            from .errors import TaskNotFoundError
            raise TaskNotFoundError(task_id)

        if task.status != TaskStatus.QUEUED:
            from .errors import InvalidOperationError
            raise InvalidOperationError(
                f"Cannot update priority of task in {task.status.value} status"
            )

        return self.persistence.update_task(task_id, priority=priority)

    def list_all_tasks(self, limit: int = 100) -> list[Task]:
        """List all tasks (QUEUED, RUNNING, CANCELLED) ordered by created_at DESC."""
        return self.persistence.list_tasks(limit=limit)

    # =========================================================================
    # Direct API Support
    # =========================================================================

    def execute_direct(
        self,
        task_type: str,
        params: dict,
        reserved_by: str,
        timeout: Optional[float] = None,
    ) -> TaskRun:
        """
        Execute a direct API request with next-slot reservation.

        From DEC-004:
        1. Reserve next slot
        2. Wait for current task to complete
        3. Execute direct request
        4. Release reservation

        Args:
            task_type: Type of work
            params: Execution parameters
            reserved_by: Identifier for reservation
            timeout: Maximum wait for current task

        Returns:
            The completed TaskRun
        """
        return self.dispatcher.execute_direct(
            task_type=task_type,
            params=params,
            reserved_by=reserved_by,
            timeout=timeout,
        )

    # =========================================================================
    # TaskGroup Operations (DEC-012)
    # =========================================================================

    def create_task_group(
        self,
        tasks: list[dict],
        name: Optional[str] = None,
        priority: int = 0,
    ) -> tuple:
        """
        Create a TaskGroup and enqueue its tasks.

        From DEC-012: Tasks in a group execute sequentially.

        Args:
            tasks: List of task specs, each with 'task_type' and 'params'.
                   Tasks are assigned sequence_numbers 0, 1, 2, ... in order.
            name: Optional group name
            priority: Dispatch priority for all tasks in the group

        Returns:
            Tuple of (TaskGroup, list of created Tasks)
        """
        return self.queue_manager.create_task_group(
            tasks=tasks,
            name=name,
            priority=priority,
        )

    def create_concurrent_group(
        self,
        task_ids: list[str],
        name: Optional[str] = None,
    ) -> object:
        """
        Create a concurrent execution group from existing task IDs.

        Delegates to queue_manager.create_concurrent_group.

        Args:
            task_ids: List of task IDs to group for concurrent execution
            name: Optional group name

        Returns:
            The created TaskGroup
        """
        return self.queue_manager.create_concurrent_group(
            task_ids=task_ids,
            name=name,
        )

    def get_task_group(self, group_id: str):
        """Get a TaskGroup by ID."""
        return self.queue_manager.get_job_group(group_id)

    def get_tasks_in_group(self, group_id: str) -> list[Task]:
        """Get all tasks in a group, ordered by sequence_number."""
        return self.queue_manager.get_jobs_in_group(group_id)

    def cancel_task_group(self, group_id: str):
        """
        Cancel all QUEUED tasks in a group.

        Note: RUNNING tasks complete normally (no preemption per DEC-004).

        Args:
            group_id: Group to cancel

        Returns:
            The updated TaskGroup
        """
        return self.queue_manager.cancel_job_group(group_id)

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================

    enqueue_job = enqueue_task
    get_job = get_task
    get_job_run = get_task_run
    get_job_run_for_job = get_task_run_for_task
    list_queued_jobs = list_queued_tasks
    list_running_jobs = list_running_tasks
    list_job_runs = list_task_runs
    cancel_job = cancel_task
    retry_job_run = retry_task_run
    get_current_job_id = get_current_task_id
    create_job_group = create_task_group
    get_job_group = get_task_group
    get_jobs_in_group = get_tasks_in_group
    cancel_job_group = cancel_task_group
    update_job_priority = update_task_priority
    list_all_jobs = list_all_tasks
