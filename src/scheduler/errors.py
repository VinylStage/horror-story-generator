"""
Scheduler-specific exceptions.

These exceptions enforce invariants from DESIGN_GUARDS.md:
- INV-001: Job immutability after dispatch
- INV-002: JobRun immutability
- PERS-005: Reservation exclusivity
"""


class SchedulerError(Exception):
    """Base exception for all scheduler errors."""
    pass


class InvalidOperationError(SchedulerError):
    """
    Raised when an operation violates scheduler invariants.

    Examples:
    - Modifying Job.params after dispatch (INV-001)
    - Modifying immutable JobRun fields (INV-002)
    - Invalid state transitions
    """
    pass


class JobNotFoundError(SchedulerError):
    """Raised when a requested job does not exist."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")


class JobRunNotFoundError(SchedulerError):
    """Raised when a requested job run does not exist."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"JobRun not found: {run_id}")


class TemplateNotFoundError(SchedulerError):
    """Raised when a requested job template does not exist."""

    def __init__(self, template_id: str):
        self.template_id = template_id
        super().__init__(f"JobTemplate not found: {template_id}")


class ReservationConflictError(SchedulerError):
    """
    Raised when attempting to create a reservation while one is already active.

    Enforces PERS-005: Reservation Exclusivity.
    """

    def __init__(self, existing_reservation_id: str):
        self.existing_reservation_id = existing_reservation_id
        super().__init__(
            f"Cannot create reservation: another is already active ({existing_reservation_id})"
        )


class ReservationNotFoundError(SchedulerError):
    """Raised when a requested reservation does not exist."""

    def __init__(self, reservation_id: str):
        self.reservation_id = reservation_id
        super().__init__(f"Reservation not found: {reservation_id}")


class ConcurrencyViolationError(SchedulerError):
    """
    Raised when a concurrent modification is detected.

    Used for atomic claim operations where the job was already claimed
    by another process.
    """

    def __init__(self, job_id: str, expected_status: str, actual_status: str):
        self.job_id = job_id
        self.expected_status = expected_status
        self.actual_status = actual_status
        super().__init__(
            f"Concurrency violation for job {job_id}: "
            f"expected status '{expected_status}', got '{actual_status}'"
        )
