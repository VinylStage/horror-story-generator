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
    Job,
    JobRun,
    JobTemplate,
    Schedule,
    DirectReservation,
    ReservationStatus,
)
from .errors import (
    SchedulerError,
    InvalidOperationError,
    JobNotFoundError,
    JobRunNotFoundError,
    ReservationConflictError,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager
from .dispatcher import Dispatcher, DispatcherState

__all__ = [
    # Entities
    "JobStatus",
    "JobRunStatus",
    "Job",
    "JobRun",
    "JobTemplate",
    "Schedule",
    "DirectReservation",
    "ReservationStatus",
    # Errors
    "SchedulerError",
    "InvalidOperationError",
    "JobNotFoundError",
    "JobRunNotFoundError",
    "ReservationConflictError",
    # Persistence
    "PersistenceAdapter",
    # Queue
    "QueueManager",
    # Dispatcher
    "Dispatcher",
    "DispatcherState",
]
