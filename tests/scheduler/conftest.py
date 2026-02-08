"""
Scheduler Test Fixtures.

From TEST_STRATEGY.md Section 8.1:
Base fixtures:
  - Empty database
  - Mocked clock at fixed time
  - Clean queue state

Per-test fixtures:
  - Pre-populated tasks for ordering tests
  - Pre-populated RUNNING tasks for recovery tests
  - Pre-created reservations for exclusivity tests
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Callable
from unittest.mock import MagicMock

from src.scheduler import (
    PersistenceAdapter,
    QueueManager,
    Dispatcher,
    Executor,
    RetryController,
    Task,
    TaskRun,
    TaskTemplate,
    TaskStatus,
    TaskRunStatus,
)
from src.scheduler.recovery import RecoveryManager
from src.scheduler.service import SchedulerService


# Fixed time for deterministic tests (TEST_STRATEGY.md Section 1.3)
FIXED_TIME = "2026-01-01T00:00:00Z"
FIXED_DATETIME = datetime(2026, 1, 1, 0, 0, 0)


class MockClock:
    """
    Mock clock for deterministic time control.

    From TEST_STRATEGY.md Section 1.3:
    - Starts at fixed epoch
    - Advances only when explicitly ticked
    """

    def __init__(self, start_time: datetime = FIXED_DATETIME):
        self._current = start_time

    def now(self) -> datetime:
        return self._current

    def now_iso(self) -> str:
        return self._current.isoformat() + "Z"

    def tick(self, seconds: int = 1) -> None:
        """Advance time by specified seconds."""
        self._current += timedelta(seconds=seconds)

    def set(self, time: datetime) -> None:
        """Set time to specific value."""
        self._current = time


class MockTaskHandler:
    """
    Mock task handler for testing.

    Allows controlling execution outcome without subprocess.
    """

    def __init__(self):
        self.tasks_executed = []
        self._result = (TaskRunStatus.COMPLETED, None, 0, [])
        self._cancelled = False

    def set_result(
        self,
        status: TaskRunStatus,
        error: str = None,
        exit_code: int = 0,
        artifacts: list = None,
    ) -> None:
        """Set the result that execute() will return."""
        self._result = (status, error, exit_code, artifacts or [])

    def execute(self, task: Task, log_path: str = None):
        """Mock execute that returns configured result."""
        self.tasks_executed.append(task)
        return self._result

    def cancel(self) -> bool:
        self._cancelled = True
        return True


# Backward compatibility alias
MockJobHandler = MockTaskHandler


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)
    # Also cleanup WAL and SHM files
    Path(f"{db_path}-wal").unlink(missing_ok=True)
    Path(f"{db_path}-shm").unlink(missing_ok=True)


@pytest.fixture
def persistence(temp_db_path: str) -> PersistenceAdapter:
    """Create a fresh PersistenceAdapter with empty database."""
    return PersistenceAdapter(temp_db_path)


@pytest.fixture
def in_memory_persistence() -> PersistenceAdapter:
    """Create an in-memory PersistenceAdapter for fast tests."""
    return PersistenceAdapter(":memory:")


# =============================================================================
# Component Fixtures
# =============================================================================


@pytest.fixture
def queue_manager(persistence: PersistenceAdapter) -> QueueManager:
    """Create a QueueManager with the test database."""
    return QueueManager(persistence)


@pytest.fixture
def mock_handler() -> MockTaskHandler:
    """Create a mock task handler."""
    return MockTaskHandler()


@pytest.fixture
def executor(persistence: PersistenceAdapter, mock_handler: MockTaskHandler) -> Executor:
    """Create an Executor with mock handler."""
    exec = Executor(persistence)
    exec.set_handler(mock_handler)
    return exec


@pytest.fixture
def dispatcher(
    persistence: PersistenceAdapter,
    queue_manager: QueueManager,
    executor: Executor,
) -> Dispatcher:
    """Create a Dispatcher with all dependencies."""
    disp = Dispatcher(
        persistence=persistence,
        queue_manager=queue_manager,
        poll_interval=0.1,  # Fast polling for tests
    )
    disp.set_executor(executor)
    return disp


@pytest.fixture
def retry_controller(
    persistence: PersistenceAdapter,
    queue_manager: QueueManager,
) -> RetryController:
    """Create a RetryController."""
    return RetryController(persistence, queue_manager)


@pytest.fixture
def recovery_manager(
    persistence: PersistenceAdapter,
    queue_manager: QueueManager,
    retry_controller: RetryController,
) -> RecoveryManager:
    """Create a RecoveryManager."""
    return RecoveryManager(persistence, queue_manager, retry_controller)


@pytest.fixture
def mock_clock() -> MockClock:
    """Create a mock clock at fixed time."""
    return MockClock()


# =============================================================================
# Task Factory Fixtures
# =============================================================================


@pytest.fixture
def create_task(persistence: PersistenceAdapter) -> Callable:
    """
    Factory fixture for creating tasks.

    Returns a function that creates tasks with specified parameters.
    """

    def _create(
        task_type: str = "story",
        params: dict = None,
        priority: int = 0,
        status: TaskStatus = TaskStatus.QUEUED,
    ) -> Task:
        task = Task.create(
            task_type=task_type,
            params=params or {"test": True},
            priority=priority,
        )
        task = persistence.create_task(task)

        # If not QUEUED, update status
        if status != TaskStatus.QUEUED:
            task = persistence.update_task(task.task_id, status=status)

        return task

    return _create


# Backward compatibility alias
create_job = create_task


@pytest.fixture
def create_template(persistence: PersistenceAdapter) -> Callable:
    """Factory fixture for creating templates."""

    def _create(
        name: str = "test-template",
        task_type: str = "story",
        default_params: dict = None,
        retry_policy: dict = None,
    ) -> TaskTemplate:
        template = TaskTemplate.create(
            name=name,
            task_type=task_type,
            default_params=default_params or {"default": True},
            retry_policy=retry_policy or {"max_attempts": 3},
        )
        return persistence.create_template(template)

    return _create


@pytest.fixture
def create_task_run(persistence: PersistenceAdapter) -> Callable:
    """Factory fixture for creating task runs."""

    def _create(
        task_id: str,
        status: TaskRunStatus = None,
        error: str = None,
    ) -> TaskRun:
        task = persistence.get_task(task_id)
        task_run = TaskRun.create(
            task_id=task_id,
            params_snapshot=task.params if task else {},
            template_id=task.template_id if task else None,
        )
        task_run = persistence.create_task_run(task_run)

        if status:
            task_run = persistence.update_task_run(
                task_run.run_id,
                status=status,
                finished_at=datetime.utcnow().isoformat() + "Z",
                error=error,
            )

        return task_run

    return _create


# Backward compatibility alias
create_job_run = create_task_run


# =============================================================================
# Assertion Helpers (from TEST_STRATEGY.md Section 8.2)
# =============================================================================


def assert_task_status(persistence: PersistenceAdapter, task_id: str, expected: TaskStatus):
    """Assert a task has the expected status."""
    task = persistence.get_task(task_id)
    assert task is not None, f"Task {task_id} not found"
    assert task.status == expected, f"Expected {expected}, got {task.status}"


# Backward compatibility alias
assert_job_status = assert_task_status


def assert_taskrun_status(persistence: PersistenceAdapter, run_id: str, expected: TaskRunStatus):
    """Assert a task run has the expected status."""
    run = persistence.get_task_run(run_id)
    assert run is not None, f"TaskRun {run_id} not found"
    assert run.status == expected, f"Expected {expected}, got {run.status}"


# Backward compatibility alias
assert_jobrun_status = assert_taskrun_status


def assert_queue_order(persistence: PersistenceAdapter, expected_task_ids: list):
    """Assert the queue contains tasks in expected order."""
    queued = persistence.list_tasks_by_status(TaskStatus.QUEUED)
    actual_ids = [t.task_id for t in queued]
    assert actual_ids == expected_task_ids, f"Expected order {expected_task_ids}, got {actual_ids}"


def assert_retry_chain_length(persistence: PersistenceAdapter, task_id: str, expected: int):
    """Assert the retry chain has expected length."""
    actual = persistence.count_retry_chain(task_id)
    assert actual == expected, f"Expected chain length {expected}, got {actual}"
