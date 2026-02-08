"""
Task Scheduler Core Module.

Phase 4 Implementation following design documents:
- DOMAIN_MODEL.md
- PERSISTENCE_SCHEMA.md
- DESIGN_GUARDS.md (DEC-004 ~ DEC-012)
- API_CONTRACT.md
"""

from .entities import (
    TaskStatus,
    TaskRunStatus,
    TaskGroupStatus,
    Task,
    TaskRun,
    TaskTemplate,
    Schedule,
    DirectReservation,
    ReservationStatus,
    TaskGroup,
    # Backward compatibility aliases
    JobStatus,
    JobRunStatus,
    JobGroupStatus,
    Job,
    JobRun,
    JobTemplate,
    JobGroup,
)
from .errors import (
    SchedulerError,
    InvalidOperationError,
    TaskNotFoundError,
    TaskRunNotFoundError,
    TemplateNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
    ConcurrencyViolationError,
    # Backward compatibility aliases
    JobNotFoundError,
    JobRunNotFoundError,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager
from .dispatcher import Dispatcher, DispatcherState
from .executor import Executor, TaskHandler, SubprocessTaskHandler, SkipExecutor, JobHandler, SubprocessJobHandler
from .retry_controller import RetryController
from .recovery import RecoveryManager
from .service import SchedulerService

__all__ = [
    # Entities (new names)
    "TaskStatus",
    "TaskRunStatus",
    "TaskGroupStatus",
    "Task",
    "TaskRun",
    "TaskGroup",
    "TaskTemplate",
    "Schedule",
    "DirectReservation",
    "ReservationStatus",
    # Entities (backward compatibility)
    "JobStatus",
    "JobRunStatus",
    "JobGroupStatus",
    "Job",
    "JobRun",
    "JobGroup",
    "JobTemplate",
    # Errors (new names)
    "SchedulerError",
    "InvalidOperationError",
    "TaskNotFoundError",
    "TaskRunNotFoundError",
    "TemplateNotFoundError",
    "ReservationConflictError",
    "ReservationNotFoundError",
    "ConcurrencyViolationError",
    # Errors (backward compatibility)
    "JobNotFoundError",
    "JobRunNotFoundError",
    # Persistence
    "PersistenceAdapter",
    # Queue
    "QueueManager",
    # Dispatcher
    "Dispatcher",
    "DispatcherState",
    # Executor (new names)
    "Executor",
    "TaskHandler",
    "SubprocessTaskHandler",
    "SkipExecutor",
    # Executor (backward compatibility)
    "JobHandler",
    "SubprocessJobHandler",
    # Retry
    "RetryController",
    # Recovery
    "RecoveryManager",
    # Service
    "SchedulerService",
]
