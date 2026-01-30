"""
Execution Path Scenario Tests for Job Scheduler.

Tests from TEST_STRATEGY.md Section 4 (Execution Path Scenario Tests):
- EP-NORM-*: Normal queue execution
- EP-DIRECT-*: Direct API next-slot reservation (DEC-004)
- EP-RETRY-*: Retry semantics (DEC-007)
- EP-SCHED-*: Schedule-triggered job creation (skipped - requires APScheduler)

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
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
    ReservationStatus,
    ReservationConflictError,
)

from .conftest import MockJobHandler


# =============================================================================
# EP-NORM: Normal Queue Execution
# =============================================================================


class TestEPNormalExecution:
    """
    Normal queue execution scenarios.

    Scenario: Job created → queued → dispatched → executed → completed
    """

    def test_ep_norm_01_job_lifecycle(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockJobHandler,
        create_job,
    ):
        """
        EP-NORM-01: Job lifecycle - create, dispatch, complete.

        Steps:
        1. Create job
        2. Wait for dispatch
        3. Execute successfully

        Assertions:
        - Job: QUEUED → RUNNING
        - JobRun: COMPLETED
        """
        # Setup: Configure mock handler for success
        mock_handler.set_result(JobRunStatus.COMPLETED, exit_code=0)

        # Create job
        job = create_job(job_type="story", params={"test": True})
        assert job.status == JobStatus.QUEUED

        # Dispatch and execute
        result = dispatcher.dispatch_one()

        # Assertions
        assert result is not None
        executed_job, job_run = result

        assert executed_job.job_id == job.job_id
        assert job_run.status == JobRunStatus.COMPLETED
        assert job_run.exit_code == 0

        # Verify job state
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.RUNNING
        assert job_fresh.finished_at is not None

    def test_ep_norm_02_execution_order_matches_queue_order(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockJobHandler,
        create_job,
    ):
        """
        EP-NORM-02: Execution order matches queue order.

        Steps:
        1. Create 3 jobs with different priorities
        2. Execute all

        Assertions:
        - Execution order matches queue order (priority DESC)
        """
        # Setup: Configure mock handler for success
        mock_handler.set_result(JobRunStatus.COMPLETED)

        # Create jobs with different priorities
        job_low = create_job(priority=1)
        job_high = create_job(priority=10)
        job_medium = create_job(priority=5)

        # Track execution order
        execution_order = []

        # Execute all
        for _ in range(3):
            result = dispatcher.dispatch_one()
            if result:
                execution_order.append(result[0].job_id)

        # Assertions: Should be high → medium → low
        assert len(execution_order) == 3
        assert execution_order[0] == job_high.job_id
        assert execution_order[1] == job_medium.job_id
        assert execution_order[2] == job_low.job_id

    def test_ep_norm_03_cancel_before_dispatch(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        create_job,
    ):
        """
        EP-NORM-03: Cancel job before dispatch.

        Steps:
        1. Create job
        2. Cancel before dispatch

        Assertions:
        - Job: CANCELLED
        - No JobRun created
        """
        # Create job
        job = create_job()
        assert job.status == JobStatus.QUEUED

        # Cancel
        cancelled_job = queue_manager.cancel(job.job_id)

        # Assertions
        assert cancelled_job.status == JobStatus.CANCELLED

        # No JobRun should exist
        job_run = persistence.get_job_run_for_job(job.job_id)
        assert job_run is None

        # Dispatch should skip this job (queue is empty)
        result = dispatcher.dispatch_one()
        assert result is None


# =============================================================================
# EP-DIRECT: Direct API Next-Slot Reservation (DEC-004)
# =============================================================================


class TestEPDirectExecution:
    """
    Direct API next-slot reservation scenarios.

    Scenario: Direct API reserves slot, waits for running job, executes, queue resumes
    """

    def test_ep_direct_01_direct_executes_between_jobs(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockJobHandler,
        create_job,
    ):
        """
        EP-DIRECT-01: Direct executes between jobs.

        Steps:
        1. Job1 executed
        2. Direct API called (reserves slot internally)
        3. Direct executes
        4. Job2 dispatched

        Assertions:
        - Direct executes between Job1 and Job2
        """
        # Setup
        mock_handler.set_result(JobRunStatus.COMPLETED)

        # Create jobs
        job1 = create_job(priority=10)
        job2 = create_job(priority=5)

        execution_order = []

        # Execute job1
        result = dispatcher.dispatch_one()
        assert result is not None
        execution_order.append(("job1", result[0].job_id))

        # Direct execution (handles its own reservation)
        direct_job_run = dispatcher.execute_direct(
            job_type="direct",
            params={"direct": True},
            reserved_by="direct-client",
        )
        assert direct_job_run.status == JobRunStatus.COMPLETED
        execution_order.append(("direct", direct_job_run.job_id))

        # Now job2 can be dispatched
        result = dispatcher.dispatch_one()
        assert result is not None
        execution_order.append(("job2", result[0].job_id))

        # Verify order: job1 → direct → job2
        assert execution_order[0][0] == "job1"
        assert execution_order[1][0] == "direct"
        assert execution_order[2][0] == "job2"

    def test_ep_direct_02_empty_queue_direct_executes_immediately(
        self,
        persistence: PersistenceAdapter,
        dispatcher: Dispatcher,
        mock_handler: MockJobHandler,
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
        mock_handler.set_result(JobRunStatus.COMPLETED)

        # Verify queue is empty
        result = dispatcher.dispatch_one()
        assert result is None

        # Direct execution should work immediately
        job_run = dispatcher.execute_direct(
            job_type="direct",
            params={"direct": True},
            reserved_by="direct-client",
        )

        assert job_run.status == JobRunStatus.COMPLETED

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
        create_job,
    ):
        """
        EP-DIRECT-04: Queue paused during reservation.

        Steps:
        1. Direct reservation
        2. Job1 completes
        3. Verify queue paused

        Assertions:
        - Job2 not dispatched until reservation released
        """
        # Create job
        job = create_job()

        # Create reservation
        reservation = queue_manager.reserve_next_slot("direct-client")

        # Queue should be paused
        assert queue_manager.has_active_reservation()

        # Dispatch should not proceed
        result = dispatcher.dispatch_one()
        assert result is None

        # Job should still be QUEUED
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.QUEUED

    def test_ep_direct_05_queue_resumes_after_release(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
        mock_handler: MockJobHandler,
        create_job,
    ):
        """
        EP-DIRECT-05: Queue resumes after reservation released.

        Steps:
        1. Reservation released

        Assertions:
        - Queue dispatch resumes immediately
        """
        # Setup
        mock_handler.set_result(JobRunStatus.COMPLETED)

        # Create job
        job = create_job()

        # Create and release reservation
        reservation = queue_manager.reserve_next_slot("direct-client")
        queue_manager.release_reservation(reservation.reservation_id)

        # No active reservation
        assert not queue_manager.has_active_reservation()

        # Queue should resume
        result = dispatcher.dispatch_one()
        assert result is not None
        assert result[0].job_id == job.job_id


# =============================================================================
# EP-RETRY: Retry Semantics (DEC-007)
# =============================================================================


class TestEPRetrySemantics:
    """
    Retry semantics scenarios.

    Scenario: Job fails, automatic retry up to 3, then manual required
    """

    def test_ep_retry_01_failed_job_creates_retry(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_job,
        create_job_run,
    ):
        """
        EP-RETRY-01: Failed job creates retry.

        Steps:
        1. Job1 fails

        Assertions:
        - Retry Job2 created automatically
        """
        # Create and fail job
        job1 = create_job()
        job1, job_run1 = persistence.atomic_claim_job(job1.job_id)

        persistence.update_job_run(
            job_run1.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error="Test failure",
        )
        persistence.update_job(job1.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Trigger retry evaluation
        job1_fresh = persistence.get_job(job1.job_id)
        job_run1_fresh = persistence.get_job_run(job_run1.run_id)

        retry_job = retry_controller.on_job_failed(job1_fresh, job_run1_fresh)

        # Assertions
        assert retry_job is not None
        assert retry_job.job_id != job1.job_id
        assert retry_job.retry_of == job1.job_id
        assert retry_job.status == JobStatus.QUEUED

    def test_ep_retry_02_three_consecutive_failures(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_job,
    ):
        """
        EP-RETRY-02: Three consecutive failures create retries.

        Steps:
        1. Job1 fails
        2. Job2 fails
        3. Job3 fails

        Assertions:
        - Retry Job4 created
        """
        # First job
        job1 = create_job()
        job1, run1 = persistence.atomic_claim_job(job1.job_id)
        persistence.update_job_run(run1.run_id, status=JobRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_job(job1.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        job2 = retry_controller.on_job_failed(persistence.get_job(job1.job_id), persistence.get_job_run(run1.run_id))
        assert job2 is not None

        # Second job
        job2, run2 = persistence.atomic_claim_job(job2.job_id)
        persistence.update_job_run(run2.run_id, status=JobRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_job(job2.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        job3 = retry_controller.on_job_failed(persistence.get_job(job2.job_id), persistence.get_job_run(run2.run_id))
        assert job3 is not None

        # Third job
        job3, run3 = persistence.atomic_claim_job(job3.job_id)
        persistence.update_job_run(run3.run_id, status=JobRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_job(job3.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        job4 = retry_controller.on_job_failed(persistence.get_job(job3.job_id), persistence.get_job_run(run3.run_id))
        # Note: With default max_attempts=3, after 3 retries (chain length = 3), no more auto-retry
        # Chain: job1 -> job2 -> job3 -> job4 would be 4 attempts total
        # The chain length at job3 is 2, so one more retry is allowed
        assert job4 is not None

    def test_ep_retry_03_max_retries_exhausted(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_job,
    ):
        """
        EP-RETRY-03: Max retries exhausted.

        Steps:
        1. Job1-4 all fail (3 retries exhausted)

        Assertions:
        - No Job5 created automatically
        """
        # Create retry controller with max_attempts=3
        retry_controller = RetryController(persistence, queue_manager, max_attempts=3)

        # Original job
        job = create_job()

        # Simulate failure chain: original + 3 retries = 4 jobs total
        for i in range(4):
            job, run = persistence.atomic_claim_job(job.job_id)
            persistence.update_job_run(
                run.run_id,
                status=JobRunStatus.FAILED,
                finished_at=datetime.utcnow().isoformat() + "Z",
            )
            persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

            next_job = retry_controller.on_job_failed(
                persistence.get_job(job.job_id),
                persistence.get_job_run(run.run_id),
            )

            if i < 3:
                assert next_job is not None, f"Expected retry at attempt {i + 1}"
                job = next_job
            else:
                # At attempt 4 (chain length = 3), no more auto-retry
                assert next_job is None, "Should not create auto-retry after max attempts"

    def test_ep_retry_04_manual_retry_after_max(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_job,
    ):
        """
        EP-RETRY-04: Manual retry after max reached.

        Steps:
        1. Max retries reached
        2. Manual retry API

        Assertions:
        - New Job created successfully
        """
        # Create retry controller with max_attempts=1 for quick test
        retry_controller = RetryController(persistence, queue_manager, max_attempts=1)

        # Original job
        job = create_job()
        job, run = persistence.atomic_claim_job(job.job_id)
        persistence.update_job_run(
            run.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # First automatic retry
        retry1 = retry_controller.on_job_failed(
            persistence.get_job(job.job_id),
            persistence.get_job_run(run.run_id),
        )
        assert retry1 is not None

        # Complete retry1 as failed
        retry1, run1 = persistence.atomic_claim_job(retry1.job_id)
        persistence.update_job_run(
            run1.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(retry1.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # No more auto-retry
        auto_retry = retry_controller.on_job_failed(
            persistence.get_job(retry1.job_id),
            persistence.get_job_run(run1.run_id),
        )
        assert auto_retry is None

        # Manual retry should still work
        manual_retry = retry_controller.manual_retry(run1.run_id)
        assert manual_retry is not None
        assert manual_retry.retry_of == retry1.job_id
        assert manual_retry.status == JobStatus.QUEUED

    def test_ep_retry_05_retry_of_links_to_original(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
        create_job,
    ):
        """
        EP-RETRY-05: retry_of field links to original.

        Steps:
        1. Job fails
        2. Retry job created

        Assertions:
        - retry_of field links to original
        """
        # Create and fail job
        original = create_job()
        original, run = persistence.atomic_claim_job(original.job_id)
        persistence.update_job_run(
            run.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(original.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry
        retry = retry_controller.on_job_failed(
            persistence.get_job(original.job_id),
            persistence.get_job_run(run.run_id),
        )

        # Verify link
        assert retry.retry_of == original.job_id

        # Verify chain
        chain_length = retry_controller.get_retry_count(retry.job_id)
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
# EP-SCHED: Schedule-Triggered Job Creation (skipped)
# =============================================================================


@pytest.mark.skip(reason="Schedule trigger tests require APScheduler integration (Phase 4+)")
class TestEPScheduleTriggered:
    """
    Schedule-triggered job creation.

    Scenario: Schedule cron fires, job created

    Note: These tests are skipped per TEST_STRATEGY.md Section 7.3.
    """

    def test_ep_sched_01_schedule_trigger_creates_job(self):
        """EP-SCHED-01: Schedule trigger creates job."""
        pass

    def test_ep_sched_02_disabled_schedule_no_job(self):
        """EP-SCHED-02: Disabled schedule doesn't create job."""
        pass

    def test_ep_sched_03_schedule_param_overrides(self):
        """EP-SCHED-03: Schedule param_overrides applied."""
        pass

    def test_ep_sched_04_last_triggered_at_updated(self):
        """EP-SCHED-04: last_triggered_at updated."""
        pass
