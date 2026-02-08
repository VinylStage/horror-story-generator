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
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from .entities import (
    Task,
    TaskRun,
    TaskRunStatus,
)
from .persistence import PersistenceAdapter


logger = logging.getLogger(__name__)


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


class SubprocessTaskHandler(TaskHandler):
    """
    Task handler that executes work via subprocess.

    This matches the existing CLI-based execution model.
    """

    def __init__(
        self,
        project_root: Path,
        logs_dir: Path,
    ):
        """
        Initialize subprocess handler.

        Args:
            project_root: Project root directory for subprocess cwd
            logs_dir: Directory for execution logs
        """
        self.project_root = project_root
        self.logs_dir = logs_dir
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def execute(
        self,
        task: Task,
        log_path: Optional[str] = None,
    ) -> tuple[TaskRunStatus, Optional[str], Optional[int], list[str]]:
        """Execute task via subprocess."""
        self._cancelled = False

        # Ensure logs directory exists
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Generate log path if not provided
        if log_path is None:
            log_path = str(
                self.logs_dir / f"{task.task_type}_{task.task_id}.log"
            )

        # Build command based on task type
        cmd = self._build_command(task)

        logger.info(f"Executing task {task.task_id}: {' '.join(cmd)}")

        try:
            with open(log_path, "w") as log_file:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=self.project_root,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )

                # Wait for completion
                exit_code = self._process.wait()

            self._process = None

            if self._cancelled:
                return (
                    TaskRunStatus.FAILED,
                    "Task was cancelled",
                    exit_code,
                    [],
                )

            # Parse artifacts from log or output
            artifacts = self._collect_artifacts(task, log_path)

            if exit_code == 0:
                return (
                    TaskRunStatus.COMPLETED,
                    None,
                    exit_code,
                    artifacts,
                )
            else:
                # Read error from log
                error = self._read_error_from_log(log_path)
                return (
                    TaskRunStatus.FAILED,
                    error or f"Process exited with code {exit_code}",
                    exit_code,
                    artifacts,
                )

        except Exception as e:
            logger.exception(f"Error executing task {task.task_id}")
            return (
                TaskRunStatus.FAILED,
                str(e),
                -1,
                [],
            )

    def cancel(self) -> bool:
        """Cancel the currently executing subprocess."""
        if self._process is not None:
            self._cancelled = True
            try:
                self._process.terminate()
                return True
            except Exception as e:
                logger.error(f"Error terminating process: {e}")
        return False

    def _build_command(self, task: Task) -> list[str]:
        """Build subprocess command based on task type."""
        params = task.params

        if task.task_type == "story":
            cmd = [sys.executable, str(self.project_root / "main.py")]

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
            if params.get("target_length"):
                cmd.extend(["--target-length", str(params["target_length"])])

            # Issue #123: Topic-based generation params
            if params.get("topic"):
                cmd.extend(["--topic", params["topic"]])
            if params.get("tags"):
                cmd.append("--tags")
                cmd.extend(params["tags"])
            if params.get("auto_research") is False:
                cmd.append("--no-auto-research")
            if params.get("research_model"):
                cmd.extend(["--research-model", params["research_model"]])
            if params.get("thumbnail_provider"):
                cmd.extend(["--thumbnail-provider", params["thumbnail_provider"]])

            return cmd

        elif task.task_type == "research":
            cmd = [sys.executable, "-m", "src.research.executor", "run"]

            topic = params.get("topic", "")
            cmd.append(topic)

            tags = params.get("tags", [])
            if tags:
                cmd.append("--tags")
                cmd.extend(tags)

            if params.get("model"):
                cmd.extend(["--model", params["model"]])
            if params.get("timeout"):
                cmd.extend(["--timeout", str(params["timeout"])])

            return cmd

        else:
            raise ValueError(f"Unknown task type: {task.task_type}")

    def _collect_artifacts(self, task: Task, log_path: str) -> list[str]:
        """Collect artifacts produced by the task."""
        artifacts = []

        # Include log file as artifact
        if Path(log_path).exists():
            artifacts.append(log_path)

        # For story tasks, look for generated story files
        if task.task_type == "story":
            stories_dir = self.project_root / "data" / "stories"
            if stories_dir.exists():
                # Get recent files (created after task started)
                # This is a simple heuristic
                for story_file in stories_dir.glob("*.json"):
                    artifacts.append(str(story_file))

        # For research tasks, look for research cards
        elif task.task_type == "research":
            research_dir = self.project_root / "data" / "research"
            if research_dir.exists():
                for card_file in research_dir.glob("*.json"):
                    artifacts.append(str(card_file))

        return artifacts

    def _read_error_from_log(self, log_path: str) -> Optional[str]:
        """Read last error lines from log file."""
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                # Return last few non-empty lines
                error_lines = [l.strip() for l in lines[-10:] if l.strip()]
                if error_lines:
                    return "\n".join(error_lines[-3:])
        except Exception:
            pass
        return None


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
JobHandler = TaskHandler
SubprocessJobHandler = SubprocessTaskHandler
