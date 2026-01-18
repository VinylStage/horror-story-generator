"""
Job Scheduler Core Module.

Phase 4 Implementation following design documents:
- DOMAIN_MODEL.md
- PERSISTENCE_SCHEMA.md
- DESIGN_GUARDS.md (DEC-004 ~ DEC-012)
- API_CONTRACT.md
"""

from .entities import (
    JobStatus,
    JobRunStatus,
    JobGroupStatus,
    Job,
    JobRun,
    JobTemplate,
    Schedule,
    DirectReservation,
    ReservationStatus,
    JobGroup,
)
from .errors import (
    SchedulerError,
    InvalidOperationError,
    JobNotFoundError,
    JobRunNotFoundError,
    TemplateNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
    ConcurrencyViolationError,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager
from .dispatcher import Dispatcher, DispatcherState
from .executor import Executor, JobHandler, SubprocessJobHandler, SkipExecutor
from .retry_controller import RetryController
from .recovery import RecoveryManager
from .service import SchedulerService

__all__ = [
    # Entities
    "JobStatus",
    "JobRunStatus",
    "JobGroupStatus",
    "Job",
    "JobRun",
    "JobGroup",
    "JobTemplate",
    "Schedule",
    "DirectReservation",
    "ReservationStatus",
    # Errors
    "SchedulerError",
    "InvalidOperationError",
    "JobNotFoundError",
    "JobRunNotFoundError",
    "TemplateNotFoundError",
    "ReservationConflictError",
    "ReservationNotFoundError",
    "ConcurrencyViolationError",
    # Persistence
    "PersistenceAdapter",
    # Queue
    "QueueManager",
    # Dispatcher
    "Dispatcher",
    "DispatcherState",
    # Executor
    "Executor",
    "JobHandler",
    "SubprocessJobHandler",
    "SkipExecutor",
    # Retry
    "RetryController",
    # Recovery
    "RecoveryManager",
    # Service
    "SchedulerService",
]
