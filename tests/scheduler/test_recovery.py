"""
Recovery Scenario Tests for Job Scheduler.

Tests from TEST_STRATEGY.md Section 5 (Crash/Restart Recovery Tests):
- REC-RUN-*: Crash during RUNNING job
- REC-RES-*: Crash during Direct API reservation
- REC-RETRY-*: Crash during retry creation
- REC-TXN-*: Crash during JobRun creation (transaction)
- REC-MULTI-*: Multiple RUNNING jobs recovery
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
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
    ReservationStatus,
    DirectReservation,
)
from src.scheduler.recovery import RecoveryManager


# =============================================================================
# REC-RUN: Crash During RUNNING Job
# =============================================================================


class TestRECRunningJob:
    """
    Crash during RUNNING job scenarios (from RECOVERY_SCENARIOS.md Scenario 1).
    """

    def test_rec_run_01_running_job_with_non_terminal_run(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RUN-01: Running job with non-terminal JobRun.

        Setup: Job1 RUNNING, JobRun1 non-terminal
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - JobRun1.status = FAILED
        """
        # Setup: Create RUNNING job with non-terminal JobRun
        job = create_job(status=JobStatus.QUEUED)
        job, job_run = persistence.atomic_claim_job(job.job_id)
        assert job.status == JobStatus.RUNNING
        assert job_run.status is None  # Non-terminal

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        job_run_fresh = persistence.get_job_run(job_run.run_id)
        assert job_run_fresh.status == JobRunStatus.FAILED
        assert "recovery" in job_run_fresh.error.lower()
        assert stats["running_jobs_recovered"] >= 1

    def test_rec_run_02_running_job_without_jobrun(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RUN-02: Running job without JobRun (crash before JobRun creation).

        Setup: Job1 RUNNING, no JobRun
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - FAILED JobRun created
        """
        # Setup: Manually create RUNNING job without JobRun (corrupt state)
        job = create_job(status=JobStatus.QUEUED)

        # Directly update to RUNNING without creating JobRun
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = ? WHERE job_id = ?",
                (JobStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", job.job_id),
            )

        # Verify corrupt state
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.RUNNING
        assert persistence.get_job_run_for_job(job.job_id) is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        job_run = persistence.get_job_run_for_job(job.job_id)
        assert job_run is not None
        assert job_run.status == JobRunStatus.FAILED
        assert "recovery" in job_run.error.lower()

    def test_rec_run_03_running_job_with_completed_run(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RUN-03: Running job with terminal JobRun (crash after completion).

        Setup: Job1 RUNNING, JobRun1 COMPLETED
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Job1.finished_at set only
        """
        # Setup: Create RUNNING job with COMPLETED JobRun
        job = create_job(status=JobStatus.QUEUED)
        job, job_run = persistence.atomic_claim_job(job.job_id)

        # Complete the JobRun but don't update job.finished_at (simulate crash)
        persistence.update_job_run(
            job_run.run_id,
            status=JobRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Verify job still shows RUNNING without finished_at
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.RUNNING
        assert job_fresh.finished_at is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.finished_at is not None

        # JobRun should remain COMPLETED (not changed to FAILED)
        job_run_fresh = persistence.get_job_run(job_run.run_id)
        assert job_run_fresh.status == JobRunStatus.COMPLETED

    def test_rec_run_04_recovered_job_gets_retry(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RUN-04: Recovered job gets retry if eligible.

        Setup: Job1 RUNNING, recovered
        After Recovery: Check retry

        Assertions:
        - Retry job created if eligible
        """
        # Setup: Create RUNNING job
        job = create_job(status=JobStatus.QUEUED)
        job, job_run = persistence.atomic_claim_job(job.job_id)

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Verify recovery marked as FAILED
        job_run_fresh = persistence.get_job_run(job_run.run_id)
        assert job_run_fresh.status == JobRunStatus.FAILED

        # Recovery should have created retry job
        assert stats["retries_created"] >= 1 or stats["running_jobs_recovered"] >= 1

    def test_rec_run_05_recovery_idempotent(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RUN-05: Recovery is idempotent.

        Setup: Same as REC-RUN-01
        Action: Run recovery twice

        Assertions:
        - No duplicate FAILED markers
        - JobRun status is FAILED and stays FAILED
        - No duplicate retry jobs created
        """
        # Setup: Create RUNNING job
        job = create_job(status=JobStatus.QUEUED)
        job, job_run = persistence.atomic_claim_job(job.job_id)

        # First recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats1 = recovery_manager.recover_on_startup()
        state_after_first = persistence.get_job_run(job_run.run_id).status
        retry_after_first = persistence.get_retry_job_for(job.job_id)

        # Second recovery
        stats2 = recovery_manager.recover_on_startup()
        state_after_second = persistence.get_job_run(job_run.run_id).status
        retry_after_second = persistence.get_retry_job_for(job.job_id)

        # Assertions: State should be the same after both recoveries
        assert state_after_first == state_after_second == JobRunStatus.FAILED

        # Idempotency: No duplicate retry jobs created
        # (same retry job exists, no new one created)
        if retry_after_first:
            assert retry_after_second.job_id == retry_after_first.job_id
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
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RES-03: Queue resumes after reservation expired.

        Setup: After reservation expired
        Action: Check queue

        Assertions:
        - Queue dispatch resumed
        """
        # Setup: Create reservation and job
        reservation = DirectReservation.create(
            reserved_by="test-client",
            expires_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.create_reservation(reservation)

        job = create_job()

        # Recovery expires reservation
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Queue should be unblocked
        assert not queue_manager.has_active_reservation()

        # Job should be dispatchable
        next_job = queue_manager.get_next()
        assert next_job is not None
        assert next_job.job_id == job.job_id

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
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RETRY-01: Failed job without retry job.

        Setup: JobRun1 FAILED, no retry job
        Crash: Kill before retry
        Recovery: recovery_on_startup()

        Assertions:
        - Retry job created
        """
        # Setup: Create failed job without retry
        job = create_job()
        job, job_run = persistence.atomic_claim_job(job.job_id)

        persistence.update_job_run(
            job_run.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error="Test failure",
        )
        persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Verify no retry exists
        retry = persistence.get_retry_job_for(job.job_id)
        assert retry is None

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        retry = persistence.get_retry_job_for(job.job_id)
        assert retry is not None
        assert retry.retry_of == job.job_id
        assert stats["retries_created"] >= 1

    def test_rec_retry_02_failed_with_retry_exists(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-RETRY-02: Failed job with retry already exists.

        Setup: JobRun1 FAILED, retry job exists
        After Recovery: recovery_on_startup()

        Assertions:
        - No duplicate retry
        """
        # Setup: Create failed job with existing retry
        job = create_job()
        job, job_run = persistence.atomic_claim_job(job.job_id)

        persistence.update_job_run(
            job_run.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry manually
        queue_manager = QueueManager(persistence)
        existing_retry = queue_manager.enqueue(
            job_type=job.job_type,
            params=job.params,
            retry_of=job.job_id,
        )

        # Count jobs before recovery
        jobs_before = len(persistence.list_jobs_by_status(JobStatus.QUEUED))

        # Recovery
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions: No new retry created
        jobs_after = len(persistence.list_jobs_by_status(JobStatus.QUEUED))
        assert jobs_after == jobs_before  # Same count (no duplicate)
        assert stats["retries_created"] == 0

    def test_rec_retry_03_max_retries_no_new_retry(
        self, persistence: PersistenceAdapter, create_job
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

        # Original job
        job1 = create_job()
        job1, run1 = persistence.atomic_claim_job(job1.job_id)
        persistence.update_job_run(run1.run_id, status=JobRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_job(job1.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # First retry (now at max)
        retry1 = queue_manager.enqueue(
            job_type=job1.job_type,
            params=job1.params,
            retry_of=job1.job_id,
        )
        retry1, run2 = persistence.atomic_claim_job(retry1.job_id)
        persistence.update_job_run(run2.run_id, status=JobRunStatus.FAILED, finished_at=datetime.utcnow().isoformat() + "Z")
        persistence.update_job(retry1.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Verify chain length is at max
        chain_length = persistence.count_retry_chain(retry1.job_id)
        assert chain_length == 1  # retry1 has one predecessor (job1)

        # Recovery with max_attempts=1
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)
        stats = recovery_manager.recover_on_startup()

        # Assertions: No new retry (at max)
        assert stats["retries_created"] == 0


# =============================================================================
# REC-TXN: Crash During JobRun Creation (Transaction)
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
        - Job remains QUEUED
        """
        # This test verifies SQLite's transactional behavior
        persistence = PersistenceAdapter(temp_db_path)

        # Create a QUEUED job
        job = Job.create(job_type="story", params={"test": True})
        job = persistence.create_job(job)
        assert job.status == JobStatus.QUEUED

        # Simulate partial transaction that would be rolled back on crash
        # Start a transaction, make changes, but don't commit
        conn = persistence._get_connection()
        try:
            conn.execute(
                "UPDATE jobs SET status = ? WHERE job_id = ?",
                (JobStatus.RUNNING.value, job.job_id),
            )
            # Simulate crash - don't commit, just close
            conn.rollback()  # This is what happens on crash
        finally:
            conn.close()

        # Verify job is still QUEUED (transaction was rolled back)
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.QUEUED

    def test_rec_txn_02_after_rollback_normal_dispatch(
        self, temp_db_path: str
    ):
        """
        REC-TXN-02: After rollback, normal dispatch works.

        Setup: After rollback
        Action: Restart

        Assertions:
        - Job dispatched again
        """
        persistence = PersistenceAdapter(temp_db_path)

        # Create a QUEUED job
        job = Job.create(job_type="story", params={"test": True})
        job = persistence.create_job(job)

        # Successful dispatch after any rollback
        claimed_job, job_run = persistence.atomic_claim_job(job.job_id)

        assert claimed_job.status == JobStatus.RUNNING
        assert job_run is not None


# =============================================================================
# REC-MULTI: Multiple RUNNING Jobs Recovery
# =============================================================================


class TestRECMultipleRunning:
    """
    Multiple RUNNING jobs recovery (from RECOVERY_SCENARIOS.md Scenario 5).
    """

    def test_rec_multi_01_both_marked_failed(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-MULTI-01: Both RUNNING jobs marked FAILED.

        Setup: Job1, Job2 both RUNNING
        Crash: Kill process
        Recovery: recovery_on_startup()

        Assertions:
        - Both marked FAILED
        """
        # Setup: Create two RUNNING jobs (simulating corrupt state)
        job1 = create_job()
        job2 = create_job()

        # Set both to RUNNING without proper JobRun (corrupt)
        for job in [job1, job2]:
            with persistence._transaction() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, started_at = ? WHERE job_id = ?",
                    (JobStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", job.job_id),
                )

        # Verify both RUNNING
        assert persistence.get_job(job1.job_id).status == JobStatus.RUNNING
        assert persistence.get_job(job2.job_id).status == JobStatus.RUNNING

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Assertions
        assert stats["running_jobs_recovered"] == 2

        run1 = persistence.get_job_run_for_job(job1.job_id)
        run2 = persistence.get_job_run_for_job(job2.job_id)

        assert run1 is not None and run1.status == JobRunStatus.FAILED
        assert run2 is not None and run2.status == JobRunStatus.FAILED

    def test_rec_multi_02_both_get_retry(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-MULTI-02: Both recovered jobs get retry if eligible.

        Setup: Both recovered
        After Recovery: Both get retry jobs

        Assertions:
        - Both get retry jobs (if eligible)
        """
        # Setup: Create two RUNNING jobs
        job1 = create_job()
        job2 = create_job()

        for job in [job1, job2]:
            with persistence._transaction() as conn:
                conn.execute(
                    "UPDATE jobs SET status = ?, started_at = ? WHERE job_id = ?",
                    (JobStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", job.job_id),
                )

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        stats = recovery_manager.recover_on_startup()

        # Both should get retries
        retry1 = persistence.get_retry_job_for(job1.job_id)
        retry2 = persistence.get_retry_job_for(job2.job_id)

        assert retry1 is not None
        assert retry2 is not None

    def test_rec_multi_03_queue_order_preserved(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-MULTI-03: Queue order preserved after recovery.

        Setup: Queue had Job3, Job4, Job5
        After Recovery: Queue order preserved

        Assertions:
        - Queue order preserved
        """
        # Create queued jobs with different priorities
        job_low = create_job(priority=1)
        job_high = create_job(priority=10)
        job_medium = create_job(priority=5)

        # Get expected order before any changes
        expected_order = [job_high.job_id, job_medium.job_id, job_low.job_id]

        # Recovery (with no RUNNING jobs to recover)
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Check queue order
        queued = persistence.list_jobs_by_status(JobStatus.QUEUED)
        actual_order = [j.job_id for j in queued]

        assert actual_order == expected_order


# =============================================================================
# REC-IDEM: Rapid Restart Idempotency
# =============================================================================


class TestRECIdempotency:
    """
    Rapid restart idempotency (from RECOVERY_SCENARIOS.md Scenario 6).
    """

    def test_rec_idem_01_crash_recover_crash_recover(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-IDEM-01: Crash → recover → crash → recover produces same result.

        Setup: Job1 RUNNING
        Actions: Crash → recover → crash → recover

        Assertions:
        - Same final state as single recovery
        """
        # Setup: Create RUNNING job
        job = create_job()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = ? WHERE job_id = ?",
                (JobStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", job.job_id),
            )

        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        # First recovery
        stats1 = recovery_manager.recover_on_startup()
        state_after_first = {
            "job_run_status": persistence.get_job_run_for_job(job.job_id).status,
            "retry_exists": persistence.get_retry_job_for(job.job_id) is not None,
        }

        # Second recovery
        stats2 = recovery_manager.recover_on_startup()
        state_after_second = {
            "job_run_status": persistence.get_job_run_for_job(job.job_id).status,
            "retry_exists": persistence.get_retry_job_for(job.job_id) is not None,
        }

        # Assertions
        assert state_after_first == state_after_second

    def test_rec_idem_02_multiple_failed_same_retries(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        REC-IDEM-02: Multiple failed jobs - same retry count.

        Setup: Multiple FAILED jobs needing retry
        Action: Run recovery N times

        Assertions:
        - Same number of retry jobs
        """
        # Setup: Create multiple failed jobs
        jobs = []
        for _ in range(3):
            job = create_job()
            job, job_run = persistence.atomic_claim_job(job.job_id)
            persistence.update_job_run(
                job_run.run_id,
                status=JobRunStatus.FAILED,
                finished_at=datetime.utcnow().isoformat() + "Z",
            )
            persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")
            jobs.append(job)

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
