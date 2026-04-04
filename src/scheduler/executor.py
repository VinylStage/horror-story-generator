"""
Executor for Task Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.3:
- Runs the actual task work and produces TaskRun
- Respects cancellation
- Reports execution result

What Executor MUST NOT do:
- Modify the Task entity (except through Dispatcher)
- Decide retry policy (RetryController's responsibility)
- Send webhooks directly (WebhookService's responsibility)
- Manage queue state
"""

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from .entities import (
    Task,
    TaskRun,
    TaskRunStatus,
)
from .persistence import PersistenceAdapter


logger = logging.getLogger(__name__)
_GLOBAL_ENV_LOCK = threading.Lock()


def _ensure_log_artifact(log_path: str, artifacts: list[str]) -> None:
    """Ensure execution log is present as the first artifact when file exists."""
    if Path(log_path).exists() and log_path not in artifacts:
        artifacts.insert(0, log_path)


class TaskHandler(ABC):
    """
    Abstract base class for task type handlers.

    Each task type (story, research) implements this interface.
    """

    @abstractmethod
    def execute(
        self,
        task: Task,
        log_path: Optional[str] = None,
    ) -> tuple[TaskRunStatus, Optional[str], Optional[int], list[str]]:
        """
        Execute the task.

        Args:
            task: The task to execute
            log_path: Optional path for execution log

        Returns:
            Tuple of (status, error, exit_code, artifacts)
        """
        ...

    @abstractmethod
    def cancel(self) -> bool:
        """
        Cancel the currently executing task.

        Returns:
            True if cancellation was initiated
        """
        ...


class DirectTaskHandler(TaskHandler):
    """
    Task handler that executes work via direct in-process function calls.
    """

    def __init__(
        self,
        project_root: Path,
        logs_dir: Path,
    ):
        """
        Initialize direct handler.

        Args:
            project_root: Project root directory
            logs_dir: Directory for execution logs
        """
        self.project_root = project_root
        self.logs_dir = logs_dir
        self._active_cancel_events: dict[int, threading.Event] = {}
        self._cancel_lock = threading.Lock()
        self._next_execution_id = 0

    def execute(
        self,
        task: Task,
        log_path: Optional[str] = None,
    ) -> tuple[TaskRunStatus, Optional[str], Optional[int], list[str]]:
        """Execute task via direct function calls."""
        cancel_event = threading.Event()
        with self._cancel_lock:
            self._next_execution_id += 1
            execution_id = self._next_execution_id
            self._active_cancel_events[execution_id] = cancel_event
        artifacts: list[str] = []

        # Ensure logs directory exists
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Generate log path if not provided
        if log_path is None:
            log_path = str(
                self.logs_dir / f"{task.task_type}_{task.task_id}.log"
            )

        logger.info(f"Executing task {task.task_id} ({task.task_type}) via direct handler")

        try:
            with open(log_path, "w") as log_file:
                if task.task_type == "story":
                    self._execute_story_task(task, log_file, artifacts, cancel_event)
                elif task.task_type == "research":
                    self._execute_research_task(task, log_file, artifacts)
                else:
                    raise ValueError(f"Unknown task type: {task.task_type}")

            if cancel_event.is_set():
                _ensure_log_artifact(log_path, artifacts)
                return (
                    TaskRunStatus.FAILED,
                    "Task was cancelled",
                    -1,
                    artifacts,
                )

            return (
                TaskRunStatus.COMPLETED,
                None,
                0,
                artifacts,
            )

        except Exception as e:
            logger.exception(f"Error executing task {task.task_id}")
            return (
                TaskRunStatus.FAILED,
                str(e),
                -1,
                artifacts,
            )
        finally:
            _ensure_log_artifact(log_path, artifacts)
            with self._cancel_lock:
                self._active_cancel_events.pop(execution_id, None)

    def cancel(self) -> bool:
        """Request cancellation for current task execution."""
        with self._cancel_lock:
            if not self._active_cancel_events:
                return False
            events = list(self._active_cancel_events.values())
        for event in events:
            event.set()
        return True

    def _execute_story_task(
        self,
        task: Task,
        log_file,
        artifacts: list[str],
        cancel_event: threading.Event,
    ) -> None:
        """Execute story task using story generator pipeline."""
        from src.story.generator import (
            generate_horror_story,
            generate_with_dedup_control,
            generate_with_topic,
        )
        from src.registry.story_registry import init_registry, close_registry
        from src.dedup.similarity import load_past_stories_into_memory

        params = task.params
        max_stories = _coerce_int_param(params, "max_stories", 1)
        interval_seconds = _coerce_int_param(params, "interval_seconds", 0)
        duration_seconds = params.get("duration_seconds")
        enable_dedup = bool(params.get("enable_dedup", False))
        execution_start_time = time.time()
        stories_generated = 0
        registry = None

        thumbnail_provider = params.get("thumbnail_provider")
        with _GLOBAL_ENV_LOCK:
            previous_thumbnail_provider = os.environ.get("THUMBNAIL_PROVIDER")
            if thumbnail_provider:
                os.environ["THUMBNAIL_PROVIDER"] = str(thumbnail_provider)

            if enable_dedup:
                registry = init_registry(db_path=params.get("db_path"))
                load_history = _coerce_int_param(params, "load_history", 200)
                past = registry.load_recent_accepted(limit=load_history)
                if past:
                    load_past_stories_into_memory(past)

            try:
                while stories_generated < max_stories:
                    if cancel_event.is_set():
                        break

                    elapsed_time = time.time() - execution_start_time
                    if duration_seconds is not None and elapsed_time >= float(duration_seconds):
                        break

                    topic = params.get("topic")
                    if topic is not None:
                        result = generate_with_topic(
                            topic=topic,
                            auto_research=params.get("auto_research", True),
                            model_spec=params.get("model"),
                            research_model_spec=params.get("research_model"),
                            save_output=True,
                            registry=registry,
                            target_length=params.get("target_length"),
                            custom_tags=params.get("tags"),
                        )
                    elif enable_dedup and registry:
                        result = generate_with_dedup_control(
                            registry=registry,
                            model_spec=params.get("model"),
                            target_length=params.get("target_length"),
                        )
                    else:
                        result = generate_horror_story(
                            model_spec=params.get("model"),
                            target_length=params.get("target_length"),
                        )

                    if result and result.get("file_path"):
                        artifacts.append(result["file_path"])
                    if result:
                        stories_generated += 1

                    if interval_seconds > 0 and stories_generated < max_stories:
                        if cancel_event.wait(timeout=interval_seconds):
                            break
            finally:
                if thumbnail_provider:
                    if previous_thumbnail_provider is None:
                        os.environ.pop("THUMBNAIL_PROVIDER", None)
                    else:
                        os.environ["THUMBNAIL_PROVIDER"] = previous_thumbnail_provider
                if registry is not None:
                    close_registry()
                log_file.write(f"stories_generated={stories_generated}\n")

    def _execute_research_task(self, task: Task, log_file, artifacts: list[str]) -> None:
        """Execute research task using research pipeline."""
        from src.research.executor.executor import run_research_pipeline

        params = task.params
        topic = str(params.get("topic", "")).strip()
        if not topic:
            raise ValueError("Research task 'topic' parameter is required and must not be empty")

        result = run_research_pipeline(
            topic=topic,
            tags=params.get("tags") or [],
            model_spec=params.get("model"),
            timeout=_coerce_int_param(params, "timeout", 300),
        )
        log_file.write(f"success={result.get('success', False)}\n")

        if not result.get("success"):
            raise RuntimeError(result.get("error") or "Research pipeline failed")

        card_path = result.get("card_path")
        if card_path:
            artifacts.append(card_path)


class Executor:
    """
    Executes tasks and manages TaskRun lifecycle.

    From IMPLEMENTATION_PLAN.md Section 1.3:
    1. Execute work via task handler
    2. Update TaskRun with result
    3. Signal completion

    Execution happens synchronously - the caller (Dispatcher) blocks
    until execution completes.
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        handler: Optional[TaskHandler] = None,
    ):
        """
        Initialize Executor.

        Args:
            persistence: PersistenceAdapter for TaskRun updates
            handler: TaskHandler for actual execution (injectable for testing)
        """
        self.persistence = persistence
        self._handler = handler
        self._current_task: Optional[Task] = None

    def set_handler(self, handler: TaskHandler) -> None:
        """Set the task handler for execution."""
        self._handler = handler

    def execute(self, task: Task, task_run: TaskRun) -> TaskRun:
        """
        Execute a task and return the completed TaskRun.

        This is the main execution entry point called by Dispatcher.

        Args:
            task: The task to execute
            task_run: The TaskRun record for this execution

        Returns:
            The completed TaskRun with terminal status
        """
        if self._handler is None:
            raise RuntimeError("Task handler not set. Call set_handler() first.")

        self._current_task = task

        try:
            # Execute via handler
            status, error, exit_code, artifacts = self._handler.execute(
                task,
                log_path=task_run.log_path,
            )

            # Update TaskRun with result
            now = datetime.utcnow().isoformat() + "Z"

            updated_run = self.persistence.update_task_run(
                task_run.run_id,
                status=status,
                finished_at=now,
                exit_code=exit_code,
                error=error,
                artifacts=artifacts,
            )

            logger.info(
                f"Task {task.task_id} execution completed: "
                f"status={status.value}, exit_code={exit_code}"
            )

            return updated_run

        except Exception as e:
            # Handle unexpected execution errors
            logger.exception(f"Unexpected error executing task {task.task_id}")

            now = datetime.utcnow().isoformat() + "Z"

            return self.persistence.update_task_run(
                task_run.run_id,
                status=TaskRunStatus.FAILED,
                finished_at=now,
                error=f"Execution error: {str(e)}",
            )

        finally:
            self._current_task = None

    def cancel_current(self) -> bool:
        """
        Cancel the currently executing task.

        Returns:
            True if cancellation was initiated
        """
        if self._current_task is None:
            return False

        if self._handler is not None:
            return self._handler.cancel()

        return False

    @property
    def is_executing(self) -> bool:
        """Check if executor is currently running a task."""
        return self._current_task is not None


class SkipExecutor:
    """
    Special executor that immediately marks tasks as SKIPPED.

    Used for dedup scenarios where execution should be skipped.
    """

    def __init__(self, persistence: PersistenceAdapter, reason: str = "Skipped"):
        self.persistence = persistence
        self.reason = reason

    def execute(self, task: Task, task_run: TaskRun) -> TaskRun:
        """Mark task as skipped immediately."""
        now = datetime.utcnow().isoformat() + "Z"

        return self.persistence.update_task_run(
            task_run.run_id,
            status=TaskRunStatus.SKIPPED,
            finished_at=now,
            error=self.reason,
        )


# Backward compatibility aliases
SubprocessTaskHandler = DirectTaskHandler
JobHandler = TaskHandler
SubprocessJobHandler = DirectTaskHandler


def _coerce_int_param(params: dict, key: str, default: int) -> int:
    """Convert task param to int while preserving explicit zero values."""
    value = params.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid integer value for '{key}': {value!r}") from e
