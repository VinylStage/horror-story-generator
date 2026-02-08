"""
Scheduler-specific exceptions.

These exceptions enforce invariants from DESIGN_GUARDS.md:
- INV-001: Task immutability after dispatch
- INV-002: TaskRun immutability
- PERS-005: Reservation exclusivity
"""


class SchedulerError(Exception):
    """Base exception for all scheduler errors."""
    pass


class InvalidOperationError(SchedulerError):
    """
    Raised when an operation violates scheduler invariants.

    Examples:
    - Modifying Task.params after dispatch (INV-001)
    - Modifying immutable TaskRun fields (INV-002)
    - Invalid state transitions
    """
    pass


class TaskNotFoundError(SchedulerError):
    """Raised when a requested task does not exist."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskRunNotFoundError(SchedulerError):
    """Raised when a requested task run does not exist."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"TaskRun not found: {run_id}")


class TemplateNotFoundError(SchedulerError):
    """Raised when a requested task template does not exist."""

    def __init__(self, template_id: str):
        self.template_id = template_id
        super().__init__(f"TaskTemplate not found: {template_id}")


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

    Used for atomic claim operations where the task was already claimed
    by another process.
    """

    def __init__(self, task_id: str, expected_status: str, actual_status: str):
        self.task_id = task_id
        self.expected_status = expected_status
        self.actual_status = actual_status
        super().__init__(
            f"Concurrency violation for task {task_id}: "
            f"expected status '{expected_status}', got '{actual_status}'"
        )


# Backward compatibility aliases
JobNotFoundError = TaskNotFoundError
JobRunNotFoundError = TaskRunNotFoundError
