"""
Execution Path Scenario Tests for Task Scheduler.

Tests from TEST_STRATEGY.md Section 4 (Execution Path Scenario Tests):
- EP-NORM-*: Normal queue execution
- EP-DIRECT-*: Direct API next-slot reservation (DEC-004)
- EP-RETRY-*: Retry semantics (DEC-007)
- EP-SCHED-*: Schedule-triggered task creation (skipped - requires APScheduler)

Each test validates end-to-end execution scenarios.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta

from src.scheduler import (
    PersistenceAdapter,
    QueueManager,
    Dispatcher,
    Executor,
    RetryController,
    Task,
    TaskRun,
    TaskStatus,
    TaskRunStatus,
    ReservationStatus,
    ReservationConflictError,
)

from .conftest import MockTaskHandler


# =============================================================================
# EP-NORM: Normal Queue Execution
# =============================================================================


class TestEPNormalExecution:
    """
    Normal queue execution scenarios.

    Scenario: Task created -> queued -> dispatched -> executed -> completed
    """

    def test_ep_norm_01_task_lifecycle(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockTaskHandler,
        create_task,
    ):
        """
        EP-NORM-01: Task lifecycle - create, dispatch, complete.

        Steps:
        1. Create task
        2. Wait for dispatch
        3. Execute successfully

        Assertions:
        - Task: QUEUED -> RUNNING
        - TaskRun: COMPLETED
        """
        # Setup: Configure mock handler for success
        mock_handler.set_result(TaskRunStatus.COMPLETED, exit_code=0)

        # Create task
        task = create_task(task_type="story", params={"test": True})
        assert task.status == TaskStatus.QUEUED

        # Dispatch and execute
        result = dispatcher.dispatch_one()

        # Assertions
        assert result is not None
        executed_task, task_run = result

        assert executed_task.task_id == task.task_id
        assert task_run.status == TaskRunStatus.COMPLETED
        assert task_run.exit_code == 0

        # Verify task state
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.COMPLETED
        assert task_fresh.finished_at is not None

    def test_ep_norm_02_execution_order_matches_queue_order(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockTaskHandler,
        create_task,
    ):
        """
        EP-NORM-02: Execution order matches queue order.

        Steps:
        1. Create 3 tasks with different priorities
        2. Execute all

        Assertions:
        - Execution order matches queue order (priority DESC)
        """
        # Setup: Configure mock handler for success
        mock_handler.set_result(TaskRunStatus.COMPLETED)

        # Create tasks with different priorities
        task_low = create_task(priority=1)
        task_high = create_task(priority=10)
        task_medium = create_task(priority=5)

        # Track execution order
        execution_order = []

        # Execute all
        for _ in range(3):
            result = dispatcher.dispatch_one()
            if result:
                execution_order.append(result[0].task_id)

        # Assertions: Should be high -> medium -> low
        assert len(execution_order) == 3
        assert execution_order[0] == task_high.task_id
        assert execution_order[1] == task_medium.task_id
        assert execution_order[2] == task_low.task_id

    def test_ep_norm_03_cancel_before_dispatch(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        create_task,
    ):
        """
        EP-NORM-03: Cancel task before dispatch.

        Steps:
        1. Create task
        2. Cancel before dispatch

        Assertions:
        - Task: CANCELLED
        - No TaskRun created
        """
        # Create task
        task = create_task()
        assert task.status == TaskStatus.QUEUED

        # Cancel
        cancelled_task = queue_manager.cancel(task.task_id)

        # Assertions
        assert cancelled_task.status == TaskStatus.CANCELLED

        # No TaskRun should exist
        task_run = persistence.get_task_run_for_task(task.task_id)
        assert task_run is None

        # Dispatch should skip this task (queue is empty)
        result = dispatcher.dispatch_one()
        assert result is None


# =============================================================================
# EP-DIRECT: Direct API Next-Slot Reservation (DEC-004)
# =============================================================================


class TestEPDirectExecution:
    """
    Direct API next-slot reservation scenarios.

    Scenario: Direct API reserves slot, waits for running task, executes, queue resumes
    """

    def test_ep_direct_01_direct_executes_between_tasks(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockTaskHandler,
        create_task,
    ):
        """
        EP-DIRECT-01: Direct executes between tasks.

        Steps:
        1. Task1 executed
        2. Direct API called (reserves slot internally)
        3. Direct executes
        4. Task2 dispatched

        Assertions:
        - Direct executes between Task1 and Task2
        """
        # Setup
        mock_handler.set_result(TaskRunStatus.COMPLETED)

        # Create tasks
        task1 = create_task(priority=10)
        task2 = create_task(priority=5)

        execution_order = []

        # Execute task1
        result = dispatcher.dispatch_one()
        assert result is not None
        execution_order.append(("task1", result[0].task_id))

        # Direct execution (handles its own reservation)
        direct_task_run = dispatcher.execute_direct(
            task_type="direct",
            params={"direct": True},
            reserved_by="direct-client",
        )
        assert direct_task_run.status == TaskRunStatus.COMPLETED
        execution_order.append(("direct", direct_task_run.task_id))

        # Now task2 can be dispatched
        result = dispatcher.dispatch_one()
        assert result is not None
        execution_order.append(("task2", result[0].task_id))

        # Verify order: task1 -> direct -> task2
        assert execution_order[0][0] == "task1"
        assert execution_order[1][0] == "direct"
        assert execution_order[2][0] == "task2"

    def test_ep_direct_02_empty_queue_direct_executes_immediately(
        self,
        persistence: PersistenceAdapter,
        dispatcher: Dispatcher,
        mock_handler: MockTaskHandler,
    ):
        """
        EP-DIRECT-02: Empty queue - direct executes immediately.

        Steps:
        1. Queue empty
        2. Direct API called

        Assertions:
        - Direct executes immediately
        """
        # Setup
        mock_handler.set_result(TaskRunStatus.COMPLETED)

        # Verify queue is empty
        result = dispatcher.dispatch_one()
        assert result is None

        # Direct execution should work immediately
        task_run = dispatcher.execute_direct(
            task_type="direct",
            params={"direct": True},
            reserved_by="direct-client",
        )

        assert task_run.status == TaskRunStatus.COMPLETED

    def test_ep_direct_03_second_direct_waits_for_first(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
    ):
        """
        EP-DIRECT-03: Second Direct API waits for first.

        Steps:
        1. Direct API #1
        2. Another Direct API #2

        Assertions:
        - Second waits for first to complete (or raises conflict)
        """
        # Reserve first slot
        reservation1 = queue_manager.reserve_next_slot("client-1")
        assert reservation1.status == ReservationStatus.ACTIVE

        # Second reservation should fail
        with pytest.raises(ReservationConflictError):
            queue_manager.reserve_next_slot("client-2")

        # Release first
        queue_manager.release_reservation(reservation1.reservation_id)

        # Now second can reserve
        reservation2 = queue_manager.reserve_next_slot("client-2")
        assert reservation2.status == ReservationStatus.ACTIVE

    def test_ep_direct_04_queue_paused_during_reservation(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        create_task,
    ):
        """
        EP-DIRECT-04: Queue paused during reservation.

        Steps:
        1. Direct reservation
        2. Task1 completes
        3. Verify queue paused

        Assertions:
        - Task2 not dispatched until reservation released
        """
        # Create task
        task = create_task()

        # Create reservation
        reservation = queue_manager.reserve_next_slot("direct-client")

        # Queue should be paused
        assert queue_manager.has_active_reservation()

        # Dispatch should not proceed
        result = dispatcher.dispatch_one()
        assert result is None

        # Task should still be QUEUED
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.QUEUED

    def test_ep_direct_05_queue_resumes_after_release(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockTaskHandler,
        create_task,
    ):
        """
        EP-DIRECT-05: Queue resumes after reservation released.

        Steps:
        1. Reservation released

        Assertions:
        - Queue dispatch resumes immediately
        """
        # Setup
        mock_handler.set_result(TaskRunStatus.COMPLETED)

        # Create task
        task = create_task()

        # Create and release reservation
        reservation = queue_manager.reserve_next_slot("direct-client")
        queue_manager.release_reservation(reservation.reservation_id)

        # No active reservation
        assert not queue_manager.has_active_reservation()

        # Queue should resume
        result = dispatcher.dispatch_one()
        assert result is not None
        assert result[0].task_id == task.task_id


# =============================================================================
# EP-RETRY: Retry Semantics (DEC-007)
# =============================================================================


class TestEPRetrySemantics:
    """
    Retry semantics scenarios.

    Scenario: Task fails, automatic retry up to 3, then manual required
    """

    def test_ep_retry_01_failed_task_creates_retry(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_task,
        create_task_run,
    ):
        """
        EP-RETRY-01: Failed task creates retry.

        Steps:
        1. Task1 fails

        Assertions:
        - Retry Task2 created automatically
        """
        # Create and fail task
        task1 = create_task()
        task1, task_run1 = persistence.atomic_claim_task(task1.task_id)

        persistence.update_task_run(
            task_run1.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error="Test failure",
        )
        persistence.update_task(task1.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Trigger retry evaluation
        task1_fresh = persistence.get_task(task1.task_id)
        task_run1_fresh = persistence.get_task_run(task_run1.run_id)

        retry_task = retry_controller.on_task_failed(task1_fresh, task_run1_fresh)

        # Assertions
        assert retry_task is not None
        assert retry_task.task_id != task1.task_id
        assert retry_task.retry_of == task1.task_id
        assert retry_task.status == TaskStatus.QUEUED

    def test_ep_retry_02_three_consecutive_failures(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_task,
    ):
        """
        EP-RETRY-02: Three consecutive failures create retries.

        Steps:
        1. Task1 fails
        2. Task2 fails
        3. Task3 fails

        Assertions:
        - Retry Task4 created
        """
        # First task
        task1 = create_task()
        task1, run1 = persistence.atomic_claim_task(task1.task_id)
        persistence.update_task_run(run1.run_id, status=TaskRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_task(task1.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        task2 = retry_controller.on_task_failed(persistence.get_task(task1.task_id), persistence.get_task_run(run1.run_id))
        assert task2 is not None

        # Second task
        task2, run2 = persistence.atomic_claim_task(task2.task_id)
        persistence.update_task_run(run2.run_id, status=TaskRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_task(task2.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        task3 = retry_controller.on_task_failed(persistence.get_task(task2.task_id), persistence.get_task_run(run2.run_id))
        assert task3 is not None

        # Third task
        task3, run3 = persistence.atomic_claim_task(task3.task_id)
        persistence.update_task_run(run3.run_id, status=TaskRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_task(task3.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        task4 = retry_controller.on_task_failed(persistence.get_task(task3.task_id), persistence.get_task_run(run3.run_id))
        # Note: With default max_attempts=3, after 3 retries (chain length = 3), no more auto-retry
        # Chain: task1 -> task2 -> task3 -> task4 would be 4 attempts total
        # The chain length at task3 is 2, so one more retry is allowed
        assert task4 is not None

    def test_ep_retry_03_max_retries_exhausted(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_task,
    ):
        """
        EP-RETRY-03: Max retries exhausted.

        Steps:
        1. Task1-4 all fail (3 retries exhausted)

        Assertions:
        - No Task5 created automatically
        """
        # Create retry controller with max_attempts=3
        retry_controller = RetryController(persistence, queue_manager, max_attempts=3)

        # Original task
        task = create_task()

        # Simulate failure chain: original + 3 retries = 4 tasks total
        for i in range(4):
            task, run = persistence.atomic_claim_task(task.task_id)
            persistence.update_task_run(
                run.run_id,
                status=TaskRunStatus.FAILED,
                finished_at=datetime.utcnow().isoformat() + "Z",
            )
            persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

            next_task = retry_controller.on_task_failed(
                persistence.get_task(task.task_id),
                persistence.get_task_run(run.run_id),
            )

            if i < 3:
                assert next_task is not None, f"Expected retry at attempt {i + 1}"
                task = next_task
            else:
                # At attempt 4 (chain length = 3), no more auto-retry
                assert next_task is None, "Should not create auto-retry after max attempts"

    def test_ep_retry_04_manual_retry_after_max(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_task,
    ):
        """
        EP-RETRY-04: Manual retry after max reached.

        Steps:
        1. Max retries reached
        2. Manual retry API

        Assertions:
        - New Task created successfully
        """
        # Create retry controller with max_attempts=1 for quick test
        retry_controller = RetryController(persistence, queue_manager, max_attempts=1)

        # Original task
        task = create_task()
        task, run = persistence.atomic_claim_task(task.task_id)
        persistence.update_task_run(
            run.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # First automatic retry
        retry1 = retry_controller.on_task_failed(
            persistence.get_task(task.task_id),
            persistence.get_task_run(run.run_id),
        )
        assert retry1 is not None

        # Complete retry1 as failed
        retry1, run1 = persistence.atomic_claim_task(retry1.task_id)
        persistence.update_task_run(
            run1.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(retry1.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # No more auto-retry
        auto_retry = retry_controller.on_task_failed(
            persistence.get_task(retry1.task_id),
            persistence.get_task_run(run1.run_id),
        )
        assert auto_retry is None

        # Manual retry should still work
        manual_retry = retry_controller.manual_retry(run1.run_id)
        assert manual_retry is not None
        assert manual_retry.retry_of == retry1.task_id
        assert manual_retry.status == TaskStatus.QUEUED

    def test_ep_retry_05_retry_of_links_to_original(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_task,
    ):
        """
        EP-RETRY-05: retry_of field links to original.

        Steps:
        1. Task fails
        2. Retry task created

        Assertions:
        - retry_of field links to original
        """
        # Create and fail task
        original = create_task()
        original, run = persistence.atomic_claim_task(original.task_id)
        persistence.update_task_run(
            run.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(original.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry
        retry = retry_controller.on_task_failed(
            persistence.get_task(original.task_id),
            persistence.get_task_run(run.run_id),
        )

        # Verify link
        assert retry.retry_of == original.task_id

        # Verify chain
        chain_length = retry_controller.get_retry_count(retry.task_id)
        assert chain_length == 1  # One predecessor

    def test_ep_retry_06_backoff_increases_exponentially(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
    ):
        """
        EP-RETRY-06: Backoff delay increases exponentially.

        Assertions:
        - Backoff increases: base * 2^n
        """
        retry_controller = RetryController(
            persistence,
            queue_manager,
            base_delay_seconds=10,
        )

        # Calculate backoff for each attempt
        backoff_0 = retry_controller._calculate_backoff(0)  # 10 * 2^0 = 10
        backoff_1 = retry_controller._calculate_backoff(1)  # 10 * 2^1 = 20
        backoff_2 = retry_controller._calculate_backoff(2)  # 10 * 2^2 = 40

        assert backoff_0 == 10
        assert backoff_1 == 20
        assert backoff_2 == 40
        assert backoff_1 == backoff_0 * 2
        assert backoff_2 == backoff_1 * 2


# =============================================================================
# EP-SCHED: Schedule-Triggered Task Creation (skipped)
# =============================================================================


@pytest.mark.skip(reason="Schedule trigger tests require APScheduler integration (Phase 4+)")
class TestEPScheduleTriggered:
    """
    Schedule-triggered task creation.

    Scenario: Schedule cron fires, task created

    Note: These tests are skipped per TEST_STRATEGY.md Section 7.3.
    """

    def test_ep_sched_01_schedule_trigger_creates_task(self):
        """EP-SCHED-01: Schedule trigger creates task."""
        pass

    def test_ep_sched_02_disabled_schedule_no_task(self):
        """EP-SCHED-02: Disabled schedule doesn't create task."""
        pass

    def test_ep_sched_03_schedule_param_overrides(self):
        """EP-SCHED-03: Schedule param_overrides applied."""
        pass

    def test_ep_sched_04_last_triggered_at_updated(self):
        """EP-SCHED-04: last_triggered_at updated."""
        pass
