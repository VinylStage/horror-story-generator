"""
Tests for scheduler state management singleton.

Verifies:
1. init_scheduler_service() creates singleton, idempotent on repeated calls
2. get_scheduler_service() returns instance or raises RuntimeError
3. shutdown_scheduler_service() stops scheduler, clears singleton, safe no-op
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import src.api._scheduler_state as scheduler_state_module


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MOCK_DB_PATH = Path("/tmp/test_scheduler.db")
MOCK_PROJECT_ROOT = Path("/tmp/project")
MOCK_LOGS_DIR = Path("/tmp/logs")
DEFAULT_POLL_INTERVAL = 1.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton before and after each test."""
    scheduler_state_module._scheduler_service = None
    yield
    scheduler_state_module._scheduler_service = None


@pytest.fixture()
def mock_service():
    """Create a mock SchedulerService instance."""
    svc = MagicMock()
    svc.is_running = False
    return svc


# ---------------------------------------------------------------------------
# init_scheduler_service
# ---------------------------------------------------------------------------
class TestInitSchedulerService:
    """Tests for init_scheduler_service()."""

    @patch("src.api._scheduler_state.SchedulerService")
    def test_creates_singleton_via_factory(self, mock_cls, mock_service):
        """Should call SchedulerService.create() with correct args."""
        mock_cls.create.return_value = mock_service

        result = scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
            poll_interval=2.5,
        )

        mock_cls.create.assert_called_once_with(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
            poll_interval=2.5,
        )
        assert result is mock_service

    @patch("src.api._scheduler_state.SchedulerService")
    def test_idempotent_returns_same_instance(self, mock_cls, mock_service):
        """Calling init twice should return the same singleton (no second create)."""
        mock_cls.create.return_value = mock_service

        first = scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )
        second = scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )

        assert first is second
        assert mock_cls.create.call_count == 1

    @patch("src.api._scheduler_state.SchedulerService")
    def test_default_poll_interval(self, mock_cls, mock_service):
        """Default poll_interval should be 1.0."""
        mock_cls.create.return_value = mock_service

        scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )

        mock_cls.create.assert_called_once_with(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
            poll_interval=DEFAULT_POLL_INTERVAL,
        )


# ---------------------------------------------------------------------------
# get_scheduler_service
# ---------------------------------------------------------------------------
class TestGetSchedulerService:
    """Tests for get_scheduler_service()."""

    def test_raises_runtime_error_before_init(self):
        """Should raise RuntimeError when called before init."""
        with pytest.raises(RuntimeError, match="Scheduler service not initialized"):
            scheduler_state_module.get_scheduler_service()

    @patch("src.api._scheduler_state.SchedulerService")
    def test_returns_initialized_instance(self, mock_cls, mock_service):
        """Should return the service after initialization."""
        mock_cls.create.return_value = mock_service

        scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )

        result = scheduler_state_module.get_scheduler_service()
        assert result is mock_service


# ---------------------------------------------------------------------------
# shutdown_scheduler_service
# ---------------------------------------------------------------------------
class TestShutdownSchedulerService:
    """Tests for shutdown_scheduler_service()."""

    def test_noop_when_not_initialized(self):
        """Should be a safe no-op when service is None."""
        # No exception should be raised
        scheduler_state_module.shutdown_scheduler_service()
        assert scheduler_state_module._scheduler_service is None

    @patch("src.api._scheduler_state.SchedulerService")
    def test_stops_running_scheduler_and_clears(self, mock_cls, mock_service):
        """Should stop a running scheduler and clear the singleton."""
        mock_service.is_running = True
        mock_cls.create.return_value = mock_service

        scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )

        scheduler_state_module.shutdown_scheduler_service()

        mock_service.stop.assert_called_once()
        assert scheduler_state_module._scheduler_service is None

    @patch("src.api._scheduler_state.SchedulerService")
    def test_clears_singleton_without_stop_if_not_running(self, mock_cls, mock_service):
        """Should clear singleton but not call stop() if scheduler not running."""
        mock_service.is_running = False
        mock_cls.create.return_value = mock_service

        scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )

        scheduler_state_module.shutdown_scheduler_service()

        mock_service.stop.assert_not_called()
        assert scheduler_state_module._scheduler_service is None

    @patch("src.api._scheduler_state.SchedulerService")
    def test_get_raises_after_shutdown(self, mock_cls, mock_service):
        """After shutdown, get_scheduler_service() should raise RuntimeError."""
        mock_cls.create.return_value = mock_service

        scheduler_state_module.init_scheduler_service(
            db_path=MOCK_DB_PATH,
            project_root=MOCK_PROJECT_ROOT,
            logs_dir=MOCK_LOGS_DIR,
        )
        scheduler_state_module.shutdown_scheduler_service()

        with pytest.raises(RuntimeError, match="Scheduler service not initialized"):
            scheduler_state_module.get_scheduler_service()
