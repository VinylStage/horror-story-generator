"""
Tests for the scheduler router (/scheduler/*).

Verifies:
1. POST /scheduler/start: already running, fresh start, error handling
2. POST /scheduler/stop: already stopped, running stop, error handling
3. GET /scheduler/status: normal response, error handling
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from src.api.routers.scheduler import router


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
START_URL = "/scheduler/start"
STOP_URL = "/scheduler/stop"
STATUS_URL = "/scheduler/status"

SAMPLE_STATUS = {
    "scheduler_running": True,
    "current_task_id": "task-42",
    "queue_length": 5,
    "cumulative_stats": {
        "total_executed": 100,
        "succeeded": 90,
        "failed": 5,
        "cancelled": 3,
        "skipped": 2,
    },
    "has_active_reservation": False,
}

RECOVERY_STATS = {"recovered": 2, "failed": 0}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_service():
    """Create a mock SchedulerService."""
    svc = MagicMock()
    type(svc).is_running = PropertyMock(return_value=False)
    svc.start.return_value = RECOVERY_STATS
    svc.get_scheduler_status.return_value = SAMPLE_STATUS
    return svc


@pytest.fixture()
def app():
    """Create a minimal FastAPI app with the scheduler router."""
    _app = FastAPI()
    _app.include_router(router, prefix="/scheduler")
    return _app


@pytest.fixture()
async def client(app):
    """Async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /scheduler/start
# ---------------------------------------------------------------------------
class TestStartScheduler:
    """Tests for the start_scheduler endpoint."""

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_already_running(self, mock_get, mock_service, client):
        """If already running, should return success with 'already running' message."""
        type(mock_service).is_running = PropertyMock(return_value=True)
        mock_get.return_value = mock_service

        resp = await client.post(START_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "already running" in body["message"].lower()
        assert body["recovery_stats"] is None
        mock_service.start.assert_not_called()

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_start_success(self, mock_get, mock_service, client):
        """Should start scheduler and return recovery stats."""
        type(mock_service).is_running = PropertyMock(return_value=False)
        mock_get.return_value = mock_service

        resp = await client.post(START_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "started successfully" in body["message"].lower()
        assert body["recovery_stats"] == RECOVERY_STATS
        mock_service.start.assert_called_once_with(
            run_recovery=True, blocking=False,
        )

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_start_with_no_recovery(self, mock_get, mock_service, client):
        """Should pass run_recovery=False when requested."""
        type(mock_service).is_running = PropertyMock(return_value=False)
        mock_get.return_value = mock_service

        resp = await client.post(START_URL, json={"run_recovery": False})

        assert resp.status_code == 200
        mock_service.start.assert_called_once_with(
            run_recovery=False, blocking=False,
        )

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_start_empty_recovery_stats(self, mock_get, mock_service, client):
        """Empty recovery stats dict should be returned as None."""
        type(mock_service).is_running = PropertyMock(return_value=False)
        mock_service.start.return_value = {}
        mock_get.return_value = mock_service

        resp = await client.post(START_URL)

        assert resp.status_code == 200
        body = resp.json()
        # Empty dict is falsy, so recovery_stats should be None
        assert body["recovery_stats"] is None

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_start_error_returns_500(self, mock_get, mock_service, client):
        """Service exception should result in 500."""
        type(mock_service).is_running = PropertyMock(return_value=False)
        mock_service.start.side_effect = RuntimeError("DB locked")
        mock_get.return_value = mock_service

        resp = await client.post(START_URL)

        assert resp.status_code == 500
        assert "Failed to start scheduler" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /scheduler/stop
# ---------------------------------------------------------------------------
class TestStopScheduler:
    """Tests for the stop_scheduler endpoint."""

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_already_stopped(self, mock_get, mock_service, client):
        """If not running, should return success with 'already stopped'."""
        type(mock_service).is_running = PropertyMock(return_value=False)
        mock_get.return_value = mock_service

        resp = await client.post(STOP_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "already stopped" in body["message"].lower()
        mock_service.stop.assert_not_called()

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_stop_success(self, mock_get, mock_service, client):
        """Should stop scheduler with default timeout."""
        type(mock_service).is_running = PropertyMock(return_value=True)
        mock_get.return_value = mock_service

        resp = await client.post(STOP_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "stopped successfully" in body["message"].lower()
        mock_service.stop.assert_called_once_with(timeout=30.0)

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_stop_custom_timeout(self, mock_get, mock_service, client):
        """Should pass custom timeout to service.stop()."""
        type(mock_service).is_running = PropertyMock(return_value=True)
        mock_get.return_value = mock_service

        resp = await client.post(STOP_URL, json={"timeout": 60.0})

        assert resp.status_code == 200
        mock_service.stop.assert_called_once_with(timeout=60.0)

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_stop_error_returns_500(self, mock_get, mock_service, client):
        """Service exception should result in 500."""
        type(mock_service).is_running = PropertyMock(return_value=True)
        mock_service.stop.side_effect = RuntimeError("Thread hang")
        mock_get.return_value = mock_service

        resp = await client.post(STOP_URL)

        assert resp.status_code == 500
        assert "Failed to stop scheduler" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /scheduler/status
# ---------------------------------------------------------------------------
class TestGetSchedulerStatus:
    """Tests for the get_scheduler_status endpoint."""

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_status_success(self, mock_get, mock_service, client):
        """Should return full status with cumulative_stats."""
        mock_get.return_value = mock_service

        resp = await client.get(STATUS_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["scheduler_running"] is True
        assert body["current_task_id"] == "task-42"
        assert body["queue_length"] == 5
        assert body["has_active_reservation"] is False

        stats = body["cumulative_stats"]
        assert stats["total_executed"] == 100
        assert stats["succeeded"] == 90
        assert stats["failed"] == 5
        assert stats["cancelled"] == 3
        assert stats["skipped"] == 2

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_status_idle_scheduler(self, mock_get, client):
        """Idle scheduler should show zeros and no current task."""
        idle_service = MagicMock()
        idle_service.get_scheduler_status.return_value = {
            "scheduler_running": False,
            "current_task_id": None,
            "queue_length": 0,
            "cumulative_stats": {
                "total_executed": 0,
                "succeeded": 0,
                "failed": 0,
                "cancelled": 0,
                "skipped": 0,
            },
            "has_active_reservation": False,
        }
        mock_get.return_value = idle_service

        resp = await client.get(STATUS_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["scheduler_running"] is False
        assert body["current_task_id"] is None
        assert body["queue_length"] == 0

    @patch("src.api.routers.scheduler.get_scheduler_service")
    async def test_status_error_returns_500(self, mock_get, mock_service, client):
        """Service exception should result in 500."""
        mock_service.get_scheduler_status.side_effect = RuntimeError("DB error")
        mock_get.return_value = mock_service

        resp = await client.get(STATUS_URL)

        assert resp.status_code == 500
        assert "Failed to get scheduler status" in resp.json()["detail"]
