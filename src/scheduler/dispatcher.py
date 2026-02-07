"""
Dispatcher for Task Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.2:
- Pulls tasks from queue and hands them to Executor
- Manages dispatch loop
- Respects Direct API next-slot reservation (DEC-004)
- Single-worker dispatch (DEC-011) with concurrent group support

What Dispatcher MUST NOT do:
- Modify task parameters (immutable after dispatch per INV-001)
- Execute the task itself
- Handle retries
- Manage concurrency limits beyond single-worker (except concurrent groups)
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Protocol

from .entities import (
    Task,
    TaskRun,
    TaskStatus,
    TaskRunStatus,
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
    """Protocol for task executor."""

    def execute(self, task: Task, task_run: TaskRun) -> TaskRun:
        """
        Execute a task and return the completed TaskRun.

        Args:
            task: The task to execute
            task_run: The TaskRun record for this execution

        Returns:
            The completed TaskRun with terminal status
        """
        ...


class Dispatcher:
    """
    Pulls tasks from queue and dispatches to executor.

    Key behaviors (from IMPLEMENTATION_PLAN.md):
    1. Check if next-slot is reserved -> wait
    2. Query QueueManager.get_next()
    3. If task exists:
       a. Transition task: QUEUED -> RUNNING (atomic with TaskRun creation)
       b. Hand to Executor
    4. Wait for Executor completion
    5. Loop

    Single-worker enforcement (DEC-011):
    - Maximum 1 task running at any time (sequential mode)
    - Concurrent groups dispatch all group tasks in parallel via ThreadPoolExecutor
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
        self._current_tasks: dict[str, Task] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._tasks_lock = threading.Lock()

        # Callback for post-execution notifications (e.g., to RetryController)
        self._on_task_completed: Optional[Callable[[Task, TaskRun], None]] = None

    @property
    def state(self) -> DispatcherState:
        """Get current dispatcher state."""
        return self._state

    @property
    def current_task(self) -> Optional[Task]:
        """Get the currently running task, if any (backward compat).

        Returns the first running task or None if no tasks are running.
        """
        with self._tasks_lock:
            if not self._current_tasks:
                return None
            return next(iter(self._current_tasks.values()))

    def set_executor(self, executor: ExecutorProtocol) -> None:
        """
        Set the executor for task execution.

        Must be called before starting the dispatcher.
        """
        self._executor = executor

    def set_on_task_completed(
        self,
        callback: Callable[[Task, TaskRun], None],
    ) -> None:
        """
        Set callback for task completion notification.

        Used to notify RetryController and WebhookService.
        """
        self._on_task_completed = callback

    # =========================================================================
    # Single Dispatch Operation
    # =========================================================================

    def dispatch_one(self) -> Optional[tuple[Task, TaskRun]]:
        """
        Attempt to dispatch a single task (or a concurrent group).

        This is the core dispatch operation:
        1. Check for active reservation
        2. Get next queued task
        3. If task belongs to a concurrent group, dispatch entire group
        4. Otherwise, atomically claim (QUEUED -> RUNNING + create TaskRun)
        5. Execute via executor
        6. Notify completion callback

        Returns:
            (Task, TaskRun) if a task was dispatched and executed, None otherwise.
            For concurrent groups, returns the result of the first task in the group.

        Raises:
            RuntimeError: If executor is not set
        """
        if self._executor is None:
            raise RuntimeError("Executor not set. Call set_executor() first.")

        # Check DEC-011: Single-worker constraint (check if any tasks running)
        with self._tasks_lock:
            if self._current_tasks:
                logger.debug("Already running task(s), skipping dispatch")
                return None

        # Check DEC-004: Next-slot reservation
        if self.queue_manager.has_active_reservation():
            logger.debug("Active reservation exists, pausing dispatch")
            return None

        # Get next task from queue
        next_task = self.queue_manager.get_next()
        if next_task is None:
            logger.debug("Queue is empty")
            return None

        # Check if next task is part of a concurrent group
        if next_task.group_id is not None:
            group = self.persistence.get_task_group(next_task.group_id)
            if group is not None and group.execution_mode == "concurrent":
                # Gather all QUEUED tasks in this concurrent group
                group_tasks = self.persistence.get_tasks_by_group(next_task.group_id)
                queued_tasks = [
                    t for t in group_tasks if t.status == TaskStatus.QUEUED
                ]
                if queued_tasks:
                    return self._dispatch_concurrent_group(queued_tasks)

        # Standard single-task dispatch
        # Atomic claim: QUEUED -> RUNNING + create TaskRun
        try:
            task, task_run = self.persistence.atomic_claim_task(next_task.task_id)
            logger.info(
                f"Dispatched task {task.task_id} (type={task.task_type}, "
                f"priority={task.priority})"
            )
        except ConcurrencyViolationError as e:
            # Task was claimed by another process (race condition)
            logger.warning(f"Task {next_task.task_id} already claimed: {e}")
            return None

        # Track current task
        with self._tasks_lock:
            self._current_tasks[task.task_id] = task

        try:
            # Execute via executor
            completed_run = self._executor.execute(task, task_run)

            # Update task finished_at
            self.persistence.update_task(
                task.task_id,
                finished_at=completed_run.finished_at,
            )

            # Refresh task state
            task = self.persistence.get_task(task.task_id)

            logger.info(
                f"Task {task.task_id} completed with status {completed_run.status.value}"
            )

            # Notify completion callback
            if self._on_task_completed is not None:
                try:
                    self._on_task_completed(task, completed_run)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

            return task, completed_run

        finally:
            # Clear current task
            with self._tasks_lock:
                self._current_tasks.pop(task.task_id, None)

    # =========================================================================
    # Concurrent Group Dispatch
    # =========================================================================

    def _dispatch_concurrent_group(
        self,
        tasks: list[Task],
    ) -> Optional[tuple[Task, TaskRun]]:
        """
        Dispatch a list of tasks from the same concurrent group in parallel.

        Uses concurrent.futures.ThreadPoolExecutor to execute all tasks
        simultaneously. Each task goes through atomic_claim + execute cycle.
        All tasks are tracked in _current_tasks dict.

        After all tasks complete, removes them from _current_tasks and
        notifies the completion callback for each.

        Args:
            tasks: List of QUEUED Tasks from the same concurrent group

        Returns:
            (Task, TaskRun) for the first task in the group, or None if
            no tasks could be claimed.
        """
        if self._executor is None:
            raise RuntimeError("Executor not set. Call set_executor() first.")

        first_result: Optional[tuple[Task, TaskRun]] = None
        results: list[tuple[Task, TaskRun]] = []

        def _execute_single(task: Task) -> Optional[tuple[Task, TaskRun]]:
            """Claim and execute a single task within the concurrent group."""
            try:
                claimed_task, task_run = self.persistence.atomic_claim_task(
                    task.task_id
                )
                logger.info(
                    f"Dispatched concurrent task {claimed_task.task_id} "
                    f"(type={claimed_task.task_type}, group={claimed_task.group_id})"
                )
            except ConcurrencyViolationError as e:
                logger.warning(
                    f"Concurrent task {task.task_id} already claimed: {e}"
                )
                return None

            # Track in current tasks
            with self._tasks_lock:
                self._current_tasks[claimed_task.task_id] = claimed_task

            try:
                completed_run = self._executor.execute(claimed_task, task_run)

                # Update task finished_at
                self.persistence.update_task(
                    claimed_task.task_id,
                    finished_at=completed_run.finished_at,
                )

                # Refresh task state
                refreshed_task = self.persistence.get_task(claimed_task.task_id)

                logger.info(
                    f"Concurrent task {refreshed_task.task_id} completed "
                    f"with status {completed_run.status.value}"
                )

                return refreshed_task, completed_run

            except Exception as e:
                logger.error(
                    f"Error executing concurrent task {claimed_task.task_id}: {e}",
                    exc_info=True,
                )
                return None

            finally:
                with self._tasks_lock:
                    self._current_tasks.pop(claimed_task.task_id, None)

        # Execute all tasks in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures: list[Future] = [
                pool.submit(_execute_single, task) for task in tasks
            ]

            # Collect results as they complete
            for future in futures:
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    logger.error(
                        f"Unexpected error in concurrent dispatch future: {e}",
                        exc_info=True,
                    )

        # Notify completion callbacks for all completed tasks
        for task, completed_run in results:
            if self._on_task_completed is not None:
                try:
                    self._on_task_completed(task, completed_run)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

        # Return first result for backward compatibility
        if results:
            first_result = results[0]

        return first_result

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

        Waits for current task(s) to complete (no preemption per DEC-004).

        Args:
            timeout: Maximum seconds to wait for current task(s)
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
                    # No task dispatched, wait before polling again
                    self._stop_event.wait(self.poll_interval)
                # If a task was dispatched, immediately check for next

            except Exception as e:
                logger.error(f"Error in dispatch loop: {e}", exc_info=True)
                self._stop_event.wait(self.poll_interval)

        logger.info("Dispatcher loop ended")

    # =========================================================================
    # Direct API Support (DEC-004)
    # =========================================================================

    def wait_for_current_task(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the current task(s) to complete.

        Used by Direct API to wait for running task(s) before executing.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Returns:
            True if no tasks are running, False if timeout reached
        """
        with self._tasks_lock:
            if not self._current_tasks:
                return True

        start = time.time()
        while True:
            with self._tasks_lock:
                if not self._current_tasks:
                    return True
            if timeout is not None:
                elapsed = time.time() - start
                if elapsed >= timeout:
                    return False
            time.sleep(0.1)

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
        2. Wait for current task(s) to complete
        3. Execute direct request (NOT a queued Task)
        4. Release reservation
        5. Return result

        This creates a temporary Task and TaskRun for tracking but
        follows the Direct API execution contract.

        Args:
            task_type: Type of work
            params: Execution parameters
            reserved_by: Identifier for reservation
            timeout: Maximum wait for current task(s)

        Returns:
            The completed TaskRun

        Raises:
            RuntimeError: If executor not set
            ReservationConflictError: If another reservation active
            TimeoutError: If timeout waiting for current task(s)
        """
        if self._executor is None:
            raise RuntimeError("Executor not set")

        # Reserve next slot
        reservation = self.queue_manager.reserve_next_slot(reserved_by)
        logger.info(f"Direct execution reserved slot: {reservation.reservation_id}")

        try:
            # Wait for current task(s)
            if not self.wait_for_current_task(timeout):
                raise TimeoutError("Timeout waiting for current task(s) to complete")

            # Create temporary task for execution
            # Note: This is a Task entity but follows Direct API semantics
            task = Task.create(
                task_type=task_type,
                params=params,
            )
            task = self.persistence.create_task(task)

            # Claim and execute
            task, task_run = self.persistence.atomic_claim_task(task.task_id)
            with self._tasks_lock:
                self._current_tasks[task.task_id] = task

            try:
                completed_run = self._executor.execute(task, task_run)

                # Update task finished_at
                self.persistence.update_task(
                    task.task_id,
                    finished_at=completed_run.finished_at,
                )

                logger.info(
                    f"Direct execution completed: {completed_run.status.value}"
                )

                return completed_run

            finally:
                with self._tasks_lock:
                    self._current_tasks.pop(task.task_id, None)

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
        """Check if dispatcher is executing task(s)."""
        with self._tasks_lock:
            return bool(self._current_tasks)

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================

    @property
    def current_job(self) -> Optional[Task]:
        """Backward compat alias for current_task."""
        return self.current_task

    @property
    def _current_job(self) -> Optional[Task]:
        """Backward compat: returns first running task or None."""
        return self.current_task

    @_current_job.setter
    def _current_job(self, value: Optional[Task]) -> None:
        """Backward compat setter: ignored (use _current_tasks dict directly)."""
        # This setter exists to prevent AttributeError from legacy code
        # that may still assign to _current_job. The actual tracking is
        # done via _current_tasks dict.
        pass

    def set_on_job_completed(
        self,
        callback: Callable[[Task, TaskRun], None],
    ) -> None:
        """Backward compat alias for set_on_task_completed."""
        self.set_on_task_completed(callback)

    def wait_for_current_job(self, timeout: Optional[float] = None) -> bool:
        """Backward compat alias for wait_for_current_task."""
        return self.wait_for_current_task(timeout)
