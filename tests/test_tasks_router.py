"""
Tests for tasks router.

Phase 4: Scheduler-based task CRUD + batch input + concurrent groups.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API."""
    from src.api.main import app
    return TestClient(app)


class TestCreateTasks:
    """Tests for POST /tasks endpoint (always array input)."""

    def test_create_single_task(self, client):
        """Should create a single task from array with one item."""
        from src.scheduler.entities import Task, TaskStatus

        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "task-123"
        mock_task.task_type = "story"
        mock_task.status = TaskStatus.QUEUED
        mock_task.params = {"max_stories": 1}
        mock_task.priority = 0
        mock_task.position = 0
        mock_task.template_id = None
        mock_task.group_id = None
        mock_task.retry_of = None
        mock_task.created_at = "2026-01-18T10:00:00"
        mock_task.queued_at = "2026-01-18T10:00:00"
        mock_task.started_at = None
        mock_task.finished_at = None

        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.enqueue_task.return_value = mock_task
            mock_get_service.return_value = mock_service

            response = client.post(
                "/tasks",
                json=[{"type": "story", "params": {"max_stories": 1}, "priority": 0}]
            )

            assert response.status_code == 201
            data = response.json()
            assert data["total"] == 1
            assert len(data["tasks"]) == 1
            assert data["tasks"][0]["task_id"] == "task-123"
            assert data["tasks"][0]["task_type"] == "story"
            assert data["tasks"][0]["status"] == "QUEUED"

    def test_create_multiple_tasks(self, client):
        """Should create multiple tasks from array."""
        from src.scheduler.entities import Task, TaskStatus

        mock_task1 = MagicMock(spec=Task)
        mock_task1.task_id = "task-1"
        mock_task1.task_type = "story"
        mock_task1.status = TaskStatus.QUEUED
        mock_task1.params = {"max_stories": 1}
        mock_task1.priority = 0
        mock_task1.position = 0
        mock_task1.template_id = None
        mock_task1.group_id = None
        mock_task1.retry_of = None
        mock_task1.created_at = "2026-01-18T10:00:00"
        mock_task1.queued_at = "2026-01-18T10:00:00"
        mock_task1.started_at = None
        mock_task1.finished_at = None

        mock_task2 = MagicMock(spec=Task)
        mock_task2.task_id = "task-2"
        mock_task2.task_type = "research"
        mock_task2.status = TaskStatus.QUEUED
        mock_task2.params = {"topic": "test"}
        mock_task2.priority = 10
        mock_task2.position = 1
        mock_task2.template_id = None
        mock_task2.group_id = None
        mock_task2.retry_of = None
        mock_task2.created_at = "2026-01-18T10:00:00"
        mock_task2.queued_at = "2026-01-18T10:00:00"
        mock_task2.started_at = None
        mock_task2.finished_at = None

        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.enqueue_task.side_effect = [mock_task1, mock_task2]
            mock_get_service.return_value = mock_service

            response = client.post(
                "/tasks",
                json=[
                    {"type": "story", "params": {"max_stories": 1}, "priority": 0},
                    {"type": "research", "params": {"topic": "test"}, "priority": 10},
                ]
            )

            assert response.status_code == 201
            data = response.json()
            assert data["total"] == 2
            assert len(data["tasks"]) == 2
            assert data["tasks"][0]["task_id"] == "task-1"
            assert data["tasks"][1]["task_id"] == "task-2"

    def test_create_tasks_empty_array_rejected(self, client):
        """Should reject empty array."""
        response = client.post("/tasks", json=[])
        # FastAPI validates List min_length or returns 422
        assert response.status_code == 422


class TestGetTask:
    """Tests for GET /tasks/{task_id} endpoint."""

    def test_get_task(self, client):
        """Should return task details."""
        from src.scheduler.entities import Task, TaskStatus

        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "task-123"
        mock_task.task_type = "story"
        mock_task.status = TaskStatus.QUEUED
        mock_task.params = {"max_stories": 1}
        mock_task.priority = 0
        mock_task.position = 1
        mock_task.template_id = None
        mock_task.group_id = None
        mock_task.retry_of = None
        mock_task.created_at = "2026-01-18T10:00:00"
        mock_task.queued_at = "2026-01-18T10:00:00"
        mock_task.started_at = None
        mock_task.finished_at = None

        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_task.return_value = mock_task
            mock_get_service.return_value = mock_service

            response = client.get("/tasks/task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task-123"
            assert data["task_type"] == "story"
            assert data["status"] == "QUEUED"

    def test_get_nonexistent_task(self, client):
        """Should return 404 for nonexistent task."""
        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_task.return_value = None
            mock_get_service.return_value = mock_service

            response = client.get("/tasks/nonexistent-id")

            assert response.status_code == 404


class TestListTasks:
    """Tests for GET /tasks endpoint."""

    def test_list_tasks_empty(self, client):
        """Should return empty list when no tasks."""
        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_all_tasks.return_value = []
            mock_service.get_queue_stats.return_value = {
                "queued_count": 0,
                "running_count": 0,
            }
            mock_get_service.return_value = mock_service

            response = client.get("/tasks")

            assert response.status_code == 200
            data = response.json()
            assert data["tasks"] == []
            assert data["total"] == 0


    def test_list_tasks_sorted_by_status_priority(self, client):
        """Should return tasks sorted: RUNNING → QUEUED → COMPLETED."""
        from src.scheduler.entities import Task, TaskStatus

        mock_cancelled = MagicMock(spec=Task)
        mock_cancelled.task_id = "task-done"
        mock_cancelled.task_type = "story"
        mock_cancelled.status = TaskStatus.CANCELLED
        mock_cancelled.params = {}
        mock_cancelled.priority = 0
        mock_cancelled.position = 0
        mock_cancelled.template_id = None
        mock_cancelled.group_id = None
        mock_cancelled.retry_of = None
        mock_cancelled.created_at = "2026-01-18T10:00:00"
        mock_cancelled.queued_at = "2026-01-18T10:00:00"
        mock_cancelled.started_at = "2026-01-18T10:01:00"
        mock_cancelled.finished_at = "2026-01-18T10:05:00"

        mock_queued = MagicMock(spec=Task)
        mock_queued.task_id = "task-wait"
        mock_queued.task_type = "story"
        mock_queued.status = TaskStatus.QUEUED
        mock_queued.params = {}
        mock_queued.priority = 0
        mock_queued.position = 100
        mock_queued.template_id = None
        mock_queued.group_id = None
        mock_queued.retry_of = None
        mock_queued.created_at = "2026-01-18T10:02:00"
        mock_queued.queued_at = "2026-01-18T10:02:00"
        mock_queued.started_at = None
        mock_queued.finished_at = None

        mock_running = MagicMock(spec=Task)
        mock_running.task_id = "task-run"
        mock_running.task_type = "research"
        mock_running.status = TaskStatus.RUNNING
        mock_running.params = {}
        mock_running.priority = 0
        mock_running.position = 0
        mock_running.template_id = None
        mock_running.group_id = None
        mock_running.retry_of = None
        mock_running.created_at = "2026-01-18T10:01:00"
        mock_running.queued_at = "2026-01-18T10:01:00"
        mock_running.started_at = "2026-01-18T10:03:00"
        mock_running.finished_at = None

        # Service returns already-sorted list (persistence handles ORDER BY)
        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_all_tasks.return_value = [mock_running, mock_queued, mock_cancelled]
            mock_service.get_queue_stats.return_value = {
                "queued_count": 1,
                "running_count": 1,
            }
            mock_get_service.return_value = mock_service

            response = client.get("/tasks")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert data["tasks"][0]["task_id"] == "task-run"
            assert data["tasks"][0]["status"] == "RUNNING"
            assert data["tasks"][1]["task_id"] == "task-wait"
            assert data["tasks"][1]["status"] == "QUEUED"
            assert data["tasks"][2]["task_id"] == "task-done"
            assert data["tasks"][2]["status"] == "CANCELLED"


class TestDeleteTask:
    """Tests for DELETE /tasks/{task_id} endpoint."""

    def test_cancel_task(self, client):
        """Should cancel a queued task."""
        from src.scheduler.entities import Task, TaskStatus

        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "task-123"
        mock_task.status = TaskStatus.CANCELLED

        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.cancel_task.return_value = mock_task
            mock_get_service.return_value = mock_service

            response = client.delete("/tasks/task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task-123"
            assert data["success"] is True


class TestCreateTaskGroup:
    """Tests for POST /tasks/group endpoint."""

    def test_create_concurrent_group(self, client):
        """Should create a concurrent execution group."""
        from src.scheduler.entities import Task, TaskStatus, TaskGroup, TaskGroupStatus

        mock_group = MagicMock(spec=TaskGroup)
        mock_group.group_id = "grp-123"
        mock_group.name = "test group"
        mock_group.status = TaskGroupStatus.CREATED
        mock_group.execution_mode = "concurrent"
        mock_group.created_at = "2026-01-18T10:00:00"
        mock_group.started_at = None
        mock_group.finished_at = None

        mock_task1 = MagicMock(spec=Task)
        mock_task1.task_id = "task-1"
        mock_task1.task_type = "story"
        mock_task1.status = TaskStatus.QUEUED
        mock_task1.params = {}
        mock_task1.priority = 0
        mock_task1.position = 0
        mock_task1.template_id = None
        mock_task1.group_id = "grp-123"
        mock_task1.retry_of = None
        mock_task1.created_at = "2026-01-18T10:00:00"
        mock_task1.queued_at = "2026-01-18T10:00:00"
        mock_task1.started_at = None
        mock_task1.finished_at = None

        with patch("src.api.routers.tasks.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.create_concurrent_group.return_value = (mock_group, [mock_task1])
            mock_get_service.return_value = mock_service

            response = client.post(
                "/tasks/group",
                json={"task_ids": ["task-1"], "mode": "concurrent", "name": "test group"}
            )

            assert response.status_code == 201
            data = response.json()
            assert data["group_id"] == "grp-123"
            assert data["execution_mode"] == "concurrent"
            assert len(data["tasks"]) == 1
