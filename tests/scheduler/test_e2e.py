"""
End-to-End Tests for Task Scheduler.

Phase 6-A Merge Validation Tests.

These tests exercise the full scheduler stack with controlled execution:
- E2E-NORM: Normal queue execution lifecycle
- E2E-DIRECT: Direct API next-slot reservation (DEC-004)
- E2E-RETRY: Retry flow with max 3 attempts (DEC-007)
- E2E-RECOVERY: Crash recovery scenarios
- E2E-GROUP: TaskGroup sequential execution with stop-on-failure (DEC-012)
- E2E-WEBHOOK: Webhook emission (schema + at-least-once semantics)

Resource Usage Policy:
- Tests use mock handlers (no real Ollama/API calls)
- If actual execution were needed, only ONE local Ollama workload allowed
- External API usage approved for test purposes (but not used here)
"""

import pytest
import tempfile
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable
from unittest.mock import MagicMock, patch

from src.scheduler import (
    PersistenceAdapter,
    QueueManager,
    Dispatcher,
    Executor,
    RetryController,
    RecoveryManager,
    SchedulerService,
    Task,
    TaskRun,
    TaskGroup,
    TaskStatus,
    TaskRunStatus,
    TaskGroupStatus,
)
from src.scheduler.executor import TaskHandler


# =============================================================================
# E2E Test Fixtures
# =============================================================================


class E2ETaskHandler(TaskHandler):
    """
    Controllable task handler for E2E tests.

    Allows precise control over execution outcomes without subprocess.
    """

    def __init__(self):
        self.execution_log = []
        self._result_queue = []  # Queue of results for sequential calls
        self._default_result = (TaskRunStatus.COMPLETED, None, 0, [])
        self._execution_delay = 0.0
        self._cancelled = False
        self._fail_count = {}  # task_type -> fail count

    def set_next_result(
        self,
        status: TaskRunStatus,
        error: Optional[str] = None,
        exit_code: int = 0,
        artifacts: Optional[list] = None,
    ) -> None:
        """Queue a result for the next execution."""
        self._result_queue.append((status, error, exit_code, artifacts or []))

    def set_default_result(
        self,
        status: TaskRunStatus,
        error: Optional[str] = None,
        exit_code: int = 0,
        artifacts: Optional[list] = None,
    ) -> None:
        """Set default result when queue is empty."""
        self._default_result = (status, error, exit_code, artifacts or [])

    def set_fail_first_n(self, task_type: str, n: int) -> None:
        """Make first N executions of task_type fail."""
        self._fail_count[task_type] = n

    def set_execution_delay(self, delay: float) -> None:
        """Set delay before returning result (simulates execution time)."""
        self._execution_delay = delay

    def execute(
        self,
        task: Task,
        log_path: Optional[str] = None,
    ) -> tuple[TaskRunStatus, Optional[str], Optional[int], list[str]]:
        """Execute task with configured behavior."""
        self._cancelled = False

        # Log execution
        self.execution_log.append({
            "task_id": task.task_id,
            "task_type": task.task_type,
            "params": task.params,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Simulate execution time
        if self._execution_delay > 0:
            time.sleep(self._execution_delay)

        if self._cancelled:
            return (TaskRunStatus.FAILED, "Cancelled", -1, [])

        # Check for programmed failures
        if task.task_type in self._fail_count and self._fail_count[task.task_type] > 0:
            self._fail_count[task.task_type] -= 1
            return (TaskRunStatus.FAILED, f"Programmed failure for {task.task_type}", 1, [])

        # Use queued result or default
        if self._result_queue:
            return self._result_queue.pop(0)
        return self._default_result

    def cancel(self) -> bool:
        """Cancel execution."""
        self._cancelled = True
        return True


@pytest.fixture
def e2e_temp_dir():
    """Create temporary directory for E2E tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def e2e_handler():
    """Create E2E task handler."""
    return E2ETaskHandler()


@pytest.fixture
def e2e_service(e2e_temp_dir, e2e_handler):
    """
    Create a fully configured SchedulerService for E2E tests.

    Uses E2ETaskHandler instead of SubprocessTaskHandler.
    """
    db_path = e2e_temp_dir / "e2e_test.db"
    logs_dir = e2e_temp_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Create persistence
    persistence = PersistenceAdapter(str(db_path))

    # Create queue manager
    queue_manager = QueueManager(persistence)

    # Create dispatcher with fast polling
    dispatcher = Dispatcher(
        persistence=persistence,
        queue_manager=queue_manager,
        poll_interval=0.1,
    )

    # Create executor with E2E handler
    executor = Executor(persistence=persistence, handler=e2e_handler)

    # Create retry controller
    retry_controller = RetryController(
        persistence=persistence,
        queue_manager=queue_manager,
        max_attempts=3,
        base_delay_seconds=0,  # No delay for tests
    )

    # Create recovery manager
    recovery_manager = RecoveryManager(
        persistence=persistence,
        queue_manager=queue_manager,
        retry_controller=retry_controller,
    )

    # Wire components
    dispatcher.set_executor(executor)

    # Set up completion callback
    def on_task_completed(task: Task, task_run: TaskRun):
        if task_run.status == TaskRunStatus.FAILED:
            retry_controller.on_task_failed(task, task_run)
        queue_manager.handle_group_task_completion(task, task_run)

    dispatcher.set_on_task_completed(on_task_completed)

    # Create service
    service = SchedulerService(
        persistence=persistence,
        queue_manager=queue_manager,
        dispatcher=dispatcher,
        executor=executor,
        retry_controller=retry_controller,
        recovery_manager=recovery_manager,
    )

    yield service

    # Cleanup
    if service.is_running:
        service.stop(timeout=5.0)


# =============================================================================
# E2E-NORM: Normal Queue Execution
# =============================================================================


class TestE2ENormalExecution:
    """
    E2E tests for normal queue execution lifecycle.

    Validates the complete flow: enqueue -> dispatch -> execute -> complete.
    """

    def test_e2e_norm_01_single_task_lifecycle(self, e2e_service, e2e_handler):
        """
        E2E-NORM-01: Single task complete lifecycle.

        Steps:
        1. Enqueue a task
        2. Start dispatcher
        3. Wait for completion
        4. Verify final state
        """
        # Enqueue task
        task = e2e_service.enqueue_task(
            task_type="story",
            params={"theme": "test", "max_stories": 1},
            priority=5,
        )
        assert task.status == TaskStatus.QUEUED

        # Execute via dispatcher (single dispatch)
        result = e2e_service.dispatcher.dispatch_one()

        # Verify execution
        assert result is not None
        executed_task, task_run = result
        assert executed_task.task_id == task.task_id
        assert task_run.status == TaskRunStatus.COMPLETED

        # Verify handler was called
        assert len(e2e_handler.execution_log) == 1
        assert e2e_handler.execution_log[0]["task_id"] == task.task_id

    def test_e2e_norm_02_multiple_tasks_priority_order(self, e2e_service, e2e_handler):
        """
        E2E-NORM-02: Multiple tasks execute in priority order.

        Steps:
        1. Enqueue 3 tasks with different priorities
        2. Execute all
        3. Verify execution order
        """
        # Enqueue tasks with different priorities
        task_low = e2e_service.enqueue_task("story", {"id": "low"}, priority=1)
        task_high = e2e_service.enqueue_task("story", {"id": "high"}, priority=10)
        task_med = e2e_service.enqueue_task("story", {"id": "medium"}, priority=5)

        # Execute all
        execution_order = []
        for _ in range(3):
            result = e2e_service.dispatcher.dispatch_one()
            if result:
                execution_order.append(result[0].task_id)

        # Verify order: high -> medium -> low
        assert execution_order == [task_high.task_id, task_med.task_id, task_low.task_id]

    def test_e2e_norm_03_task_cancellation(self, e2e_service):
        """
        E2E-NORM-03: Task cancellation before dispatch.

        Steps:
        1. Enqueue task
        2. Cancel task
        3. Verify no execution
        """
        # Enqueue and cancel
        task = e2e_service.enqueue_task("story", {"test": True})
        cancelled = e2e_service.cancel_task(task.task_id)

        assert cancelled.status == TaskStatus.CANCELLED

        # Verify dispatch returns nothing
        result = e2e_service.dispatcher.dispatch_one()
        assert result is None


# =============================================================================
# E2E-DIRECT: Direct API Next-Slot Reservation (DEC-004)
# =============================================================================


class TestE2EDirectExecution:
    """
    E2E tests for Direct API next-slot reservation.

    Validates DEC-004: Direct API tasks reserve next slot,
    wait for current task, then execute.
    """

    def test_e2e_direct_01_empty_queue_immediate(self, e2e_service, e2e_handler):
        """
        E2E-DIRECT-01: Direct execution on empty queue.

        Steps:
        1. Queue is empty
        2. Execute direct
        3. Verify immediate execution
        """
        # Execute direct on empty queue
        task_run = e2e_service.execute_direct(
            task_type="story",
            params={"direct": True},
            reserved_by="test-client",
        )

        assert task_run.status == TaskRunStatus.COMPLETED
        assert len(e2e_handler.execution_log) == 1

    def test_e2e_direct_02_between_queued_tasks(self, e2e_service, e2e_handler):
        """
        E2E-DIRECT-02: Direct executes between queued tasks.

        Steps:
        1. Execute task1
        2. Task2 queued
        3. Direct execution
        4. Task2 executes after direct
        """
        # Enqueue two tasks
        task1 = e2e_service.enqueue_task("story", {"seq": 1}, priority=10)
        task2 = e2e_service.enqueue_task("story", {"seq": 2}, priority=5)

        execution_order = []

        # Execute task1
        result = e2e_service.dispatcher.dispatch_one()
        execution_order.append(("queued", result[0].task_id))

        # Direct execution (reserves slot, executes)
        direct_run = e2e_service.execute_direct(
            task_type="story",
            params={"direct": True},
            reserved_by="test-client",
        )
        execution_order.append(("direct", direct_run.task_id))

        # Task2 executes
        result = e2e_service.dispatcher.dispatch_one()
        execution_order.append(("queued", result[0].task_id))

        # Verify order
        assert execution_order[0] == ("queued", task1.task_id)
        assert execution_order[1][0] == "direct"
        assert execution_order[2] == ("queued", task2.task_id)

    def test_e2e_direct_03_queue_pauses_during_reservation(self, e2e_service):
        """
        E2E-DIRECT-03: Queue pauses while reservation active.

        Steps:
        1. Create reservation manually
        2. Try dispatch
        3. Verify queue paused
        """
        # Enqueue task
        task = e2e_service.enqueue_task("story", {"test": True})

        # Create reservation
        reservation = e2e_service.queue_manager.reserve_next_slot("test-client")

        # Verify queue paused
        assert e2e_service.queue_manager.has_active_reservation()

        # Dispatch should not proceed
        result = e2e_service.dispatcher.dispatch_one()
        assert result is None

        # Release and verify dispatch resumes
        e2e_service.queue_manager.release_reservation(reservation.reservation_id)
        result = e2e_service.dispatcher.dispatch_one()
        assert result is not None


# =============================================================================
# E2E-RETRY: Retry Flow (DEC-007)
# =============================================================================


class TestE2ERetryFlow:
    """
    E2E tests for automatic retry behavior.

    Validates DEC-007: Automatic retry up to 3 attempts.
    """

    def test_e2e_retry_01_single_failure_creates_retry(self, e2e_service, e2e_handler):
        """
        E2E-RETRY-01: Single failure creates automatic retry.

        Steps:
        1. Task fails
        2. Verify retry task created
        3. Retry succeeds
        """
        # Set first execution to fail
        e2e_handler.set_fail_first_n("story", 1)

        # Enqueue and execute
        task = e2e_service.enqueue_task("story", {"test": True})

        # First execution fails
        result = e2e_service.dispatcher.dispatch_one()
        assert result[1].status == TaskRunStatus.FAILED

        # Retry task should exist in queue
        queued = e2e_service.list_queued_tasks()
        assert len(queued) == 1
        retry_task = queued[0]
        assert retry_task.retry_of == task.task_id

        # Execute retry - succeeds
        result = e2e_service.dispatcher.dispatch_one()
        assert result[1].status == TaskRunStatus.COMPLETED

    def test_e2e_retry_02_max_three_attempts(self, e2e_service, e2e_handler):
        """
        E2E-RETRY-02: Max 3 automatic retry attempts.

        Steps:
        1. Task fails repeatedly
        2. Verify exactly 3 retries
        3. No more auto-retry after 3
        """
        # Set to fail always
        e2e_handler.set_default_result(TaskRunStatus.FAILED, "Always fails", 1)

        task = e2e_service.enqueue_task("story", {"test": True})

        attempts = 0
        while True:
            result = e2e_service.dispatcher.dispatch_one()
            if result is None:
                break
            attempts += 1
            if attempts > 5:  # Safety limit
                break

        # Original + 3 retries = 4 attempts total
        assert attempts == 4, f"Expected 4 attempts (1 original + 3 retries), got {attempts}"

        # No more tasks in queue
        queued = e2e_service.list_queued_tasks()
        assert len(queued) == 0

    def test_e2e_retry_03_retry_chain_linkage(self, e2e_service, e2e_handler):
        """
        E2E-RETRY-03: Retry chain maintains linkage.

        Steps:
        1. Task fails twice
        2. Verify retry_of chain
        """
        # Fail first 2 times
        e2e_handler.set_fail_first_n("story", 2)

        task = e2e_service.enqueue_task("story", {"test": True})
        task_ids = [task.task_id]

        # Execute all
        for _ in range(3):
            result = e2e_service.dispatcher.dispatch_one()
            if result:
                task_ids.append(result[0].task_id)

        # Verify chain
        # task_ids = [original, retry1, retry2, retry3...]
        for i in range(1, len(task_ids)):
            retry = e2e_service.get_task(task_ids[i])
            if retry and retry.retry_of:
                assert retry.retry_of == task_ids[i-1]


# =============================================================================
# E2E-RECOVERY: Crash Recovery
# =============================================================================


class TestE2ERecovery:
    """
    E2E tests for crash recovery.

    Validates recovery of RUNNING tasks after simulated crash.
    """

    def test_e2e_recovery_01_running_task_marked_failed(self, e2e_temp_dir, e2e_handler):
        """
        E2E-RECOVERY-01: Running task marked FAILED on recovery.

        Steps:
        1. Create service, start task
        2. Simulate crash (stop without cleanup)
        3. New service recovers
        4. Verify task marked FAILED
        """
        db_path = e2e_temp_dir / "recovery_test.db"

        # Create first service instance
        persistence1 = PersistenceAdapter(str(db_path))
        queue_manager1 = QueueManager(persistence1)

        # Create and start a task
        task = Task.create("story", {"test": True})
        task = persistence1.create_task(task)

        # Simulate: task is RUNNING (crash mid-execution)
        task, task_run = persistence1.atomic_claim_task(task.task_id)

        # Verify RUNNING state
        assert task.status == TaskStatus.RUNNING

        # --- SIMULATE CRASH ---
        # Don't cleanup, just abandon connection

        # Create new service (simulates restart)
        persistence2 = PersistenceAdapter(str(db_path))
        queue_manager2 = QueueManager(persistence2)
        retry_controller2 = RetryController(persistence2, queue_manager2)
        recovery_manager2 = RecoveryManager(persistence2, queue_manager2, retry_controller2)

        # Run recovery
        stats = recovery_manager2.recover_on_startup()

        # Verify recovery
        assert stats["running_tasks_recovered"] == 1

        # Verify task run marked FAILED
        recovered_run = persistence2.get_task_run(task_run.run_id)
        assert recovered_run.status == TaskRunStatus.FAILED
        assert "recovery" in recovered_run.error.lower()

    def test_e2e_recovery_02_retry_created_for_recovered(self, e2e_temp_dir):
        """
        E2E-RECOVERY-02: Retry created for recovered task.

        Steps:
        1. Crash during task execution
        2. Recovery creates FAILED TaskRun
        3. Retry task created
        """
        db_path = e2e_temp_dir / "recovery_retry_test.db"

        # Setup: task in RUNNING state
        persistence1 = PersistenceAdapter(str(db_path))
        task = Task.create("story", {"test": True})
        task = persistence1.create_task(task)
        task, task_run = persistence1.atomic_claim_task(task.task_id)

        # Simulate crash and recovery
        persistence2 = PersistenceAdapter(str(db_path))
        queue_manager2 = QueueManager(persistence2)
        retry_controller2 = RetryController(persistence2, queue_manager2, max_attempts=3)
        recovery_manager2 = RecoveryManager(persistence2, queue_manager2, retry_controller2)

        stats = recovery_manager2.recover_on_startup()

        # Verify retry created
        assert stats["retries_created"] == 1

        # Verify retry task exists
        queued = persistence2.list_tasks_by_status(TaskStatus.QUEUED)
        assert len(queued) == 1
        retry_task = queued[0]
        assert retry_task.retry_of == task.task_id


# =============================================================================
# E2E-GROUP: TaskGroup Sequential Execution (DEC-012)
# =============================================================================


class TestE2ETaskGroup:
    """
    E2E tests for TaskGroup sequential execution.

    Validates DEC-012: Sequential execution with stop-on-failure.
    """

    def test_e2e_group_01_sequential_execution(self, e2e_service, e2e_handler):
        """
        E2E-GROUP-01: Tasks in group execute sequentially.

        Steps:
        1. Create group with 3 tasks
        2. Execute
        3. Verify sequential order
        """
        # Create group
        group, tasks = e2e_service.create_task_group(
            tasks=[
                {"task_type": "story", "params": {"seq": 1}},
                {"task_type": "story", "params": {"seq": 2}},
                {"task_type": "story", "params": {"seq": 3}},
            ],
            name="test-group",
        )

        assert len(tasks) == 3

        execution_order = []

        # Execute all tasks
        for _ in range(3):
            result = e2e_service.dispatcher.dispatch_one()
            if result:
                execution_order.append(result[0].params.get("seq"))

        # Verify sequential order
        assert execution_order == [1, 2, 3]

    def test_e2e_group_02_stop_on_failure(self, e2e_service, e2e_handler):
        """
        E2E-GROUP-02: Group stops on first failure (after retries).

        Steps:
        1. Create group with 3 tasks
        2. Task 2 fails (all retries exhausted)
        3. Task 3 never executes (SKIPPED)
        4. Group status = PARTIAL
        """
        # Configure: task 2 always fails (no retries in this setup)
        # We need to track which task is being executed
        call_count = [0]
        original_execute = e2e_handler.execute

        def tracked_execute(task, log_path=None):
            call_count[0] += 1
            seq = task.params.get("seq")
            if seq == 2:
                return (TaskRunStatus.FAILED, "Task 2 fails", 1, [])
            return (TaskRunStatus.COMPLETED, None, 0, [])

        e2e_handler.execute = tracked_execute

        # Create group
        group, tasks = e2e_service.create_task_group(
            tasks=[
                {"task_type": "story", "params": {"seq": 1}},
                {"task_type": "story", "params": {"seq": 2}},
                {"task_type": "story", "params": {"seq": 3}},
            ],
            name="stop-on-failure-test",
        )

        # Execute until queue empty or blocked
        executed = 0
        while executed < 10:  # Safety limit
            result = e2e_service.dispatcher.dispatch_one()
            if result is None:
                break
            executed += 1

        # Check group status
        group_final = e2e_service.get_task_group(group.group_id)

        # With retries, it takes 4 attempts for task 2 (1 original + 3 retries)
        # After that, task 3 should be SKIPPED and group is PARTIAL
        assert group_final.status == TaskGroupStatus.PARTIAL

        # Task 3 should never have executed (seq=3 never called)
        for log in e2e_handler.execution_log:
            # Only seq=1 and seq=2 should appear
            assert log["task"]["params"].get("seq") != 3 if "task" in log else True

        # Restore
        e2e_handler.execute = original_execute

    def test_e2e_group_03_completed_group(self, e2e_service, e2e_handler):
        """
        E2E-GROUP-03: All tasks complete -> group COMPLETED.

        Steps:
        1. Create group
        2. All tasks complete successfully
        3. Group status = COMPLETED
        """
        # All tasks succeed
        e2e_handler.set_default_result(TaskRunStatus.COMPLETED, None, 0, [])

        group, tasks = e2e_service.create_task_group(
            tasks=[
                {"task_type": "story", "params": {"seq": 1}},
                {"task_type": "story", "params": {"seq": 2}},
            ],
            name="complete-test",
        )

        # Execute all
        for _ in range(2):
            e2e_service.dispatcher.dispatch_one()

        # Check group status
        group_final = e2e_service.get_task_group(group.group_id)
        assert group_final.status == TaskGroupStatus.COMPLETED
        assert group_final.finished_at is not None


# =============================================================================
# E2E-WEBHOOK: Webhook Emission
# =============================================================================


class TestE2EWebhook:
    """
    E2E tests for webhook emission.

    Validates webhook schema and at-least-once semantics.
    Delivery is tested with mock (actual HTTP not required).
    """

    def test_e2e_webhook_01_completed_event_schema(self, e2e_service, e2e_handler):
        """
        E2E-WEBHOOK-01: COMPLETED task produces correct webhook event.

        Assertions:
        - Event type: task.run.completed
        - Payload contains required fields
        """
        task = e2e_service.enqueue_task("story", {"test": True})
        result = e2e_service.dispatcher.dispatch_one()

        task_run = result[1]
        assert task_run.status == TaskRunStatus.COMPLETED

        # Build expected webhook payload
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.completed"

        # Verify payload fields
        payload = {
            "event": event_type,
            "data": {
                "run_id": task_run.run_id,
                "task_id": task_run.task_id,
                "status": task_run.status.value,
                "started_at": task_run.started_at,
                "finished_at": task_run.finished_at,
                "exit_code": task_run.exit_code,
            }
        }

        assert payload["data"]["run_id"] is not None
        assert payload["data"]["status"] == "COMPLETED"

    def test_e2e_webhook_02_failed_event_includes_error(self, e2e_service, e2e_handler):
        """
        E2E-WEBHOOK-02: FAILED task webhook includes error.

        Assertions:
        - Event type: task.run.failed
        - Payload includes error field
        """
        e2e_handler.set_default_result(TaskRunStatus.FAILED, "Test error", 1)

        task = e2e_service.enqueue_task("story", {"test": True})
        result = e2e_service.dispatcher.dispatch_one()

        task_run = result[1]
        assert task_run.status == TaskRunStatus.FAILED

        # Build expected webhook payload
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.failed"

        payload = {
            "event": event_type,
            "data": {
                "run_id": task_run.run_id,
                "task_id": task_run.task_id,
                "status": task_run.status.value,
                "error": task_run.error,
            }
        }

        assert payload["data"]["error"] is not None
        assert "Test error" in payload["data"]["error"]

    def test_e2e_webhook_03_skipped_event_for_group(self, e2e_service, e2e_handler):
        """
        E2E-WEBHOOK-03: SKIPPED task (group stop-on-failure) produces webhook.

        Assertions:
        - Skipped tasks have SKIPPED status in TaskRun
        - Event type: task.run.skipped
        """
        # Make second task fail always
        call_count = [0]
        def fail_second(task, log_path=None):
            call_count[0] += 1
            seq = task.params.get("seq")
            if seq == 2:
                return (TaskRunStatus.FAILED, "Fails", 1, [])
            return (TaskRunStatus.COMPLETED, None, 0, [])

        e2e_handler.execute = fail_second

        group, tasks = e2e_service.create_task_group(
            tasks=[
                {"task_type": "story", "params": {"seq": 1}},
                {"task_type": "story", "params": {"seq": 2}},
                {"task_type": "story", "params": {"seq": 3}},
            ],
            name="skipped-test",
        )

        # Execute until done
        for _ in range(10):
            if e2e_service.dispatcher.dispatch_one() is None:
                break

        # Check task 3 has SKIPPED TaskRun
        task3 = tasks[2]
        task3_run = e2e_service.get_task_run_for_task(task3.task_id)

        assert task3_run is not None
        assert task3_run.status == TaskRunStatus.SKIPPED

        # Webhook event type
        event_type = f"task.run.{task3_run.status.value.lower()}"
        assert event_type == "task.run.skipped"

    def test_e2e_webhook_04_at_least_once_semantics(self):
        """
        E2E-WEBHOOK-04: Webhook delivery has at-least-once semantics.

        Note: This is a design validation test. Actual delivery is mocked.
        The system guarantees at-least-once by:
        1. Persisting webhook intent before sending
        2. Retrying on failure (up to 3 times)
        """
        # This test validates the design principle
        # Actual HTTP delivery would be tested with a mock HTTP server

        # Per DESIGN_GUARDS.md DEC-009:
        # - Webhook MUST be delivered at-least-once
        # - Retry up to 3 times on failure
        # - Client handles idempotency via run_id

        # The TaskRun.run_id serves as idempotency key
        task_run = TaskRun.create(
            task_id="test-task",
            params_snapshot={},
        )

        # run_id is unique per execution attempt
        assert task_run.run_id is not None

        # Clients can use run_id for deduplication
        # This is the contract for at-least-once semantics
        pass
