"""
Dispatcher for Job Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.2:
- Pulls jobs from queue and hands them to Executor
- Manages dispatch loop
- Respects Direct API next-slot reservation (DEC-004)
- Single-worker dispatch (DEC-011)

What Dispatcher MUST NOT do:
- Modify job parameters (immutable after dispatch per INV-001)
- Execute the job itself
- Handle retries
- Manage concurrency limits beyond single-worker
"""

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Protocol

from .entities import (
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
    ReservationStatus,
)
from .errors import (
    ConcurrencyViolationError,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager


logger = logging.getLogger(__name__)


class DispatcherState(str, Enum):
    """Dispatcher lifecycle states."""

    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    WAITING_FOR_RESERVATION = "WAITING_FOR_RESERVATION"


class ExecutorProtocol(Protocol):
    """Protocol for job executor."""

    def execute(self, job: Job, job_run: JobRun) -> JobRun:
        """
        Execute a job and return the completed JobRun.

        Args:
            job: The job to execute
            job_run: The JobRun record for this execution

        Returns:
            The completed JobRun with terminal status
        """
        ...


class Dispatcher:
    """
    Pulls jobs from queue and dispatches to executor.

    Key behaviors (from IMPLEMENTATION_PLAN.md):
    1. Check if next-slot is reserved → wait
    2. Query QueueManager.get_next()
    3. If job exists:
       a. Transition job: QUEUED → RUNNING (atomic with JobRun creation)
       b. Hand to Executor
    4. Wait for Executor completion
    5. Loop

    Single-worker enforcement (DEC-011):
    - Maximum 1 job running at any time
    - No concurrent dispatch
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        poll_interval: float = 1.0,
    ):
        """
        Initialize Dispatcher.

        Args:
            persistence: PersistenceAdapter for storage
            queue_manager: QueueManager for queue operations
            poll_interval: Seconds between queue polls when idle
        """
        self.persistence = persistence
        self.queue_manager = queue_manager
        self.poll_interval = poll_interval

        self._state = DispatcherState.STOPPED
        self._executor: Optional[ExecutorProtocol] = None
        self._current_job: Optional[Job] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callback for post-execution notifications (e.g., to RetryController)
        self._on_job_completed: Optional[Callable[[Job, JobRun], None]] = None

    @property
    def state(self) -> DispatcherState:
        """Get current dispatcher state."""
        return self._state

    @property
    def current_job(self) -> Optional[Job]:
        """Get the currently running job, if any."""
        return self._current_job

    def set_executor(self, executor: ExecutorProtocol) -> None:
        """
        Set the executor for job execution.

        Must be called before starting the dispatcher.
        """
        self._executor = executor

    def set_on_job_completed(
        self,
        callback: Callable[[Job, JobRun], None],
    ) -> None:
        """
        Set callback for job completion notification.

        Used to notify RetryController and WebhookService.
        """
        self._on_job_completed = callback

    # =========================================================================
    # Single Dispatch Operation
    # =========================================================================

    def dispatch_one(self) -> Optional[tuple[Job, JobRun]]:
        """
        Attempt to dispatch a single job.

        This is the core dispatch operation:
        1. Check for active reservation
        2. Get next queued job
        3. Atomically claim (QUEUED → RUNNING + create JobRun)
        4. Execute via executor
        5. Notify completion callback

        Returns:
            (Job, JobRun) if a job was dispatched and executed, None otherwise

        Raises:
            RuntimeError: If executor is not set
        """
        if self._executor is None:
            raise RuntimeError("Executor not set. Call set_executor() first.")

        # Check DEC-011: Single-worker constraint
        if self._current_job is not None:
            logger.debug("Already running a job, skipping dispatch")
            return None

        # Check DEC-004: Next-slot reservation
        if self.queue_manager.has_active_reservation():
            logger.debug("Active reservation exists, pausing dispatch")
            return None

        # Get next job from queue
        next_job = self.queue_manager.get_next()
        if next_job is None:
            logger.debug("Queue is empty")
            return None

        # Atomic claim: QUEUED → RUNNING + create JobRun
        try:
            job, job_run = self.persistence.atomic_claim_job(next_job.job_id)
            logger.info(
                f"Dispatched job {job.job_id} (type={job.job_type}, "
                f"priority={job.priority})"
            )
        except ConcurrencyViolationError as e:
            # Job was claimed by another process (race condition)
            logger.warning(f"Job {next_job.job_id} already claimed: {e}")
            return None

        # Track current job
        self._current_job = job

        try:
            # Execute via executor
            completed_run = self._executor.execute(job, job_run)

            # Update job finished_at
            self.persistence.update_job(
                job.job_id,
                finished_at=completed_run.finished_at,
            )

            # Refresh job state
            job = self.persistence.get_job(job.job_id)

            logger.info(
                f"Job {job.job_id} completed with status {completed_run.status.value}"
            )

            # Notify completion callback
            if self._on_job_completed is not None:
                try:
                    self._on_job_completed(job, completed_run)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

            return job, completed_run

        finally:
            # Clear current job
            self._current_job = None

    # =========================================================================
    # Dispatch Loop
    # =========================================================================

    def start(self, blocking: bool = False) -> None:
        """
        Start the dispatch loop.

        Args:
            blocking: If True, run in current thread. If False, run in background.
        """
        if self._state != DispatcherState.STOPPED:
            raise RuntimeError(f"Cannot start dispatcher in {self._state.value} state")

        if self._executor is None:
            raise RuntimeError("Executor not set. Call set_executor() first.")

        self._stop_event.clear()
        self._state = DispatcherState.RUNNING

        if blocking:
            self._dispatch_loop()
        else:
            self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the dispatch loop gracefully.

        Waits for current job to complete (no preemption per DEC-004).

        Args:
            timeout: Maximum seconds to wait for current job
        """
        if self._state == DispatcherState.STOPPED:
            return

        logger.info("Stopping dispatcher...")
        self._state = DispatcherState.STOPPING
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Dispatcher thread did not stop within timeout")
            self._thread = None

        self._state = DispatcherState.STOPPED
        logger.info("Dispatcher stopped")

    def _dispatch_loop(self) -> None:
        """Main dispatch loop."""
        logger.info("Dispatcher loop started")

        while not self._stop_event.is_set():
            try:
                result = self.dispatch_one()

                if result is None:
                    # No job dispatched, wait before polling again
                    self._stop_event.wait(self.poll_interval)
                # If a job was dispatched, immediately check for next

            except Exception as e:
                logger.error(f"Error in dispatch loop: {e}", exc_info=True)
                self._stop_event.wait(self.poll_interval)

        logger.info("Dispatcher loop ended")

    # =========================================================================
    # Direct API Support (DEC-004)
    # =========================================================================

    def wait_for_current_job(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the current job to complete.

        Used by Direct API to wait for running job before executing.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Returns:
            True if no job is running, False if timeout reached
        """
        if self._current_job is None:
            return True

        start = time.time()
        while self._current_job is not None:
            if timeout is not None:
                elapsed = time.time() - start
                if elapsed >= timeout:
                    return False
            time.sleep(0.1)

        return True

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
        3. Execute direct request (NOT a Job)
        4. Release reservation
        5. Return result

        This creates a temporary Job and JobRun for tracking but
        follows the Direct API execution contract.

        Args:
            job_type: Type of work
            params: Execution parameters
            reserved_by: Identifier for reservation
            timeout: Maximum wait for current job

        Returns:
            The completed JobRun

        Raises:
            RuntimeError: If executor not set
            ReservationConflictError: If another reservation active
            TimeoutError: If timeout waiting for current job
        """
        if self._executor is None:
            raise RuntimeError("Executor not set")

        # Reserve next slot
        reservation = self.queue_manager.reserve_next_slot(reserved_by)
        logger.info(f"Direct execution reserved slot: {reservation.reservation_id}")

        try:
            # Wait for current job
            if not self.wait_for_current_job(timeout):
                raise TimeoutError("Timeout waiting for current job to complete")

            # Create temporary job for execution
            # Note: This is a Job entity but follows Direct API semantics
            job = Job.create(
                job_type=job_type,
                params=params,
            )
            job = self.persistence.create_job(job)

            # Claim and execute
            job, job_run = self.persistence.atomic_claim_job(job.job_id)
            self._current_job = job

            try:
                completed_run = self._executor.execute(job, job_run)

                # Update job finished_at
                self.persistence.update_job(
                    job.job_id,
                    finished_at=completed_run.finished_at,
                )

                logger.info(
                    f"Direct execution completed: {completed_run.status.value}"
                )

                return completed_run

            finally:
                self._current_job = None

        finally:
            # Always release reservation
            self.queue_manager.release_reservation(reservation.reservation_id)
            logger.info(f"Direct execution released slot: {reservation.reservation_id}")

    # =========================================================================
    # Recovery Support
    # =========================================================================

    def is_running(self) -> bool:
        """Check if dispatcher is running."""
        return self._state == DispatcherState.RUNNING

    def is_busy(self) -> bool:
        """Check if dispatcher is executing a job."""
        return self._current_job is not None
