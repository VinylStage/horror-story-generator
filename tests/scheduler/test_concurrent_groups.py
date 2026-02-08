"""Tests for concurrent execution group feature."""
import pytest
import time
import threading
from src.scheduler.entities import Task, TaskRun, TaskStatus, TaskRunStatus, TaskGroup, TaskGroupStatus
from src.scheduler.persistence import PersistenceAdapter
from src.scheduler.queue_manager import QueueManager


class TestConcurrentGroupCreation:
    """Tests for POST /tasks/group - creating concurrent groups."""

    def test_create_concurrent_group(self, persistence, queue_manager):
        """Should create a concurrent group from QUEUED tasks."""
        # Create individual tasks
        t1 = queue_manager.enqueue(task_type="story", params={"topic": "A"})
        t2 = queue_manager.enqueue(task_type="story", params={"topic": "B"})
        t3 = queue_manager.enqueue(task_type="research", params={"topic": "C"})

        # Group tasks 2 and 3
        group, tasks = queue_manager.create_concurrent_group(
            task_ids=[t2.task_id, t3.task_id],
            name="test concurrent group",
        )

        assert group.execution_mode == "concurrent"
        assert group.name == "test concurrent group"
        assert group.status == TaskGroupStatus.QUEUED
        assert len(tasks) == 2

        # Verify tasks got group_id assigned
        for task in tasks:
            assert task.group_id == group.group_id

    def test_concurrent_group_rejects_non_queued(self, persistence, queue_manager):
        """Should reject tasks not in QUEUED status."""
        t1 = queue_manager.enqueue(task_type="story", params={})
        # Claim t1 (makes it RUNNING)
        persistence.atomic_claim_task(t1.task_id)

        t2 = queue_manager.enqueue(task_type="story", params={})

        with pytest.raises(Exception, match="QUEUED"):
            queue_manager.create_concurrent_group(task_ids=[t1.task_id, t2.task_id])

    def test_concurrent_group_rejects_already_grouped(self, persistence, queue_manager):
        """Should reject tasks already in a group."""
        group, tasks = queue_manager.create_task_group(
            [{"task_type": "story", "params": {}}],
            name="existing group",
        )

        t2 = queue_manager.enqueue(task_type="story", params={})

        with pytest.raises(Exception, match="already"):
            queue_manager.create_concurrent_group(task_ids=[tasks[0].task_id, t2.task_id])


class TestConcurrentGroupDispatch:
    """Tests for concurrent group execution behavior."""

    def test_concurrent_tasks_not_blocked(self, persistence):
        """Tasks in concurrent group should NOT block each other."""
        group = TaskGroup.create(name="concurrent", execution_mode="concurrent")
        group = persistence.create_task_group(group)
        persistence.update_task_group(group.group_id, status=TaskGroupStatus.QUEUED)

        t1 = Task.create(task_type="story", params={}, group_id=group.group_id, sequence_number=0)
        t1 = persistence.create_task(t1)

        t2 = Task.create(task_type="story", params={}, group_id=group.group_id, sequence_number=1)
        t2 = persistence.create_task(t2)

        # Neither should be blocked
        assert persistence.is_task_blocked_by_group(t1) == False
        assert persistence.is_task_blocked_by_group(t2) == False

    def test_sequential_tasks_still_blocked(self, persistence):
        """Tasks in sequential group should still block each other."""
        group = TaskGroup.create(name="sequential", execution_mode="sequential")
        group = persistence.create_task_group(group)
        persistence.update_task_group(group.group_id, status=TaskGroupStatus.QUEUED)

        t1 = Task.create(task_type="story", params={}, group_id=group.group_id, sequence_number=0)
        t1 = persistence.create_task(t1)

        t2 = Task.create(task_type="story", params={}, group_id=group.group_id, sequence_number=1)
        t2 = persistence.create_task(t2)

        # t1 not blocked, t2 blocked by t1
        assert persistence.is_task_blocked_by_group(t1) == False
        assert persistence.is_task_blocked_by_group(t2) == True


class TestConcurrentGroupExecution:
    """Tests for execution_mode field persistence."""

    def test_execution_mode_persisted(self, persistence):
        """Should persist execution_mode in task_groups table."""
        group = TaskGroup.create(name="test", execution_mode="concurrent")
        persistence.create_task_group(group)

        loaded = persistence.get_task_group(group.group_id)
        assert loaded.execution_mode == "concurrent"

    def test_default_execution_mode(self, persistence):
        """Default execution_mode should be sequential."""
        group = TaskGroup.create(name="default")
        persistence.create_task_group(group)

        loaded = persistence.get_task_group(group.group_id)
        assert loaded.execution_mode == "sequential"
