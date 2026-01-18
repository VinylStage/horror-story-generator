"""
Queue Manager for Job Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.1:
- Maintains the ordered queue of QUEUED jobs
- Provides insertion, cancellation, reordering
- Supports Direct API next-slot reservation (DEC-004)

What QueueManager MUST NOT do:
- Execute jobs (Executor's responsibility)
- Create JobRuns (Executor's responsibility)
- Manage retry logic (RetryController's responsibility)
- Interact with external APIs or webhooks
"""

from datetime import datetime, timedelta
from typing import Optional

from .entities import (
    Job,
    JobStatus,
    DirectReservation,
    ReservationStatus,
)
from .errors import (
    InvalidOperationError,
    JobNotFoundError,
    ReservationConflictError,
)
from .persistence import PersistenceAdapter


# Default reservation expiry (from PERSISTENCE_SCHEMA.md Section 2.5)
DEFAULT_RESERVATION_EXPIRY_MINUTES = 10


class QueueManager:
    """
    Manages the job queue with priority-based ordering.

    Key behaviors:
    - Insertion: Assign position using gap strategy
    - Ordering: priority DESC, position ASC, created_at ASC (INV-004)
    - Cancellation: QUEUED → CANCELLED only
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
    # Job Insertion
    # =========================================================================

    def enqueue(
        self,
        job_type: str,
        params: dict,
        priority: int = 0,
        template_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        group_id: Optional[str] = None,
        retry_of: Optional[str] = None,
    ) -> Job:
        """
        Add a new job to the queue.

        From IMPLEMENTATION_PLAN.md:
        Job added → assign position → persist to SQLite → status = QUEUED

        Args:
            job_type: Type of work ("story" or "research")
            params: Execution parameters
            priority: Dispatch priority (higher = sooner)
            template_id: Source template reference
            schedule_id: Triggering schedule reference
            group_id: JobGroup membership
            retry_of: Previous job in retry chain

        Returns:
            The created Job with assigned position
        """
        job = Job.create(
            job_type=job_type,
            params=params,
            priority=priority,
            template_id=template_id,
            schedule_id=schedule_id,
            group_id=group_id,
            retry_of=retry_of,
        )

        # PersistenceAdapter handles position assignment
        return self.persistence.create_job(job)

    def enqueue_from_template(
        self,
        template_id: str,
        priority: int = 0,
        param_overrides: Optional[dict] = None,
        schedule_id: Optional[str] = None,
    ) -> Job:
        """
        Create and enqueue a job from a template.

        Args:
            template_id: Source template ID
            priority: Dispatch priority
            param_overrides: Override template default params
            schedule_id: Triggering schedule reference

        Returns:
            The created Job

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
            job_type=template.job_type,
            params=params,
            priority=priority,
            template_id=template_id,
            schedule_id=schedule_id,
        )

    # =========================================================================
    # Job Retrieval
    # =========================================================================

    def get_next(self) -> Optional[Job]:
        """
        Get the next job to dispatch.

        From INV-004: priority DESC, position ASC, created_at ASC

        Note: This does NOT dispatch the job. The caller must use
        atomic_claim_job() to actually dispatch.

        Returns:
            The next QUEUED job, or None if queue is empty
        """
        return self.persistence.get_next_queued_job()

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.persistence.get_job(job_id)

    def list_queued(self, limit: int = 100) -> list[Job]:
        """
        List all queued jobs in dispatch order.

        Returns:
            Jobs ordered by (priority DESC, position ASC, created_at ASC)
        """
        return self.persistence.list_jobs_by_status(JobStatus.QUEUED, limit=limit)

    def list_running(self, limit: int = 100) -> list[Job]:
        """List all currently running jobs."""
        return self.persistence.list_jobs_by_status(JobStatus.RUNNING, limit=limit)

    def count_queued(self) -> int:
        """Get the count of queued jobs."""
        return self.persistence.count_jobs_by_status(JobStatus.QUEUED)

    def count_running(self) -> int:
        """Get the count of running jobs."""
        return self.persistence.count_jobs_by_status(JobStatus.RUNNING)

    # =========================================================================
    # Job Cancellation
    # =========================================================================

    def cancel(self, job_id: str) -> Job:
        """
        Cancel a queued job.

        From IMPLEMENTATION_PLAN.md:
        - QUEUED → CANCELLED
        - RUNNING → delegate to Executor (not handled here)

        Args:
            job_id: Job to cancel

        Returns:
            The cancelled Job

        Raises:
            JobNotFoundError: If job doesn't exist
            InvalidOperationError: If job is not QUEUED
        """
        job = self.persistence.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        if job.status != JobStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot cancel job in {job.status.value} status from queue. "
                "RUNNING jobs must be cancelled through Executor."
            )

        now = datetime.utcnow().isoformat() + "Z"
        return self.persistence.update_job(
            job_id,
            status=JobStatus.CANCELLED,
            finished_at=now,
        )

    # =========================================================================
    # Job Reordering
    # =========================================================================

    def update_priority(self, job_id: str, priority: int) -> Job:
        """
        Update a job's priority.

        Only allowed for QUEUED jobs.

        Args:
            job_id: Job to update
            priority: New priority value

        Returns:
            The updated Job
        """
        job = self.persistence.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        if job.status != JobStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot update priority for job in {job.status.value} status"
            )

        return self.persistence.update_job(job_id, priority=priority)

    def reorder(self, job_id: str, new_position: int) -> Job:
        """
        Move a job to a new position within its priority level.

        Only allowed for QUEUED jobs.

        Args:
            job_id: Job to reorder
            new_position: New position value

        Returns:
            The updated Job
        """
        job = self.persistence.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        if job.status != JobStatus.QUEUED:
            raise InvalidOperationError(
                f"Cannot reorder job in {job.status.value} status"
            )

        return self.persistence.update_job(job_id, position=new_position)

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
        - Running job completes normally (no preemption)

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

    def has_running_job(self) -> bool:
        """Check if any job is currently running."""
        return self.count_running() > 0

    def get_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get a job's position in the queue.

        Returns:
            Position (1-indexed) or None if not found/not queued
        """
        job = self.persistence.get_job(job_id)
        if job is None or job.status != JobStatus.QUEUED:
            return None

        queued = self.list_queued()
        for i, queued_job in enumerate(queued):
            if queued_job.job_id == job_id:
                return i + 1

        return None
