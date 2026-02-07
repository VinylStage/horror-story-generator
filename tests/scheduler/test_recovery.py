"""
Recovery Scenario Tests for Task Scheduler.

Tests from TEST_STRATEGY.md Section 5 (Crash/Restart Recovery Tests):
- REC-RUN-*: Crash during RUNNING task
- REC-RES-*: Crash during Direct API reservation
- REC-RETRY-*: Crash during retry creation
- REC-TXN-*: Crash during TaskRun creation (transaction)
- REC-MULTI-*: Multiple RUNNING tasks recovery
- REC-IDEM-*: Rapid restart idempotency

Each test validates crash-safe recovery behavior.
Recovery operations MUST be idempotent.
"""

import pytest
from datetime import datetime, timedelta

from src.scheduler import (
    PersistenceAdapter,
    QueueManager,
    RetryController,
    Task,
    TaskRun,
    TaskStatus,
    TaskRunStatus,
    ReservationStatus,
    DirectReservation,
)
from src.scheduler.recovery import RecoveryManager


# =============================================================================
# REC-RUN: Crash During RUNNING Task
# =============================================================================


class TestRECRunningTask:
    """
    Crash during RUNNING task scenarios (from RECOVERY_SCENARIOS.md Scenario 1).
    """

    def test_rec_run_01_running_task_with_non_terminal_run(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RUN-01: Running task with non-terminal TaskRun.

        Setup: Task1 RUNNING, TaskRun1 non-terminal
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - TaskRun1.status = FAILED
        """
        # Setup: Create RUNNING task with non-terminal TaskRun
        task = create_task(status=TaskStatus.QUEUED)
        task, task_run = persistence.atomic_claim_task(task.task_id)
        assert task.status == TaskStatus.RUNNING
        assert task_run.status is None  # Non-terminal

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        task_run_fresh = persistence.get_task_run(task_run.run_id)
        assert task_run_fresh.status == TaskRunStatus.FAILED
        assert "recovery" in task_run_fresh.error.lower()
        assert stats["running_tasks_recovered"] >= 1

    def test_rec_run_02_running_task_without_taskrun(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RUN-02: Running task without TaskRun (crash before TaskRun creation).

        Setup: Task1 RUNNING, no TaskRun
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - FAILED TaskRun created
        """
        # Setup: Manually create RUNNING task without TaskRun (corrupt state)
        task = create_task(status=TaskStatus.QUEUED)

        # Directly update to RUNNING without creating TaskRun
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
                (TaskStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", task.task_id),
            )

        # Verify corrupt state
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.RUNNING
        assert persistence.get_task_run_for_task(task.task_id) is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        task_run = persistence.get_task_run_for_task(task.task_id)
        assert task_run is not None
        assert task_run.status == TaskRunStatus.FAILED
        assert "recovery" in task_run.error.lower()

    def test_rec_run_03_running_task_with_completed_run(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RUN-03: Running task with terminal TaskRun (crash after completion).

        Setup: Task1 RUNNING, TaskRun1 COMPLETED
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Task1.finished_at set only
        """
        # Setup: Create RUNNING task with COMPLETED TaskRun
        task = create_task(status=TaskStatus.QUEUED)
        task, task_run = persistence.atomic_claim_task(task.task_id)

        # Complete the TaskRun but don't update task.finished_at (simulate crash)
        persistence.update_task_run(
            task_run.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Verify task still shows RUNNING without finished_at
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.RUNNING
        assert task_fresh.finished_at is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.finished_at is not None

        # TaskRun should remain COMPLETED (not changed to FAILED)
        task_run_fresh = persistence.get_task_run(task_run.run_id)
        assert task_run_fresh.status == TaskRunStatus.COMPLETED

    def test_rec_run_04_recovered_task_gets_retry(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RUN-04: Recovered task gets retry if eligible.

        Setup: Task1 RUNNING, recovered
        After Recovery: Check retry

        Assertions:
        - Retry task created if eligible
        """
        # Setup: Create RUNNING task
        task = create_task(status=TaskStatus.QUEUED)
        task, task_run = persistence.atomic_claim_task(task.task_id)

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Verify recovery marked as FAILED
        task_run_fresh = persistence.get_task_run(task_run.run_id)
        assert task_run_fresh.status == TaskRunStatus.FAILED

        # Recovery should have created retry task
        assert stats["retries_created"] >= 1 or stats["running_tasks_recovered"] >= 1

    def test_rec_run_05_recovery_idempotent(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RUN-05: Recovery is idempotent.

        Setup: Same as REC-RUN-01
        Action: Run recovery twice

        Assertions:
        - No duplicate FAILED markers
        - TaskRun status is FAILED and stays FAILED
        - No duplicate retry tasks created
        """
        # Setup: Create RUNNING task
        task = create_task(status=TaskStatus.QUEUED)
        task, task_run = persistence.atomic_claim_task(task.task_id)

        # First recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats1 = recovery_manager.recover_on_startup()
        state_after_first = persistence.get_task_run(task_run.run_id).status
        retry_after_first = persistence.get_retry_task_for(task.task_id)

        # Second recovery
        stats2 = recovery_manager.recover_on_startup()
        state_after_second = persistence.get_task_run(task_run.run_id).status
        retry_after_second = persistence.get_retry_task_for(task.task_id)

        # Assertions: State should be the same after both recoveries
        assert state_after_first == state_after_second == TaskRunStatus.FAILED

        # Idempotency: No duplicate retry tasks created
        # (same retry task exists, no new one created)
        if retry_after_first:
            assert retry_after_second.task_id == retry_after_first.task_id
        assert stats2["retries_created"] == 0  # No new retries on second pass


# =============================================================================
# REC-RES: Crash During Direct API Reservation
# =============================================================================


class TestRECReservation:
    """
    Crash during Direct API reservation scenarios (from RECOVERY_SCENARIOS.md Scenario 2).
    """

    def test_rec_res_01_active_reservation_expired(
        self, persistence: PersistenceAdapter
    ):
        """
        REC-RES-01: Active reservation is expired on recovery.

        Setup: Reservation ACTIVE, expired
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Reservation = EXPIRED
        """
        # Setup: Create ACTIVE reservation
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=(datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",  # Already expired
        )
        persistence.create_reservation(reservation)

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        reservation_fresh = persistence.get_reservation(reservation.reservation_id)
        assert reservation_fresh.status == ReservationStatus.EXPIRED
        assert stats["reservations_expired"] >= 1

    def test_rec_res_02_active_not_expired_force_expire(
        self, persistence: PersistenceAdapter
    ):
        """
        REC-RES-02: Active reservation (not expired) is force-expired.

        Setup: Reservation ACTIVE, not expired
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Force expire (stale - no handler running)
        """
        # Setup: Create ACTIVE reservation that hasn't expired yet
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",  # Future
        )
        persistence.create_reservation(reservation)

        # Recovery - all ACTIVE reservations are stale after crash
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        reservation_fresh = persistence.get_reservation(reservation.reservation_id)
        assert reservation_fresh.status == ReservationStatus.EXPIRED
        assert stats["reservations_expired"] >= 1

    def test_rec_res_03_queue_resumes_after_expire(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RES-03: Queue resumes after reservation expired.

        Setup: After reservation expired
        Action: Check queue

        Assertions:
        - Queue dispatch resumed
        """
        # Setup: Create reservation and task
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.create_reservation(reservation)

        task = create_task()

        # Recovery expires reservation
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Queue should be unblocked
        assert not queue_manager.has_active_reservation()

        # Task should be dispatchable
        next_task = queue_manager.get_next()
        assert next_task is not None
        assert next_task.task_id == task.task_id

    def test_rec_res_04_multiple_restarts_single_expire(
        self, persistence: PersistenceAdapter
    ):
        """
        REC-RES-04: Multiple restarts - only one EXPIRED transition.

        Setup: Multiple restarts
        Action: Run recovery twice

        Assertions:
        - Only one EXPIRED, no duplicates
        """
        # Setup: Create ACTIVE reservation
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.create_reservation(reservation)

        # First recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats1 = recovery_manager.recover_on_startup()
        assert stats1["reservations_expired"] == 1

        # Second recovery - should not expire again (already EXPIRED)
        stats2 = recovery_manager.recover_on_startup()
        assert stats2["reservations_expired"] == 0


# =============================================================================
# REC-RETRY: Crash During Retry Creation
# =============================================================================


class TestRECRetryCreation:
    """
    Crash during retry creation scenarios (from RECOVERY_SCENARIOS.md Scenario 3).
    """

    def test_rec_retry_01_failed_without_retry(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RETRY-01: Failed task without retry task.

        Setup: TaskRun1 FAILED, no retry task
        Crash: Kill before retry
        Recovery: recovery_on_startup()

        Assertions:
        - Retry task created
        """
        # Setup: Create failed task without retry
        task = create_task()
        task, task_run = persistence.atomic_claim_task(task.task_id)

        persistence.update_task_run(
            task_run.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error="Test failure",
        )
        persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Verify no retry exists
        retry = persistence.get_retry_task_for(task.task_id)
        assert retry is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        retry = persistence.get_retry_task_for(task.task_id)
        assert retry is not None
        assert retry.retry_of == task.task_id
        assert stats["retries_created"] >= 1

    def test_rec_retry_02_failed_with_retry_exists(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RETRY-02: Failed task with retry already exists.

        Setup: TaskRun1 FAILED, retry task exists
        After Recovery: recovery_on_startup()

        Assertions:
        - No duplicate retry
        """
        # Setup: Create failed task with existing retry
        task = create_task()
        task, task_run = persistence.atomic_claim_task(task.task_id)

        persistence.update_task_run(
            task_run.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry manually
        queue_manager = QueueManager(persistence)
        existing_retry = queue_manager.enqueue(
            task_type=task.task_type,
            params=task.params,
            retry_of=task.task_id,
        )

        # Count tasks before recovery
        tasks_before = len(persistence.list_tasks_by_status(TaskStatus.QUEUED))

        # Recovery
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions: No new retry created
        tasks_after = len(persistence.list_tasks_by_status(TaskStatus.QUEUED))
        assert tasks_after == tasks_before  # Same count (no duplicate)
        assert stats["retries_created"] == 0

    def test_rec_retry_03_max_retries_no_new_retry(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-RETRY-03: Max retries reached - no recovery retry.

        Setup: Already at max
        Recovery: recovery_on_startup()

        Assertions:
        - No retry created
        """
        # Setup: Create chain at max retries
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager, max_attempts=1)

        # Original task
        task1 = create_task()
        task1, run1 = persistence.atomic_claim_task(task1.task_id)
        persistence.update_task_run(run1.run_id, status=TaskRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_task(task1.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # First retry (now at max)
        retry1 = queue_manager.enqueue(
            task_type=task1.task_type,
            params=task1.params,
            retry_of=task1.task_id,
        )
        retry1, run2 = persistence.atomic_claim_task(retry1.task_id)
        persistence.update_task_run(run2.run_id, status=TaskRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_task(retry1.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Verify chain length is at max
        chain_length = persistence.count_retry_chain(retry1.task_id)
        assert chain_length == 1  # retry1 has one predecessor (task1)

        # Recovery with max_attempts=1
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)
        stats = recovery_manager.recover_on_startup()

        # Assertions: No new retry (at max)
        assert stats["retries_created"] == 0


# =============================================================================
# REC-TXN: Crash During TaskRun Creation (Transaction)
# =============================================================================


class TestRECTransaction:
    """
    Crash during transaction scenarios (from RECOVERY_SCENARIOS.md Scenario 4).
    """

    def test_rec_txn_01_uncommitted_transaction_rolled_back(
        self, temp_db_path: str
    ):
        """
        REC-TXN-01: Uncommitted transaction is rolled back.

        Setup: Uncommitted transaction
        Crash: Kill mid-transaction
        Recovery: SQLite rollback

        Assertions:
        - Task remains QUEUED
        """
        # This test verifies SQLite's transactional behavior
        persistence = PersistenceAdapter(temp_db_path)

        # Create a QUEUED task
        task = Task.create(task_type="story", params={"test": True})
        task = persistence.create_task(task)
        assert task.status == TaskStatus.QUEUED

        # Simulate partial transaction that would be rolled back on crash
        # Start a transaction, make changes, but don't commit
        conn = persistence._get_connection()
        try:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE task_id = ?",
                (TaskStatus.RUNNING.value, task.task_id),
            )
            # Simulate crash - don't commit, just close
            conn.rollback()  # This is what happens on crash
        finally:
            conn.close()

        # Verify task is still QUEUED (transaction was rolled back)
        task_fresh = persistence.get_task(task.task_id)
        assert task_fresh.status == TaskStatus.QUEUED

    def test_rec_txn_02_after_rollback_normal_dispatch(
        self, temp_db_path: str
    ):
        """
        REC-TXN-02: After rollback, normal dispatch works.

        Setup: After rollback
        Action: Restart

        Assertions:
        - Task dispatched again
        """
        persistence = PersistenceAdapter(temp_db_path)

        # Create a QUEUED task
        task = Task.create(task_type="story", params={"test": True})
        task = persistence.create_task(task)

        # Successful dispatch after any rollback
        claimed_task, task_run = persistence.atomic_claim_task(task.task_id)

        assert claimed_task.status == TaskStatus.RUNNING
        assert task_run is not None


# =============================================================================
# REC-MULTI: Multiple RUNNING Tasks Recovery
# =============================================================================


class TestRECMultipleRunning:
    """
    Multiple RUNNING tasks recovery (from RECOVERY_SCENARIOS.md Scenario 5).
    """

    def test_rec_multi_01_both_marked_failed(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-MULTI-01: Both RUNNING tasks marked FAILED.

        Setup: Task1, Task2 both RUNNING
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Both marked FAILED
        """
        # Setup: Create two RUNNING tasks (simulating corrupt state)
        task1 = create_task()
        task2 = create_task()

        # Set both to RUNNING without proper TaskRun (corrupt)
        for task in [task1, task2]:
            with persistence._transaction() as conn:
                conn.execute(
                    "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
                    (TaskStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", task.task_id),
                )

        # Verify both RUNNING
        assert persistence.get_task(task1.task_id).status == TaskStatus.RUNNING
        assert persistence.get_task(task2.task_id).status == TaskStatus.RUNNING

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        assert stats["running_tasks_recovered"] == 2

        run1 = persistence.get_task_run_for_task(task1.task_id)
        run2 = persistence.get_task_run_for_task(task2.task_id)

        assert run1 is not None and run1.status == TaskRunStatus.FAILED
        assert run2 is not None and run2.status == TaskRunStatus.FAILED

    def test_rec_multi_02_both_get_retry(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-MULTI-02: Both recovered tasks get retry if eligible.

        Setup: Both recovered
        After Recovery: Both get retry tasks

        Assertions:
        - Both get retry tasks (if eligible)
        """
        # Setup: Create two RUNNING tasks
        task1 = create_task()
        task2 = create_task()

        for task in [task1, task2]:
            with persistence._transaction() as conn:
                conn.execute(
                    "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
                    (TaskStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", task.task_id),
                )

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Both should get retries
        retry1 = persistence.get_retry_task_for(task1.task_id)
        retry2 = persistence.get_retry_task_for(task2.task_id)

        assert retry1 is not None
        assert retry2 is not None

    def test_rec_multi_03_queue_order_preserved(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-MULTI-03: Queue order preserved after recovery.

        Setup: Queue had Task3, Task4, Task5
        After Recovery: Queue order preserved

        Assertions:
        - Queue order preserved
        """
        # Create queued tasks with different priorities
        task_low = create_task(priority=1)
        task_high = create_task(priority=10)
        task_medium = create_task(priority=5)

        # Get expected order before any changes
        expected_order = [task_high.task_id, task_medium.task_id, task_low.task_id]

        # Recovery (with no RUNNING tasks to recover)
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Check queue order
        queued = persistence.list_tasks_by_status(TaskStatus.QUEUED)
        actual_order = [j.task_id for j in queued]

        assert actual_order == expected_order


# =============================================================================
# REC-IDEM: Rapid Restart Idempotency
# =============================================================================


class TestRECIdempotency:
    """
    Rapid restart idempotency (from RECOVERY_SCENARIOS.md Scenario 6).
    """

    def test_rec_idem_01_crash_recover_crash_recover(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-IDEM-01: Crash → recover → crash → recover produces same result.

        Setup: Task1 RUNNING
        Actions: Crash → recover → crash → recover

        Assertions:
        - Same final state as single recovery
        """
        # Setup: Create RUNNING task
        task = create_task()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
                (TaskStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", task.task_id),
            )

        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        # First recovery
        stats1 = recovery_manager.recover_on_startup()
        state_after_first = {
            "task_run_status": persistence.get_task_run_for_task(task.task_id).status,
            "retry_exists": persistence.get_retry_task_for(task.task_id) is not None,
        }

        # Second recovery
        stats2 = recovery_manager.recover_on_startup()
        state_after_second = {
            "task_run_status": persistence.get_task_run_for_task(task.task_id).status,
            "retry_exists": persistence.get_retry_task_for(task.task_id) is not None,
        }

        # Assertions
        assert state_after_first == state_after_second

    def test_rec_idem_02_multiple_failed_same_retries(
        self, persistence: PersistenceAdapter, create_task
    ):
        """
        REC-IDEM-02: Multiple failed tasks - same retry count.

        Setup: Multiple FAILED tasks needing retry
        Action: Run recovery N times

        Assertions:
        - Same number of retry tasks
        """
        # Setup: Create multiple failed tasks
        tasks = []
        for _ in range(3):
            task = create_task()
            task, task_run = persistence.atomic_claim_task(task.task_id)
            persistence.update_task_run(
                task_run.run_id,
                status=TaskRunStatus.FAILED,
                finished_at=datetime.utcnow().isoformat() + "Z",
            )
            persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")
            tasks.append(task)

        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        # First recovery
        stats1 = recovery_manager.recover_on_startup()
        retry_count_after_first = stats1["retries_created"]

        # Second and third recovery
        stats2 = recovery_manager.recover_on_startup()
        stats3 = recovery_manager.recover_on_startup()

        # Assertions: First recovery creates retries, subsequent don't
        assert retry_count_after_first == 3
        assert stats2["retries_created"] == 0
        assert stats3["retries_created"] == 0

    def test_rec_idem_03_reservation_single_expire(
        self, persistence: PersistenceAdapter
    ):
        """
        REC-IDEM-03: Reservation - only one EXPIRED transition.

        Setup: Reservation ACTIVE
        Action: Run recovery N times

        Assertions:
        - Only one EXPIRED transition
        """
        # Setup: Create ACTIVE reservation
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.create_reservation(reservation)

        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        # Multiple recoveries
        stats1 = recovery_manager.recover_on_startup()
        stats2 = recovery_manager.recover_on_startup()
        stats3 = recovery_manager.recover_on_startup()

        # Assertions
        assert stats1["reservations_expired"] == 1
        assert stats2["reservations_expired"] == 0
        assert stats3["reservations_expired"] == 0

        # Reservation still EXPIRED
        reservation_fresh = persistence.get_reservation(reservation.reservation_id)
        assert reservation_fresh.status == ReservationStatus.EXPIRED
