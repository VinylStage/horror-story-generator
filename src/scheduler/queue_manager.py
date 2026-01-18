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
    JobRun,
    JobGroup,
    JobStatus,
    JobRunStatus,
    JobGroupStatus,
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
        sequence_number: Optional[int] = None,
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
            sequence_number: Order within JobGroup (0-indexed)
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
            sequence_number=sequence_number,
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
        Get the next job to dispatch, respecting JobGroup constraints.

        From INV-004: priority DESC, position ASC, created_at ASC
        From DEC-012: JobGroup sequential execution

        Note: This does NOT dispatch the job. The caller must use
        atomic_claim_job() to actually dispatch.

        For jobs in a JobGroup, only returns the job if:
        - No other job in the group is RUNNING
        - No prior job in the group (by sequence_number) is QUEUED

        Returns:
            The next dispatchable QUEUED job, or None if queue is empty
        """
        return self.persistence.get_next_dispatchable_job()

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

    # =========================================================================
    # JobGroup Operations (DEC-012)
    # =========================================================================

    def create_job_group(
        self,
        jobs: list[dict],
        name: Optional[str] = None,
        priority: int = 0,
    ) -> tuple[JobGroup, list[Job]]:
        """
        Create a JobGroup and enqueue its jobs.

        From DEC-012: Jobs in a group execute sequentially.

        Args:
            jobs: List of job specs, each with 'job_type' and 'params'.
                  Jobs are assigned sequence_numbers 0, 1, 2, ... in order.
            name: Optional group name
            priority: Dispatch priority for all jobs in the group

        Returns:
            Tuple of (JobGroup, list of created Jobs)

        Example:
            group, jobs = queue_manager.create_job_group([
                {"job_type": "story", "params": {"topic": "A"}},
                {"job_type": "story", "params": {"topic": "B"}},
            ], name="My Group")
        """
        # Create the group
        group = JobGroup.create(name=name)
        group = self.persistence.create_job_group(group)

        # Update group status to QUEUED
        group = self.persistence.update_job_group(
            group.group_id,
            status=JobGroupStatus.QUEUED,
        )

        # Create jobs with sequence numbers
        created_jobs = []
        for seq_num, job_spec in enumerate(jobs):
            job = self.enqueue(
                job_type=job_spec["job_type"],
                params=job_spec.get("params", {}),
                priority=priority,
                template_id=job_spec.get("template_id"),
                group_id=group.group_id,
                sequence_number=seq_num,
            )
            created_jobs.append(job)

        return group, created_jobs

    def get_job_group(self, group_id: str) -> Optional[JobGroup]:
        """Get a JobGroup by ID."""
        return self.persistence.get_job_group(group_id)

    def get_jobs_in_group(self, group_id: str) -> list[Job]:
        """Get all jobs in a group, ordered by sequence_number."""
        return self.persistence.get_jobs_by_group(group_id)

    def cancel_job_group(self, group_id: str) -> JobGroup:
        """
        Cancel all QUEUED jobs in a group.

        From DEC-012: Cancellation cancels remaining jobs.

        Args:
            group_id: Group to cancel

        Returns:
            The updated JobGroup

        Note: RUNNING jobs are not cancelled (no preemption per DEC-004).
              They will complete normally, then the group status is updated.
        """
        jobs = self.persistence.get_jobs_by_group(group_id)

        for job in jobs:
            if job.status == JobStatus.QUEUED:
                self.cancel(job.job_id)

        # Recompute and update group status
        new_status = self.persistence.compute_group_status(group_id)
        now = datetime.utcnow().isoformat() + "Z"

        group = self.persistence.update_job_group(
            group_id,
            status=new_status,
            finished_at=now if new_status.value in ("COMPLETED", "PARTIAL", "CANCELLED") else None,
        )

        return group

    def compute_group_status(self, group_id: str) -> JobGroupStatus:
        """
        Compute a group's status from its member jobs.

        From INV-006: Group terminal status determined only when ALL jobs terminal.
        """
        return self.persistence.compute_group_status(group_id)

    def handle_group_job_completion(self, job: Job, job_run: JobRun) -> None:
        """
        Handle job completion for group-related logic.

        From DEC-012: Stop-on-failure behavior
        - When a job in a group FAILS (after retry exhaustion)
        - Cancel remaining QUEUED jobs
        - Update group status

        This should be called after retry controller has processed the job.
        If a retry was created, this does nothing (job not truly failed yet).

        Args:
            job: The completed job
            job_run: The completed JobRun
        """

        if job.group_id is None:
            return

        # Only process if job completed (has finished_at)
        if job.finished_at is None:
            return

        # Update group status based on all jobs
        group = self.persistence.get_job_group(job.group_id)
        if group is None:
            return

        # Compute current group status
        new_status = self.persistence.compute_group_status(job.group_id)
        now = datetime.utcnow().isoformat() + "Z"

        # If group is starting (first job running), mark started_at
        if group.started_at is None and new_status == JobGroupStatus.RUNNING:
            self.persistence.update_job_group(
                job.group_id,
                status=new_status,
                started_at=now,
            )
            return

        # If job FAILED, check if we need stop-on-failure
        if job_run.status == JobRunStatus.FAILED:
            # Check if a retry job was created for this job
            # If retry exists, the job isn't truly "failed" yet
            retry_job = self.persistence.get_retry_job_for(job.job_id)
            if retry_job is not None:
                # Retry pending, don't stop the group yet
                self.persistence.update_job_group(
                    job.group_id,
                    status=new_status,
                )
                return

            # No retry created - this is final failure
            # Cancel remaining QUEUED jobs (DEC-012 stop-on-failure)
            jobs_in_group = self.persistence.get_jobs_by_group(job.group_id)

            for group_job in jobs_in_group:
                if group_job.status == JobStatus.QUEUED:
                    # Cancel the job
                    self.cancel(group_job.job_id)

                    # Create SKIPPED JobRun for audit trail
                    skipped_run = JobRun.create(
                        job_id=group_job.job_id,
                        params_snapshot=group_job.params,
                        template_id=group_job.template_id,
                    )
                    skipped_run.status = JobRunStatus.SKIPPED
                    skipped_run.finished_at = now
                    skipped_run.error = "Skipped: predecessor job failed"
                    self.persistence.create_job_run(skipped_run)

            # Update group to PARTIAL
            self.persistence.update_job_group(
                job.group_id,
                status=JobGroupStatus.PARTIAL,
                finished_at=now,
            )
            return

        # For COMPLETED jobs, check if group is now complete
        if new_status in (JobGroupStatus.COMPLETED, JobGroupStatus.PARTIAL, JobGroupStatus.CANCELLED):
            self.persistence.update_job_group(
                job.group_id,
                status=new_status,
                finished_at=now,
            )
        else:
            # Still running or queued jobs
            self.persistence.update_job_group(
                job.group_id,
                status=new_status,
            )
