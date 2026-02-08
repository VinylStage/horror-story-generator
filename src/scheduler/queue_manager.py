"""
Queue Manager for Task Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.1:
- Maintains the ordered queue of QUEUED tasks
- Provides insertion, cancellation, reordering
- Supports Direct API next-slot reservation (DEC-004)

What QueueManager MUST NOT do:
- Execute tasks (Executor's responsibility)
- Create TaskRuns (Executor's responsibility)
- Manage retry logic (RetryController's responsibility)
- Interact with external APIs or webhooks
"""

from datetime import datetime, timedelta
from typing import Optional

from .entities import (
    Task,
    TaskRun,
    TaskGroup,
    TaskStatus,
    TaskRunStatus,
    TaskGroupStatus,
    DirectReservation,
    ReservationStatus,
)
from .errors import (
    InvalidOperationError,
    TaskNotFoundError,
    ReservationConflictError,
)
from .persistence import PersistenceAdapter


# Default reservation expiry (from PERSISTENCE_SCHEMA.md Section 2.5)
DEFAULT_RESERVATION_EXPIRY_MINUTES = 10


class QueueManager:
    """
    Manages the task queue with priority-based ordering.

    Key behaviors:
    - Insertion: Assign position using gap strategy
    - Ordering: priority DESC, position ASC, created_at ASC (INV-004)
    - Cancellation: QUEUED -> CANCELLED only
    - Direct API Reservation: Blocks queue dispatch (DEC-004)
    """

    def __init__(self, persistence: PersistenceAdapter):
        """
        Initialize QueueManager.

        Args:
            persistence: PersistenceAdapter for storage operations
        """
        self.persistence = persistence

    # =========================================================================
    # Task Insertion
    # =========================================================================

    def enqueue(
        self,
        task_type: str,
        params: dict,
        priority: int = 0,
        template_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        group_id: Optional[str] = None,
        sequence_number: Optional[int] = None,
        retry_of: Optional[str] = None,
    ) -> Task:
        """
        Add a new task to the queue.

        From IMPLEMENTATION_PLAN.md:
        Task added -> assign position -> persist to SQLite -> status = QUEUED

        Args:
            task_type: Type of work ("story" or "research")
            params: Execution parameters
            priority: Dispatch priority (higher = sooner)
            template_id: Source template reference
            schedule_id: Triggering schedule reference
            group_id: TaskGroup membership
            sequence_number: Order within TaskGroup (0-indexed)
            retry_of: Previous task in retry chain

        Returns:
            The created Task with assigned position
        """
        task = Task.create(
            task_type=task_type,
            params=params,
            priority=priority,
            template_id=template_id,
            schedule_id=schedule_id,
            group_id=group_id,
            sequence_number=sequence_number,
            retry_of=retry_of,
        )

        # PersistenceAdapter handles position assignment
        return self.persistence.create_task(task)

    def enqueue_from_template(
        self,
        template_id: str,
        priority: int = 0,
        param_overrides: Optional[dict] = None,
        schedule_id: Optional[str] = None,
    ) -> Task:
        """
        Create and enqueue a task from a template.

        Args:
            template_id: Source template ID
            priority: Dispatch priority
            param_overrides: Override template default params
            schedule_id: Triggering schedule reference

        Returns:
            The created Task

        Raises:
            InvalidOperationError: If template not found
        """
        template = self.persistence.get_template(template_id)
        if template is None:
            raise InvalidOperationError(f"Template not found: {template_id}")

        # Merge params: template defaults + overrides
        params = {**template.default_params}
        if param_overrides:
            params.update(param_overrides)

        return self.enqueue(
            task_type=template.task_type,
            params=params,
            priority=priority,
            template_id=template_id,
            schedule_id=schedule_id,
        )

    # =========================================================================
    # Task Retrieval
    # =========================================================================

    def get_next(self) -> Optional[Task]:
        """
        Get the next task to dispatch, respecting TaskGroup constraints.

        From INV-004: priority DESC, position ASC, created_at ASC
        From DEC-012: TaskGroup sequential execution

        Note: This does NOT dispatch the task. The caller must use
        atomic_claim_task() to actually dispatch.

        For tasks in a TaskGroup, only returns the task if:
        - No other task in the group is RUNNING
        - No prior task in the group (by sequence_number) is QUEUED

        Returns:
            The next dispatchable QUEUED task, or None if queue is empty
        """
        return self.persistence.get_next_dispatchable_task()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.persistence.get_task(task_id)

    def list_queued(self, limit: int = 100) -> list[Task]:
        """
        List all queued tasks in dispatch order.

        Returns:
            Tasks ordered by (priority DESC, position ASC, created_at ASC)
        """
        return self.persistence.list_tasks_by_status(TaskStatus.QUEUED, limit=limit)

    def list_running(self, limit: int = 100) -> list[Task]:
        """List all currently running tasks."""
        return self.persistence.list_tasks_by_status(TaskStatus.RUNNING, limit=limit)

    def count_queued(self) -> int:
        """Get the count of queued tasks."""
        return self.persistence.count_tasks_by_status(TaskStatus.QUEUED)

    def count_running(self) -> int:
        """Get the count of running tasks."""
        return self.persistence.count_tasks_by_status(TaskStatus.RUNNING)

    # =========================================================================
    # Task Cancellation
    # =========================================================================

    def cancel(self, task_id: str) -> Task:
        """
        Cancel a queued task.

        From IMPLEMENTATION_PLAN.md:
        - QUEUED -> CANCELLED
        - RUNNING -> delegate to Executor (not handled here)

        Args:
            task_id: Task to cancel

        Returns:
            The cancelled Task

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidOperationError: If task is not QUEUED
        """
        task = self.persistence.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        if task.status != TaskStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot cancel task in {task.status.value} status from queue. "
                "RUNNING tasks must be cancelled through Executor."
            )

        now = datetime.utcnow().isoformat() + "Z"
        return self.persistence.update_task(
            task_id,
            status=TaskStatus.CANCELLED,
            finished_at=now,
        )

    # =========================================================================
    # Task Reordering
    # =========================================================================

    def update_priority(self, task_id: str, priority: int) -> Task:
        """
        Update a task's priority.

        Only allowed for QUEUED tasks.

        Args:
            task_id: Task to update
            priority: New priority value

        Returns:
            The updated Task
        """
        task = self.persistence.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        if task.status != TaskStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot update priority for task in {task.status.value} status"
            )

        return self.persistence.update_task(task_id, priority=priority)

    def reorder(self, task_id: str, new_position: int) -> Task:
        """
        Move a task to a new position within its priority level.

        Only allowed for QUEUED tasks.

        Args:
            task_id: Task to reorder
            new_position: New position value

        Returns:
            The updated Task
        """
        task = self.persistence.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        if task.status != TaskStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot reorder task in {task.status.value} status"
            )

        return self.persistence.update_task(task_id, position=new_position)

    # =========================================================================
    # Direct API Reservation (DEC-004)
    # =========================================================================

    def reserve_next_slot(
        self,
        reserved_by: str,
        expiry_minutes: int = DEFAULT_RESERVATION_EXPIRY_MINUTES,
    ) -> DirectReservation:
        """
        Reserve the next execution slot for Direct API.

        From DEC-004:
        - Direct APIs reserve the next execution slot
        - Queue dispatch is paused while reservation is active
        - Running task completes normally (no preemption)

        From PERSISTENCE_SCHEMA.md Section 2.5:
        - At most ONE reservation may be ACTIVE at any time
        - Expiration timeout prevents indefinite blocking

        Args:
            reserved_by: Identifier of the reserving process/request
            expiry_minutes: Timeout for stale reservations

        Returns:
            The created DirectReservation

        Raises:
            ReservationConflictError: If another reservation is active
        """
        expires_at = (
            datetime.utcnow() + timedelta(minutes=expiry_minutes)
        ).isoformat() + "Z"

        reservation = DirectReservation.create(
            reserved_by=reserved_by,
            expires_at=expires_at,
        )

        return self.persistence.create_reservation(reservation)

    def release_reservation(self, reservation_id: str) -> DirectReservation:
        """
        Release a reservation after direct execution completes.

        Args:
            reservation_id: Reservation to release

        Returns:
            The updated DirectReservation
        """
        return self.persistence.update_reservation_status(
            reservation_id,
            ReservationStatus.RELEASED,
        )

    def expire_reservation(self, reservation_id: str) -> DirectReservation:
        """
        Mark a reservation as expired (timeout or crash recovery).

        Args:
            reservation_id: Reservation to expire

        Returns:
            The updated DirectReservation
        """
        return self.persistence.update_reservation_status(
            reservation_id,
            ReservationStatus.EXPIRED,
        )

    def get_active_reservation(self) -> Optional[DirectReservation]:
        """
        Get the currently active reservation, if any.

        Used by Dispatcher to check if queue dispatch should be paused.

        Returns:
            The active reservation, or None if no reservation
        """
        return self.persistence.get_active_reservation()

    def has_active_reservation(self) -> bool:
        """Check if there's an active reservation blocking dispatch."""
        return self.get_active_reservation() is not None

    # =========================================================================
    # Queue State Queries
    # =========================================================================

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.count_queued() == 0

    def has_running_task(self) -> bool:
        """Check if any task is currently running."""
        return self.count_running() > 0

    def get_queue_position(self, task_id: str) -> Optional[int]:
        """
        Get a task's position in the queue.

        Returns:
            Position (1-indexed) or None if not found/not queued
        """
        task = self.persistence.get_task(task_id)
        if task is None or task.status != TaskStatus.QUEUED:
            return None

        queued = self.list_queued()
        for i, queued_task in enumerate(queued):
            if queued_task.task_id == task_id:
                return i + 1

        return None

    # =========================================================================
    # TaskGroup Operations (DEC-012)
    # =========================================================================

    def create_task_group(
        self,
        tasks: list[dict],
        name: Optional[str] = None,
        priority: int = 0,
    ) -> tuple[TaskGroup, list[Task]]:
        """
        Create a TaskGroup and enqueue its tasks.

        From DEC-012: Tasks in a group execute sequentially by default.

        Args:
            tasks: List of task specs, each with 'task_type' (or 'job_type' for
                   backward compat) and 'params'.
                   Tasks are assigned sequence_numbers 0, 1, 2, ... in order.
            name: Optional group name
            priority: Dispatch priority for all tasks in the group

        Returns:
            Tuple of (TaskGroup, list of created Tasks)

        Example:
            group, tasks = queue_manager.create_task_group([
                {"task_type": "story", "params": {"topic": "A"}},
                {"task_type": "story", "params": {"topic": "B"}},
            ], name="My Group")
        """
        # Create the group
        group = TaskGroup.create(name=name)
        group = self.persistence.create_task_group(group)

        # Update group status to QUEUED
        group = self.persistence.update_task_group(
            group.group_id,
            status=TaskGroupStatus.QUEUED,
        )

        # Create tasks with sequence numbers
        created_tasks = []
        for seq_num, task_spec in enumerate(tasks):
            # Support both 'task_type' and legacy 'job_type' keys
            task_type = task_spec.get("task_type") or task_spec.get("job_type")
            task = self.enqueue(
                task_type=task_type,
                params=task_spec.get("params", {}),
                priority=priority,
                template_id=task_spec.get("template_id"),
                group_id=group.group_id,
                sequence_number=seq_num,
            )
            created_tasks.append(task)

        return group, created_tasks

    def create_concurrent_group(
        self,
        task_ids: list[str],
        name: Optional[str] = None,
    ) -> tuple[TaskGroup, list[Task]]:
        """
        Create a concurrent TaskGroup from existing QUEUED tasks.

        Groups the given tasks into a new TaskGroup with execution_mode="concurrent",
        allowing them to execute simultaneously via ThreadPoolExecutor.

        Args:
            task_ids: List of existing QUEUED task IDs to group together
            name: Optional group name

        Returns:
            Tuple of (TaskGroup, list of updated Tasks)

        Raises:
            TaskNotFoundError: If any task_id does not exist
            InvalidOperationError: If any task is not QUEUED or already in a group
        """
        # Validate all tasks exist, are QUEUED, and are not already in a group
        tasks_to_group = []
        for task_id in task_ids:
            task = self.persistence.get_task(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            if task.status != TaskStatus.QUEUED:
                raise InvalidOperationError(
                    f"Cannot add task {task_id} to concurrent group: "
                    f"task is in {task.status.value} status (must be QUEUED)"
                )
            if task.group_id is not None:
                raise InvalidOperationError(
                    f"Cannot add task {task_id} to concurrent group: "
                    f"task already belongs to group {task.group_id}"
                )
            tasks_to_group.append(task)

        # Create the group with concurrent execution mode
        group = TaskGroup.create(name=name, execution_mode="concurrent")
        group = self.persistence.create_task_group(group)

        # Update group status to QUEUED
        group = self.persistence.update_task_group(
            group.group_id,
            status=TaskGroupStatus.QUEUED,
        )

        # Assign each task to the group with a sequence_number.
        # group_id and sequence_number are immutable-after-set fields not exposed
        # through update_task(), so we use a direct SQL update via the persistence
        # adapter's internal transaction context.
        updated_tasks = []
        with self.persistence._transaction() as conn:
            for seq_num, task in enumerate(tasks_to_group):
                conn.execute(
                    "UPDATE tasks SET group_id = ?, sequence_number = ? WHERE task_id = ?",
                    (group.group_id, seq_num, task.task_id),
                )

        # Re-read tasks to return updated state
        for task in tasks_to_group:
            updated_task = self.persistence.get_task(task.task_id)
            updated_tasks.append(updated_task)

        return group, updated_tasks

    def get_task_group(self, group_id: str) -> Optional[TaskGroup]:
        """Get a TaskGroup by ID."""
        return self.persistence.get_task_group(group_id)

    def get_tasks_in_group(self, group_id: str) -> list[Task]:
        """Get all tasks in a group, ordered by sequence_number."""
        return self.persistence.get_tasks_by_group(group_id)

    def cancel_task_group(self, group_id: str) -> TaskGroup:
        """
        Cancel all QUEUED tasks in a group.

        From DEC-012: Cancellation cancels remaining tasks.

        Args:
            group_id: Group to cancel

        Returns:
            The updated TaskGroup

        Note: RUNNING tasks are not cancelled (no preemption per DEC-004).
              They will complete normally, then the group status is updated.
        """
        tasks = self.persistence.get_tasks_by_group(group_id)

        for task in tasks:
            if task.status == TaskStatus.QUEUED:
                self.cancel(task.task_id)

        # Recompute and update group status
        new_status = self.persistence.compute_group_status(group_id)
        now = datetime.utcnow().isoformat() + "Z"

        group = self.persistence.update_task_group(
            group_id,
            status=new_status,
            finished_at=now if new_status.value in ("COMPLETED", "PARTIAL", "CANCELLED") else None,
        )

        return group

    def compute_group_status(self, group_id: str) -> TaskGroupStatus:
        """
        Compute a group's status from its member tasks.

        From INV-006: Group terminal status determined only when ALL tasks terminal.
        """
        return self.persistence.compute_group_status(group_id)

    def handle_group_task_completion(self, task: Task, task_run: TaskRun) -> None:
        """
        Handle task completion for group-related logic.

        From DEC-012: Stop-on-failure behavior
        - When a task in a group FAILS (after retry exhaustion)
        - Cancel remaining QUEUED tasks
        - Update group status

        This should be called after retry controller has processed the task.
        If a retry was created, this does nothing (task not truly failed yet).

        Args:
            task: The completed task
            task_run: The completed TaskRun
        """

        if task.group_id is None:
            return

        # Only process if task completed (has finished_at)
        if task.finished_at is None:
            return

        # Update group status based on all tasks
        group = self.persistence.get_task_group(task.group_id)
        if group is None:
            return

        # Compute current group status
        new_status = self.persistence.compute_group_status(task.group_id)
        now = datetime.utcnow().isoformat() + "Z"

        # If group is starting (first task running), mark started_at
        if group.started_at is None and new_status == TaskGroupStatus.RUNNING:
            self.persistence.update_task_group(
                task.group_id,
                status=new_status,
                started_at=now,
            )
            return

        # If task FAILED, check if we need stop-on-failure
        if task_run.status == TaskRunStatus.FAILED:
            # Check if a retry task was created for this task
            # If retry exists, the task isn't truly "failed" yet
            retry_task = self.persistence.get_retry_task_for(task.task_id)
            if retry_task is not None:
                # Retry pending, don't stop the group yet
                self.persistence.update_task_group(
                    task.group_id,
                    status=new_status,
                )
                return

            # No retry created - this is final failure
            # Cancel remaining QUEUED tasks (DEC-012 stop-on-failure)
            tasks_in_group = self.persistence.get_tasks_by_group(task.group_id)

            for group_task in tasks_in_group:
                if group_task.status == TaskStatus.QUEUED:
                    # Cancel the task
                    self.cancel(group_task.task_id)

                    # Create SKIPPED TaskRun for audit trail
                    skipped_run = TaskRun.create(
                        task_id=group_task.task_id,
                        params_snapshot=group_task.params,
                        template_id=group_task.template_id,
                    )
                    skipped_run.status = TaskRunStatus.SKIPPED
                    skipped_run.finished_at = now
                    skipped_run.error = "Skipped: predecessor task failed"
                    self.persistence.create_task_run(skipped_run)

            # Update group to PARTIAL
            self.persistence.update_task_group(
                task.group_id,
                status=TaskGroupStatus.PARTIAL,
                finished_at=now,
            )
            return

        # For COMPLETED tasks, check if group is now complete
        if new_status in (TaskGroupStatus.COMPLETED, TaskGroupStatus.PARTIAL, TaskGroupStatus.CANCELLED):
            self.persistence.update_task_group(
                task.group_id,
                status=new_status,
                finished_at=now,
            )
        else:
            # Still running or queued tasks
            self.persistence.update_task_group(
                task.group_id,
                status=new_status,
            )

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================

    # Task retrieval (old Job names)
    get_job = get_task
    has_running_job = has_running_task

    # TaskGroup operations (old JobGroup names)
    create_job_group = create_task_group
    get_job_group = get_task_group
    get_jobs_in_group = get_tasks_in_group
    cancel_job_group = cancel_task_group
    handle_group_job_completion = handle_group_task_completion
