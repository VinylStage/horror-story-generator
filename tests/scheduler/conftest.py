"""
Scheduler Test Fixtures.

From TEST_STRATEGY.md Section 8.1:
Base fixtures:
  - Empty database
  - Mocked clock at fixed time
  - Clean queue state

Per-test fixtures:
  - Pre-populated jobs for ordering tests
  - Pre-populated RUNNING jobs for recovery tests
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
    Job,
    JobRun,
    JobTemplate,
    JobStatus,
    JobRunStatus,
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


class MockJobHandler:
    """
    Mock job handler for testing.

    Allows controlling execution outcome without subprocess.
    """

    def __init__(self):
        self.jobs_executed = []
        self._result = (JobRunStatus.COMPLETED, None, 0, [])
        self._cancelled = False

    def set_result(
        self,
        status: JobRunStatus,
        error: str = None,
        exit_code: int = 0,
        artifacts: list = None,
    ) -> None:
        """Set the result that execute() will return."""
        self._result = (status, error, exit_code, artifacts or [])

    def execute(self, job: Job, log_path: str = None):
        """Mock execute that returns configured result."""
        self.jobs_executed.append(job)
        return self._result

    def cancel(self) -> bool:
        self._cancelled = True
        return True


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
def mock_handler() -> MockJobHandler:
    """Create a mock job handler."""
    return MockJobHandler()


@pytest.fixture
def executor(persistence: PersistenceAdapter, mock_handler: MockJobHandler) -> Executor:
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
# Job Factory Fixtures
# =============================================================================


@pytest.fixture
def create_job(persistence: PersistenceAdapter) -> Callable:
    """
    Factory fixture for creating jobs.

    Returns a function that creates jobs with specified parameters.
    """

    def _create(
        job_type: str = "story",
        params: dict = None,
        priority: int = 0,
        status: JobStatus = JobStatus.QUEUED,
    ) -> Job:
        job = Job.create(
            job_type=job_type,
            params=params or {"test": True},
            priority=priority,
        )
        job = persistence.create_job(job)

        # If not QUEUED, update status
        if status != JobStatus.QUEUED:
            job = persistence.update_job(job.job_id, status=status)

        return job

    return _create


@pytest.fixture
def create_template(persistence: PersistenceAdapter) -> Callable:
    """Factory fixture for creating templates."""

    def _create(
        name: str = "test-template",
        job_type: str = "story",
        default_params: dict = None,
        retry_policy: dict = None,
    ) -> JobTemplate:
        template = JobTemplate.create(
            name=name,
            job_type=job_type,
            default_params=default_params or {"default": True},
            retry_policy=retry_policy or {"max_attempts": 3},
        )
        return persistence.create_template(template)

    return _create


@pytest.fixture
def create_job_run(persistence: PersistenceAdapter) -> Callable:
    """Factory fixture for creating job runs."""

    def _create(
        job_id: str,
        status: JobRunStatus = None,
        error: str = None,
    ) -> JobRun:
        job = persistence.get_job(job_id)
        job_run = JobRun.create(
            job_id=job_id,
            params_snapshot=job.params if job else {},
            template_id=job.template_id if job else None,
        )
        job_run = persistence.create_job_run(job_run)

        if status:
            job_run = persistence.update_job_run(
                job_run.run_id,
                status=status,
                finished_at=datetime.utcnow().isoformat() + "Z",
                error=error,
            )

        return job_run

    return _create


# =============================================================================
# Assertion Helpers (from TEST_STRATEGY.md Section 8.2)
# =============================================================================


def assert_job_status(persistence: PersistenceAdapter, job_id: str, expected: JobStatus):
    """Assert a job has the expected status."""
    job = persistence.get_job(job_id)
    assert job is not None, f"Job {job_id} not found"
    assert job.status == expected, f"Expected {expected}, got {job.status}"


def assert_jobrun_status(persistence: PersistenceAdapter, run_id: str, expected: JobRunStatus):
    """Assert a job run has the expected status."""
    run = persistence.get_job_run(run_id)
    assert run is not None, f"JobRun {run_id} not found"
    assert run.status == expected, f"Expected {expected}, got {run.status}"


def assert_queue_order(persistence: PersistenceAdapter, expected_job_ids: list):
    """Assert the queue contains jobs in expected order."""
    queued = persistence.list_jobs_by_status(JobStatus.QUEUED)
    actual_ids = [j.job_id for j in queued]
    assert actual_ids == expected_job_ids, f"Expected order {expected_job_ids}, got {actual_ids}"


def assert_retry_chain_length(persistence: PersistenceAdapter, job_id: str, expected: int):
    """Assert the retry chain has expected length."""
    actual = persistence.count_retry_chain(job_id)
    assert actual == expected, f"Expected chain length {expected}, got {actual}"
