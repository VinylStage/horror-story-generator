"""
Executor for Job Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.3:
- Runs the actual job work and produces JobRun
- Respects cancellation
- Reports execution result

What Executor MUST NOT do:
- Modify the Job entity (except through Dispatcher)
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
    Job,
    JobRun,
    JobRunStatus,
)
from .persistence import PersistenceAdapter


logger = logging.getLogger(__name__)


class JobHandler(ABC):
    """
    Abstract base class for job type handlers.

    Each job type (story, research) implements this interface.
    """

    @abstractmethod
    def execute(
        self,
        job: Job,
        log_path: Optional[str] = None,
    ) -> tuple[JobRunStatus, Optional[str], Optional[int], list[str]]:
        """
        Execute the job.

        Args:
            job: The job to execute
            log_path: Optional path for execution log

        Returns:
            Tuple of (status, error, exit_code, artifacts)
        """
        ...

    @abstractmethod
    def cancel(self) -> bool:
        """
        Cancel the currently executing job.

        Returns:
            True if cancellation was initiated
        """
        ...


class SubprocessJobHandler(JobHandler):
    """
    Job handler that executes work via subprocess.

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
        job: Job,
        log_path: Optional[str] = None,
    ) -> tuple[JobRunStatus, Optional[str], Optional[int], list[str]]:
        """Execute job via subprocess."""
        self._cancelled = False

        # Ensure logs directory exists
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Generate log path if not provided
        if log_path is None:
            log_path = str(
                self.logs_dir / f"{job.job_type}_{job.job_id}.log"
            )

        # Build command based on job type
        cmd = self._build_command(job)

        logger.info(f"Executing job {job.job_id}: {' '.join(cmd)}")

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
                    JobRunStatus.FAILED,
                    "Job was cancelled",
                    exit_code,
                    [],
                )

            # Parse artifacts from log or output
            artifacts = self._collect_artifacts(job, log_path)

            if exit_code == 0:
                return (
                    JobRunStatus.COMPLETED,
                    None,
                    exit_code,
                    artifacts,
                )
            else:
                # Read error from log
                error = self._read_error_from_log(log_path)
                return (
                    JobRunStatus.FAILED,
                    error or f"Process exited with code {exit_code}",
                    exit_code,
                    artifacts,
                )

        except Exception as e:
            logger.exception(f"Error executing job {job.job_id}")
            return (
                JobRunStatus.FAILED,
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

    def _build_command(self, job: Job) -> list[str]:
        """Build subprocess command based on job type."""
        params = job.params

        if job.job_type == "story":
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

            return cmd

        elif job.job_type == "research":
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
            raise ValueError(f"Unknown job type: {job.job_type}")

    def _collect_artifacts(self, job: Job, log_path: str) -> list[str]:
        """Collect artifacts produced by the job."""
        artifacts = []

        # Include log file as artifact
        if Path(log_path).exists():
            artifacts.append(log_path)

        # For story jobs, look for generated story files
        if job.job_type == "story":
            stories_dir = self.project_root / "data" / "stories"
            if stories_dir.exists():
                # Get recent files (created after job started)
                # This is a simple heuristic
                for story_file in stories_dir.glob("*.json"):
                    artifacts.append(str(story_file))

        # For research jobs, look for research cards
        elif job.job_type == "research":
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
    Executes jobs and manages JobRun lifecycle.

    From IMPLEMENTATION_PLAN.md Section 1.3:
    1. Execute work via job handler
    2. Update JobRun with result
    3. Signal completion

    Execution happens synchronously - the caller (Dispatcher) blocks
    until execution completes.
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        handler: Optional[JobHandler] = None,
    ):
        """
        Initialize Executor.

        Args:
            persistence: PersistenceAdapter for JobRun updates
            handler: JobHandler for actual execution (injectable for testing)
        """
        self.persistence = persistence
        self._handler = handler
        self._current_job: Optional[Job] = None

    def set_handler(self, handler: JobHandler) -> None:
        """Set the job handler for execution."""
        self._handler = handler

    def execute(self, job: Job, job_run: JobRun) -> JobRun:
        """
        Execute a job and return the completed JobRun.

        This is the main execution entry point called by Dispatcher.

        Args:
            job: The job to execute
            job_run: The JobRun record for this execution

        Returns:
            The completed JobRun with terminal status
        """
        if self._handler is None:
            raise RuntimeError("Job handler not set. Call set_handler() first.")

        self._current_job = job

        try:
            # Execute via handler
            status, error, exit_code, artifacts = self._handler.execute(
                job,
                log_path=job_run.log_path,
            )

            # Update JobRun with result
            now = datetime.utcnow().isoformat() + "Z"

            updated_run = self.persistence.update_job_run(
                job_run.run_id,
                status=status,
                finished_at=now,
                exit_code=exit_code,
                error=error,
                artifacts=artifacts,
            )

            logger.info(
                f"Job {job.job_id} execution completed: "
                f"status={status.value}, exit_code={exit_code}"
            )

            return updated_run

        except Exception as e:
            # Handle unexpected execution errors
            logger.exception(f"Unexpected error executing job {job.job_id}")

            now = datetime.utcnow().isoformat() + "Z"

            return self.persistence.update_job_run(
                job_run.run_id,
                status=JobRunStatus.FAILED,
                finished_at=now,
                error=f"Execution error: {str(e)}",
            )

        finally:
            self._current_job = None

    def cancel_current(self) -> bool:
        """
        Cancel the currently executing job.

        Returns:
            True if cancellation was initiated
        """
        if self._current_job is None:
            return False

        if self._handler is not None:
            return self._handler.cancel()

        return False

    @property
    def is_executing(self) -> bool:
        """Check if executor is currently running a job."""
        return self._current_job is not None


class SkipExecutor:
    """
    Special executor that immediately marks jobs as SKIPPED.

    Used for dedup scenarios where execution should be skipped.
    """

    def __init__(self, persistence: PersistenceAdapter, reason: str = "Skipped"):
        self.persistence = persistence
        self.reason = reason

    def execute(self, job: Job, job_run: JobRun) -> JobRun:
        """Mark job as skipped immediately."""
        now = datetime.utcnow().isoformat() + "Z"

        return self.persistence.update_job_run(
            job_run.run_id,
            status=JobRunStatus.SKIPPED,
            finished_at=now,
            error=self.reason,
        )
