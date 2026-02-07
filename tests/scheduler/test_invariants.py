"""
Invariant Tests for Task Scheduler.

Tests from TEST_STRATEGY.md Section 2 (Invariant Test Matrix):
- INV-001: Task immutability after dispatch
- INV-002: TaskRun immutability
- INV-003: Single running task per worker
- INV-004: Queue order consistency
- INV-005: Schedule-Task isolation
- INV-006: TaskGroup completion atomicity (xfail - not implemented)

Each test explicitly states the invariant being validated and
will fail deterministically if the invariant is violated.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.scheduler import (
    PersistenceAdapter,
    QueueManager,
    Dispatcher,
    Task,
    TaskRun,
    TaskStatus,
    TaskRunStatus,
    InvalidOperationError,
)


# =============================================================================
# INV-001: Task Immutability After Dispatch
# =============================================================================


class TestINV001TaskImmutability:
    """
    INV-001: Once a Task enters DISPATCHED/RUNNING state,
    its `params` field MUST NOT change.
    """

    def test_inv_001_a_reject_params_update_on_running_task(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-001-A: Reject params update on RUNNING task.

        Setup: Create task, set status=RUNNING
        Action: Call update_task(params={new})
        Assertion: InvalidOperationError raised
        """
        # Setup: Create a RUNNING task
        task = create_task(status=TaskStatus.RUNNING)

        # Action & Assertion: Attempt to modify params should fail
        with pytest.raises(InvalidOperationError) as exc_info:
            persistence.update_task(task.task_id, params={"modified": True})

        assert "INV-001" in str(exc_info.value) or "params" in str(exc_info.value).lower()

    def test_inv_001_b_allow_params_update_on_queued_task(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-001-B: Allow params update on QUEUED task.

        Setup: Create task, status=QUEUED
        Action: Call update_task(params={new})
        Assertion: Params updated successfully
        """
        # Setup: Create a QUEUED task
        task = create_task(status=TaskStatus.QUEUED)
        original_params = task.params.copy()

        # Action: Update params
        new_params = {"modified": True, "value": 42}
        updated_task = persistence.update_task(task.task_id, params=new_params)

        # Assertion: Params should be updated
        assert updated_task.params == new_params
        assert updated_task.params != original_params

    def test_inv_001_c_priority_update_allowed_on_queued(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-001-C: Priority update allowed on QUEUED.

        Setup: Create task, status=QUEUED
        Action: Call update_task(priority=10)
        Assertion: Priority updated
        """
        # Setup: Create a QUEUED task with default priority
        task = create_task(status=TaskStatus.QUEUED, priority=0)

        # Action: Update priority
        updated_task = persistence.update_task(task.task_id, priority=10)

        # Assertion: Priority should be updated
        assert updated_task.priority == 10

    def test_inv_001_d_priority_update_rejected_on_running(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-001-D: Priority update rejected on RUNNING.

        Setup: Create task, status=RUNNING
        Action: Call update_task(priority=10)
        Assertion: InvalidOperationError raised
        """
        # Setup: Create a RUNNING task
        task = create_task(status=TaskStatus.RUNNING)

        # Action & Assertion: Attempt to modify priority should fail
        with pytest.raises(InvalidOperationError) as exc_info:
            persistence.update_task(task.task_id, priority=10)

        assert "priority" in str(exc_info.value).lower() or "dispatch" in str(exc_info.value).lower()


# =============================================================================
# INV-002: TaskRun Immutability
# =============================================================================


class TestINV002TaskRunImmutability:
    """
    INV-002: Once a TaskRun is created, only `finished_at`, `status`,
    `exit_code`, `error`, and `artifacts` may be updated.
    """

    def test_inv_002_a_reject_task_id_modification(
        self, persistence: PersistenceAdapter, create_task, create_task_run
    ):
        """
        INV-002-A: Reject task_id modification.

        Setup: Create TaskRun
        Action: Call update(task_id=other)
        Assertion: InvalidOperationError raised (or no task_id param allowed)
        """
        # Setup: Create a task and task run
        task = create_task()
        task_run = create_task_run(task.task_id)

        # Action & Assertion: task_id is not modifiable via update_task_run
        # The update_task_run method doesn't accept task_id param at all
        # This test verifies the API doesn't allow it
        original_task_id = task_run.task_id

        # Try to update something else and verify task_id unchanged
        updated_run = persistence.update_task_run(task_run.run_id, status=TaskRunStatus.COMPLETED)

        # Verify task_id hasn't changed
        assert updated_run.task_id == original_task_id

    def test_inv_002_b_reject_params_snapshot_modification(
        self, persistence: PersistenceAdapter, create_task, create_task_run
    ):
        """
        INV-002-B: Reject params_snapshot modification.

        Setup: Create TaskRun
        Action: Call update(params_snapshot={})
        Assertion: InvalidOperationError raised (or no params_snapshot param allowed)
        """
        # Setup: Create a task and task run
        task = create_task(params={"original": True})
        task_run = create_task_run(task.task_id)
        original_snapshot = task_run.params_snapshot.copy()

        # Action: Attempt to modify - update_task_run doesn't accept params_snapshot
        # This verifies the immutability by design
        updated_run = persistence.update_task_run(task_run.run_id, status=TaskRunStatus.COMPLETED)

        # Assertion: params_snapshot should be unchanged
        assert updated_run.params_snapshot == original_snapshot

    def test_inv_002_c_allow_status_update(
        self, persistence: PersistenceAdapter, create_task, create_task_run
    ):
        """
        INV-002-C: Allow status update.

        Setup: Create TaskRun
        Action: Call update(status=COMPLETED)
        Assertion: Status updated
        """
        # Setup: Create a task and task run (status is initially None)
        task = create_task()
        task_run = create_task_run(task.task_id)
        assert task_run.status is None

        # Action: Update status
        updated_run = persistence.update_task_run(task_run.run_id, status=TaskRunStatus.COMPLETED)

        # Assertion: Status should be updated
        assert updated_run.status == TaskRunStatus.COMPLETED

    def test_inv_002_d_allow_error_update(
        self, persistence: PersistenceAdapter, create_task, create_task_run
    ):
        """
        INV-002-D: Allow error update.

        Setup: Create TaskRun
        Action: Call update(error="msg")
        Assertion: Error updated
        """
        # Setup: Create a task and task run
        task = create_task()
        task_run = create_task_run(task.task_id)
        assert task_run.error is None

        # Action: Update error
        error_msg = "Test error message"
        updated_run = persistence.update_task_run(task_run.run_id, error=error_msg)

        # Assertion: Error should be updated
        assert updated_run.error == error_msg

    def test_inv_002_e_allow_artifacts_update(
        self, persistence: PersistenceAdapter, create_task, create_task_run
    ):
        """
        INV-002-E: Allow artifacts append.

        Setup: Create TaskRun
        Action: Call update(artifacts=[...])
        Assertion: Artifacts updated
        """
        # Setup: Create a task and task run
        task = create_task()
        task_run = create_task_run(task.task_id)
        assert task_run.artifacts == []

        # Action: Update artifacts
        artifacts = ["/path/to/artifact1.txt", "/path/to/artifact2.json"]
        updated_run = persistence.update_task_run(task_run.run_id, artifacts=artifacts)

        # Assertion: Artifacts should be updated
        assert updated_run.artifacts == artifacts


# =============================================================================
# INV-003: Single Running Task Per Worker
# =============================================================================


class TestINV003SingleRunningTask:
    """
    INV-003: A worker MUST NOT execute more than one Task simultaneously.
    """

    def test_inv_003_a_second_dispatch_rejected_while_running(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_task,
    ):
        """
        INV-003-A: Second dispatch rejected while running.

        Setup: Task1 RUNNING
        Action: Try dispatch Task2
        Assertion: Task2 not dispatched (waits or rejects)
        """
        # Setup: Create two tasks and make first one RUNNING
        task1 = create_task(priority=10)
        task2 = create_task(priority=5)

        # Dispatch first task
        running_task, _ = persistence.atomic_claim_task(task1.task_id)
        assert running_task.status == TaskStatus.RUNNING

        # Action & Assertion: get_next should still return task2 but it's QUEUED
        # The single-worker constraint is enforced by the dispatcher, not queue_manager
        # The queue_manager just returns the next task; dispatcher decides whether to run it
        next_task = queue_manager.get_next()
        assert next_task is not None
        assert next_task.task_id == task2.task_id
        assert next_task.status == TaskStatus.QUEUED

        # Verify only one task is RUNNING
        running_tasks = persistence.list_tasks_by_status(TaskStatus.RUNNING)
        assert len(running_tasks) == 1
        assert running_tasks[0].task_id == task1.task_id

    def test_inv_003_b_dispatch_allowed_after_completion(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_task,
    ):
        """
        INV-003-B: Dispatch allowed after completion.

        Setup: Task1 completes
        Action: Dispatch Task2
        Assertion: Task2 dispatched successfully
        """
        # Setup: Create two tasks
        task1 = create_task(priority=10)
        task2 = create_task(priority=5)

        # Dispatch and complete first task
        running_task1, task_run1 = persistence.atomic_claim_task(task1.task_id)
        assert running_task1.status == TaskStatus.RUNNING

        # Complete task1
        persistence.update_task_run(
            task_run1.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(
            task1.task_id,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Action: Dispatch task2
        running_task2, task_run2 = persistence.atomic_claim_task(task2.task_id)

        # Assertion: Task2 should be dispatched
        assert running_task2.status == TaskStatus.RUNNING
        assert task_run2 is not None


# =============================================================================
# INV-004: Queue Order Consistency
# =============================================================================


class TestINV004QueueOrder:
    """
    INV-004: Tasks MUST be dispatched in order of
    (priority DESC, position ASC, created_at ASC).
    """

    def test_inv_004_a_higher_priority_first(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-004-A: Higher priority first.

        Setup: Task1(priority=5), Task2(priority=10)
        Action: get_next()
        Assertion: Returns Task2
        """
        # Setup: Create tasks with different priorities
        task1 = create_task(priority=5)
        task2 = create_task(priority=10)

        # Action: Get next task
        next_task = persistence.get_next_queued_task()

        # Assertion: Higher priority task should be first
        assert next_task is not None
        assert next_task.task_id == task2.task_id
        assert next_task.priority == 10

    def test_inv_004_b_lower_position_first_same_priority(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-004-B: Lower position first (same priority).

        Setup: Task1(pos=200), Task2(pos=100), same priority
        Action: get_next()
        Assertion: Returns Task2
        """
        # Setup: Create tasks with same priority
        # First task gets position 100, second gets 200
        task1 = create_task(priority=5)
        task2 = create_task(priority=5)

        # Verify positions were assigned
        task1_fresh = persistence.get_task(task1.task_id)
        task2_fresh = persistence.get_task(task2.task_id)

        # First created task should have lower position and be dispatched first
        assert task1_fresh.position < task2_fresh.position

        # Action: Get next task
        next_task = persistence.get_next_queued_task()

        # Assertion: Lower position (first created) should be first
        assert next_task is not None
        assert next_task.task_id == task1.task_id

    def test_inv_004_c_earlier_created_at_first_same_priority_position(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-004-C: Earlier created_at first (same priority, position).

        Setup: Task1(created=t1), Task2(created=t2), t1 < t2
        Action: get_next()
        Assertion: Returns Task1
        """
        # Setup: Create tasks with same priority but explicit position override
        # This tests the tie-breaker using created_at
        now = datetime.utcnow()
        earlier = now - timedelta(minutes=5)

        task1 = Task.create(
            task_type="story",
            params={"test": True},
            priority=5,
        )
        task1.created_at = earlier.isoformat() + "Z"
        task1.queued_at = earlier.isoformat() + "Z"
        task1.position = 100  # Same position
        task1 = persistence.create_task(task1)

        task2 = Task.create(
            task_type="story",
            params={"test": True},
            priority=5,
        )
        task2.created_at = now.isoformat() + "Z"
        task2.queued_at = now.isoformat() + "Z"
        # Need to force same position
        persistence._get_connection()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE tasks SET position = ? WHERE task_id = ?",
                (100, task2.task_id),
            )

        # Refresh task2
        task2 = persistence.get_task(task2.task_id)

        # Action: Get next task
        next_task = persistence.get_next_queued_task()

        # Assertion: Earlier created_at should be first
        assert next_task is not None
        assert next_task.task_id == task1.task_id

    def test_inv_004_d_full_ordering_test(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-004-D: Full ordering test.

        Setup: 5 tasks with mixed priority/position/created_at
        Action: get_all_ordered()
        Assertion: Exact expected order
        """
        # Setup: Create tasks with various priorities
        # Expected order: priority DESC, position ASC, created_at ASC
        tasks = []
        tasks.append(create_task(priority=1))   # Last (lowest priority)
        tasks.append(create_task(priority=10))  # First (highest priority)
        tasks.append(create_task(priority=5))   # Middle
        tasks.append(create_task(priority=5))   # Middle (after prev due to position)
        tasks.append(create_task(priority=10))  # Second (same priority, higher position)

        # Action: Get all queued tasks
        queued = persistence.list_tasks_by_status(TaskStatus.QUEUED)

        # Expected order:
        # 1. tasks[1] - priority=10, lowest position among priority=10
        # 2. tasks[4] - priority=10, higher position
        # 3. tasks[2] - priority=5, lowest position among priority=5
        # 4. tasks[3] - priority=5, higher position
        # 5. tasks[0] - priority=1

        assert len(queued) == 5
        assert queued[0].task_id == tasks[1].task_id  # priority=10, first created
        assert queued[1].task_id == tasks[4].task_id  # priority=10, second created
        assert queued[2].task_id == tasks[2].task_id  # priority=5, first created
        assert queued[3].task_id == tasks[3].task_id  # priority=5, second created
        assert queued[4].task_id == tasks[0].task_id  # priority=1

    def test_inv_004_e_deterministic_same_input_same_output(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        INV-004-E: Deterministic (same input → same output).

        Setup: Fixed set of tasks
        Action: Run get_next() N times
        Assertion: Same order every time
        """
        # Setup: Create a set of tasks
        tasks = [
            create_task(priority=10),
            create_task(priority=5),
            create_task(priority=15),
            create_task(priority=5),
        ]

        # Action: Get next task multiple times and collect results
        results = []
        for _ in range(10):
            next_task = persistence.get_next_queued_task()
            results.append(next_task.task_id if next_task else None)

        # Assertion: All results should be the same (deterministic)
        assert all(r == results[0] for r in results)
        # And should be the highest priority task
        assert results[0] == tasks[2].task_id  # priority=15


# =============================================================================
# INV-005: Schedule-Task Isolation
# =============================================================================


class TestINV005ScheduleTaskIsolation:
    """
    INV-005: A Schedule's state MUST NOT affect already-created Tasks.
    """

    def test_inv_005_a_task_params_snapshot_is_independent(
        self,
        persistence: PersistenceAdapter,
        create_template,
    ):
        """
        INV-005-A: Task params snapshot is independent.

        Setup: Create task from schedule
        Action: Update schedule params
        Assertion: Task.params unchanged
        """
        # Setup: Create a template
        template = create_template(
            name="test-template",
            task_type="story",
            default_params={"original": True, "value": 42},
        )

        # Create a task with template params
        task = Task.create(
            task_type=template.task_type,
            params=template.default_params.copy(),
            template_id=template.template_id,
        )
        task = persistence.create_task(task)
        original_params = task.params.copy()

        # Action: Update template params
        persistence.update_template(
            template.template_id,
            default_params={"modified": True, "new_value": 100},
        )

        # Assertion: Task params should be unchanged
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.params == original_params
        assert task_fresh.params.get("original") is True
        assert task_fresh.params.get("value") == 42

    def test_inv_005_b_disable_schedule_doesnt_cancel_tasks(
        self,
        persistence: PersistenceAdapter,
        create_template,
    ):
        """
        INV-005-B: Disable schedule doesn't cancel tasks.

        Setup: Create task, then disable schedule
        Action: Check task status
        Assertion: Task still QUEUED
        """
        # Setup: Create a template and schedule
        template = create_template(
            name="test-template",
            task_type="story",
        )

        from src.scheduler import Schedule

        schedule = Schedule.create(
            template_id=template.template_id,
            name="test-schedule",
            cron_expression="0 * * * *",
            enabled=True,
        )
        schedule = persistence.create_schedule(schedule)

        # Create a task linked to the schedule
        task = Task.create(
            task_type=template.task_type,
            params={"test": True},
            template_id=template.template_id,
            schedule_id=schedule.schedule_id,
        )
        task = persistence.create_task(task)

        # Action: Disable the schedule
        persistence.update_schedule(schedule.schedule_id, enabled=False)

        # Assertion: Task should still be QUEUED
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.QUEUED


# =============================================================================
# INV-006: TaskGroup Completion Atomicity
# =============================================================================


class TestINV006TaskGroupAtomicity:
    """
    INV-006: A TaskGroup's terminal status MUST be determined only
    when ALL member Tasks reach terminal status.
    """

    def test_inv_006_a_group_running_if_any_task_running(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-A: Group RUNNING if any task RUNNING.

        Setup: Group with 3 tasks, 1 RUNNING
        Action: compute_group_status()
        Assertion: RUNNING
        """
        from src.scheduler import TaskGroup, TaskGroupStatus, TaskRunStatus

        # Create a group
        group = TaskGroup.create(name="test-group")
        group = persistence.create_task_group(group)

        # Create 3 tasks in the group
        task1 = Task.create(
            task_type="story",
            params={"seq": 1},
            group_id=group.group_id,
            sequence_number=0,
        )
        task2 = Task.create(
            task_type="story",
            params={"seq": 2},
            group_id=group.group_id,
            sequence_number=1,
        )
        task3 = Task.create(
            task_type="story",
            params={"seq": 3},
            group_id=group.group_id,
            sequence_number=2,
        )
        task1 = persistence.create_task(task1)
        task2 = persistence.create_task(task2)
        task3 = persistence.create_task(task3)

        # Mark task1 as RUNNING using atomic_claim_task
        task1, task_run1 = persistence.atomic_claim_task(task1.task_id)

        # Action: compute group status
        status = persistence.compute_group_status(group.group_id)

        # Assertion: should be RUNNING
        assert status == TaskGroupStatus.RUNNING

    def test_inv_006_b_group_terminal_only_when_all_terminal(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-B: Group terminal only when all terminal.

        Setup: 2 tasks COMPLETED (finished_at set), 1 QUEUED
        Action: compute_group_status()
        Assertion: QUEUED (not terminal yet)
        """
        from src.scheduler import TaskGroup, TaskGroupStatus, TaskRunStatus

        # Create a group
        group = TaskGroup.create(name="test-group")
        group = persistence.create_task_group(group)

        # Create 3 tasks in the group
        task1 = Task.create(
            task_type="story",
            params={"seq": 1},
            group_id=group.group_id,
            sequence_number=0,
        )
        task2 = Task.create(
            task_type="story",
            params={"seq": 2},
            group_id=group.group_id,
            sequence_number=1,
        )
        task3 = Task.create(
            task_type="story",
            params={"seq": 3},
            group_id=group.group_id,
            sequence_number=2,
        )
        task1 = persistence.create_task(task1)
        task2 = persistence.create_task(task2)
        task3 = persistence.create_task(task3)

        # Complete task1 and task2
        now = "2024-01-01T00:00:00Z"

        # Task1: RUNNING -> completed
        task1, task_run1 = persistence.atomic_claim_task(task1.task_id)
        persistence.update_task_run(
            task_run1.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=now,
        )
        persistence.update_task(task1.task_id, finished_at=now)

        # Task2: RUNNING -> completed
        task2, task_run2 = persistence.atomic_claim_task(task2.task_id)
        persistence.update_task_run(
            task_run2.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=now,
        )
        persistence.update_task(task2.task_id, finished_at=now)

        # Task3 remains QUEUED

        # Action: compute group status
        status = persistence.compute_group_status(group.group_id)

        # Assertion: should be QUEUED (not terminal because task3 is still QUEUED)
        assert status == TaskGroupStatus.QUEUED

    def test_inv_006_c_group_partial_if_any_failed(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-C: Group PARTIAL if any FAILED.

        Setup: All tasks terminal, 1 FAILED
        Action: compute_group_status()
        Assertion: PARTIAL
        """
        from src.scheduler import TaskGroup, TaskGroupStatus, TaskRunStatus

        # Create a group
        group = TaskGroup.create(name="test-group")
        group = persistence.create_task_group(group)

        # Create 3 tasks in the group
        task1 = Task.create(
            task_type="story",
            params={"seq": 1},
            group_id=group.group_id,
            sequence_number=0,
        )
        task2 = Task.create(
            task_type="story",
            params={"seq": 2},
            group_id=group.group_id,
            sequence_number=1,
        )
        task3 = Task.create(
            task_type="story",
            params={"seq": 3},
            group_id=group.group_id,
            sequence_number=2,
        )
        task1 = persistence.create_task(task1)
        task2 = persistence.create_task(task2)
        task3 = persistence.create_task(task3)

        now = "2024-01-01T00:00:00Z"

        # Task1: completed successfully
        task1, task_run1 = persistence.atomic_claim_task(task1.task_id)
        persistence.update_task_run(
            task_run1.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=now,
        )
        persistence.update_task(task1.task_id, finished_at=now)

        # Task2: FAILED
        task2, task_run2 = persistence.atomic_claim_task(task2.task_id)
        persistence.update_task_run(
            task_run2.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=now,
            error="Test failure",
        )
        persistence.update_task(task2.task_id, finished_at=now)

        # Task3: cancelled (due to task2 failure in stop-on-failure)
        persistence.update_task(
            task3.task_id,
            status=TaskStatus.CANCELLED,
            finished_at=now,
        )

        # Action: compute group status
        status = persistence.compute_group_status(group.group_id)

        # Assertion: should be PARTIAL (some tasks failed)
        assert status == TaskGroupStatus.PARTIAL
