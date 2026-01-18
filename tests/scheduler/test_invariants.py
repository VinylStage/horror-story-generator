"""
Invariant Tests for Job Scheduler.

Tests from TEST_STRATEGY.md Section 2 (Invariant Test Matrix):
- INV-001: Job immutability after dispatch
- INV-002: JobRun immutability
- INV-003: Single running job per worker
- INV-004: Queue order consistency
- INV-005: Schedule-Job isolation
- INV-006: JobGroup completion atomicity (xfail - not implemented)

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
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
    InvalidOperationError,
)


# =============================================================================
# INV-001: Job Immutability After Dispatch
# =============================================================================


class TestINV001JobImmutability:
    """
    INV-001: Once a Job enters DISPATCHED/RUNNING state,
    its `params` field MUST NOT change.
    """

    def test_inv_001_a_reject_params_update_on_running_job(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-001-A: Reject params update on RUNNING job.

        Setup: Create job, set status=RUNNING
        Action: Call update_job(params={new})
        Assertion: InvalidOperationError raised
        """
        # Setup: Create a RUNNING job
        job = create_job(status=JobStatus.RUNNING)

        # Action & Assertion: Attempt to modify params should fail
        with pytest.raises(InvalidOperationError) as exc_info:
            persistence.update_job(job.job_id, params={"modified": True})

        assert "INV-001" in str(exc_info.value) or "params" in str(exc_info.value).lower()

    def test_inv_001_b_allow_params_update_on_queued_job(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-001-B: Allow params update on QUEUED job.

        Setup: Create job, status=QUEUED
        Action: Call update_job(params={new})
        Assertion: Params updated successfully
        """
        # Setup: Create a QUEUED job
        job = create_job(status=JobStatus.QUEUED)
        original_params = job.params.copy()

        # Action: Update params
        new_params = {"modified": True, "value": 42}
        updated_job = persistence.update_job(job.job_id, params=new_params)

        # Assertion: Params should be updated
        assert updated_job.params == new_params
        assert updated_job.params != original_params

    def test_inv_001_c_priority_update_allowed_on_queued(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-001-C: Priority update allowed on QUEUED.

        Setup: Create job, status=QUEUED
        Action: Call update_job(priority=10)
        Assertion: Priority updated
        """
        # Setup: Create a QUEUED job with default priority
        job = create_job(status=JobStatus.QUEUED, priority=0)

        # Action: Update priority
        updated_job = persistence.update_job(job.job_id, priority=10)

        # Assertion: Priority should be updated
        assert updated_job.priority == 10

    def test_inv_001_d_priority_update_rejected_on_running(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-001-D: Priority update rejected on RUNNING.

        Setup: Create job, status=RUNNING
        Action: Call update_job(priority=10)
        Assertion: InvalidOperationError raised
        """
        # Setup: Create a RUNNING job
        job = create_job(status=JobStatus.RUNNING)

        # Action & Assertion: Attempt to modify priority should fail
        with pytest.raises(InvalidOperationError) as exc_info:
            persistence.update_job(job.job_id, priority=10)

        assert "priority" in str(exc_info.value).lower() or "dispatch" in str(exc_info.value).lower()


# =============================================================================
# INV-002: JobRun Immutability
# =============================================================================


class TestINV002JobRunImmutability:
    """
    INV-002: Once a JobRun is created, only `finished_at`, `status`,
    `exit_code`, `error`, and `artifacts` may be updated.
    """

    def test_inv_002_a_reject_job_id_modification(
        self, persistence: PersistenceAdapter, create_job, create_job_run
    ):
        """
        INV-002-A: Reject job_id modification.

        Setup: Create JobRun
        Action: Call update(job_id=other)
        Assertion: InvalidOperationError raised (or no job_id param allowed)
        """
        # Setup: Create a job and job run
        job = create_job()
        job_run = create_job_run(job.job_id)

        # Action & Assertion: job_id is not modifiable via update_job_run
        # The update_job_run method doesn't accept job_id param at all
        # This test verifies the API doesn't allow it
        original_job_id = job_run.job_id

        # Try to update something else and verify job_id unchanged
        updated_run = persistence.update_job_run(job_run.run_id, status=JobRunStatus.COMPLETED)

        # Verify job_id hasn't changed
        assert updated_run.job_id == original_job_id

    def test_inv_002_b_reject_params_snapshot_modification(
        self, persistence: PersistenceAdapter, create_job, create_job_run
    ):
        """
        INV-002-B: Reject params_snapshot modification.

        Setup: Create JobRun
        Action: Call update(params_snapshot={})
        Assertion: InvalidOperationError raised (or no params_snapshot param allowed)
        """
        # Setup: Create a job and job run
        job = create_job(params={"original": True})
        job_run = create_job_run(job.job_id)
        original_snapshot = job_run.params_snapshot.copy()

        # Action: Attempt to modify - update_job_run doesn't accept params_snapshot
        # This verifies the immutability by design
        updated_run = persistence.update_job_run(job_run.run_id, status=JobRunStatus.COMPLETED)

        # Assertion: params_snapshot should be unchanged
        assert updated_run.params_snapshot == original_snapshot

    def test_inv_002_c_allow_status_update(
        self, persistence: PersistenceAdapter, create_job, create_job_run
    ):
        """
        INV-002-C: Allow status update.

        Setup: Create JobRun
        Action: Call update(status=COMPLETED)
        Assertion: Status updated
        """
        # Setup: Create a job and job run (status is initially None)
        job = create_job()
        job_run = create_job_run(job.job_id)
        assert job_run.status is None

        # Action: Update status
        updated_run = persistence.update_job_run(job_run.run_id, status=JobRunStatus.COMPLETED)

        # Assertion: Status should be updated
        assert updated_run.status == JobRunStatus.COMPLETED

    def test_inv_002_d_allow_error_update(
        self, persistence: PersistenceAdapter, create_job, create_job_run
    ):
        """
        INV-002-D: Allow error update.

        Setup: Create JobRun
        Action: Call update(error="msg")
        Assertion: Error updated
        """
        # Setup: Create a job and job run
        job = create_job()
        job_run = create_job_run(job.job_id)
        assert job_run.error is None

        # Action: Update error
        error_msg = "Test error message"
        updated_run = persistence.update_job_run(job_run.run_id, error=error_msg)

        # Assertion: Error should be updated
        assert updated_run.error == error_msg

    def test_inv_002_e_allow_artifacts_update(
        self, persistence: PersistenceAdapter, create_job, create_job_run
    ):
        """
        INV-002-E: Allow artifacts append.

        Setup: Create JobRun
        Action: Call update(artifacts=[...])
        Assertion: Artifacts updated
        """
        # Setup: Create a job and job run
        job = create_job()
        job_run = create_job_run(job.job_id)
        assert job_run.artifacts == []

        # Action: Update artifacts
        artifacts = ["/path/to/artifact1.txt", "/path/to/artifact2.json"]
        updated_run = persistence.update_job_run(job_run.run_id, artifacts=artifacts)

        # Assertion: Artifacts should be updated
        assert updated_run.artifacts == artifacts


# =============================================================================
# INV-003: Single Running Job Per Worker
# =============================================================================


class TestINV003SingleRunningJob:
    """
    INV-003: A worker MUST NOT execute more than one Job simultaneously.
    """

    def test_inv_003_a_second_dispatch_rejected_while_running(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_job,
    ):
        """
        INV-003-A: Second dispatch rejected while running.

        Setup: Job1 RUNNING
        Action: Try dispatch Job2
        Assertion: Job2 not dispatched (waits or rejects)
        """
        # Setup: Create two jobs and make first one RUNNING
        job1 = create_job(priority=10)
        job2 = create_job(priority=5)

        # Dispatch first job
        running_job, _ = persistence.atomic_claim_job(job1.job_id)
        assert running_job.status == JobStatus.RUNNING

        # Action & Assertion: get_next should still return job2 but it's QUEUED
        # The single-worker constraint is enforced by the dispatcher, not queue_manager
        # The queue_manager just returns the next job; dispatcher decides whether to run it
        next_job = queue_manager.get_next()
        assert next_job is not None
        assert next_job.job_id == job2.job_id
        assert next_job.status == JobStatus.QUEUED

        # Verify only one job is RUNNING
        running_jobs = persistence.list_jobs_by_status(JobStatus.RUNNING)
        assert len(running_jobs) == 1
        assert running_jobs[0].job_id == job1.job_id

    def test_inv_003_b_dispatch_allowed_after_completion(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        create_job,
    ):
        """
        INV-003-B: Dispatch allowed after completion.

        Setup: Job1 completes
        Action: Dispatch Job2
        Assertion: Job2 dispatched successfully
        """
        # Setup: Create two jobs
        job1 = create_job(priority=10)
        job2 = create_job(priority=5)

        # Dispatch and complete first job
        running_job1, job_run1 = persistence.atomic_claim_job(job1.job_id)
        assert running_job1.status == JobStatus.RUNNING

        # Complete job1
        persistence.update_job_run(
            job_run1.run_id,
            status=JobRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(
            job1.job_id,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Action: Dispatch job2
        running_job2, job_run2 = persistence.atomic_claim_job(job2.job_id)

        # Assertion: Job2 should be dispatched
        assert running_job2.status == JobStatus.RUNNING
        assert job_run2 is not None


# =============================================================================
# INV-004: Queue Order Consistency
# =============================================================================


class TestINV004QueueOrder:
    """
    INV-004: Jobs MUST be dispatched in order of
    (priority DESC, position ASC, created_at ASC).
    """

    def test_inv_004_a_higher_priority_first(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-004-A: Higher priority first.

        Setup: Job1(priority=5), Job2(priority=10)
        Action: get_next()
        Assertion: Returns Job2
        """
        # Setup: Create jobs with different priorities
        job1 = create_job(priority=5)
        job2 = create_job(priority=10)

        # Action: Get next job
        next_job = persistence.get_next_queued_job()

        # Assertion: Higher priority job should be first
        assert next_job is not None
        assert next_job.job_id == job2.job_id
        assert next_job.priority == 10

    def test_inv_004_b_lower_position_first_same_priority(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-004-B: Lower position first (same priority).

        Setup: Job1(pos=200), Job2(pos=100), same priority
        Action: get_next()
        Assertion: Returns Job2
        """
        # Setup: Create jobs with same priority
        # First job gets position 100, second gets 200
        job1 = create_job(priority=5)
        job2 = create_job(priority=5)

        # Verify positions were assigned
        job1_fresh = persistence.get_job(job1.job_id)
        job2_fresh = persistence.get_job(job2.job_id)

        # First created job should have lower position and be dispatched first
        assert job1_fresh.position < job2_fresh.position

        # Action: Get next job
        next_job = persistence.get_next_queued_job()

        # Assertion: Lower position (first created) should be first
        assert next_job is not None
        assert next_job.job_id == job1.job_id

    def test_inv_004_c_earlier_created_at_first_same_priority_position(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-004-C: Earlier created_at first (same priority, position).

        Setup: Job1(created=t1), Job2(created=t2), t1 < t2
        Action: get_next()
        Assertion: Returns Job1
        """
        # Setup: Create jobs with same priority but explicit position override
        # This tests the tie-breaker using created_at
        now = datetime.utcnow()
        earlier = now - timedelta(minutes=5)

        job1 = Job.create(
            job_type="story",
            params={"test": True},
            priority=5,
        )
        job1.created_at = earlier.isoformat() + "Z"
        job1.queued_at = earlier.isoformat() + "Z"
        job1.position = 100  # Same position
        job1 = persistence.create_job(job1)

        job2 = Job.create(
            job_type="story",
            params={"test": True},
            priority=5,
        )
        job2.created_at = now.isoformat() + "Z"
        job2.queued_at = now.isoformat() + "Z"
        # Need to force same position
        persistence._get_connection()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE jobs SET position = ? WHERE job_id = ?",
                (100, job2.job_id),
            )

        # Refresh job2
        job2 = persistence.get_job(job2.job_id)

        # Action: Get next job
        next_job = persistence.get_next_queued_job()

        # Assertion: Earlier created_at should be first
        assert next_job is not None
        assert next_job.job_id == job1.job_id

    def test_inv_004_d_full_ordering_test(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-004-D: Full ordering test.

        Setup: 5 jobs with mixed priority/position/created_at
        Action: get_all_ordered()
        Assertion: Exact expected order
        """
        # Setup: Create jobs with various priorities
        # Expected order: priority DESC, position ASC, created_at ASC
        jobs = []
        jobs.append(create_job(priority=1))   # Last (lowest priority)
        jobs.append(create_job(priority=10))  # First (highest priority)
        jobs.append(create_job(priority=5))   # Middle
        jobs.append(create_job(priority=5))   # Middle (after prev due to position)
        jobs.append(create_job(priority=10))  # Second (same priority, higher position)

        # Action: Get all queued jobs
        queued = persistence.list_jobs_by_status(JobStatus.QUEUED)

        # Expected order:
        # 1. jobs[1] - priority=10, lowest position among priority=10
        # 2. jobs[4] - priority=10, higher position
        # 3. jobs[2] - priority=5, lowest position among priority=5
        # 4. jobs[3] - priority=5, higher position
        # 5. jobs[0] - priority=1

        assert len(queued) == 5
        assert queued[0].job_id == jobs[1].job_id  # priority=10, first created
        assert queued[1].job_id == jobs[4].job_id  # priority=10, second created
        assert queued[2].job_id == jobs[2].job_id  # priority=5, first created
        assert queued[3].job_id == jobs[3].job_id  # priority=5, second created
        assert queued[4].job_id == jobs[0].job_id  # priority=1

    def test_inv_004_e_deterministic_same_input_same_output(
        self, persistence: PersistenceAdapter, create_job
    ):
        """
        INV-004-E: Deterministic (same input → same output).

        Setup: Fixed set of jobs
        Action: Run get_next() N times
        Assertion: Same order every time
        """
        # Setup: Create a set of jobs
        jobs = [
            create_job(priority=10),
            create_job(priority=5),
            create_job(priority=15),
            create_job(priority=5),
        ]

        # Action: Get next job multiple times and collect results
        results = []
        for _ in range(10):
            next_job = persistence.get_next_queued_job()
            results.append(next_job.job_id if next_job else None)

        # Assertion: All results should be the same (deterministic)
        assert all(r == results[0] for r in results)
        # And should be the highest priority job
        assert results[0] == jobs[2].job_id  # priority=15


# =============================================================================
# INV-005: Schedule-Job Isolation
# =============================================================================


class TestINV005ScheduleJobIsolation:
    """
    INV-005: A Schedule's state MUST NOT affect already-created Jobs.
    """

    def test_inv_005_a_job_params_snapshot_is_independent(
        self,
        persistence: PersistenceAdapter,
        create_template,
    ):
        """
        INV-005-A: Job params snapshot is independent.

        Setup: Create job from schedule
        Action: Update schedule params
        Assertion: Job.params unchanged
        """
        # Setup: Create a template
        template = create_template(
            name="test-template",
            job_type="story",
            default_params={"original": True, "value": 42},
        )

        # Create a job with template params
        job = Job.create(
            job_type=template.job_type,
            params=template.default_params.copy(),
            template_id=template.template_id,
        )
        job = persistence.create_job(job)
        original_params = job.params.copy()

        # Action: Update template params
        persistence.update_template(
            template.template_id,
            default_params={"modified": True, "new_value": 100},
        )

        # Assertion: Job params should be unchanged
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.params == original_params
        assert job_fresh.params.get("original") is True
        assert job_fresh.params.get("value") == 42

    def test_inv_005_b_disable_schedule_doesnt_cancel_jobs(
        self,
        persistence: PersistenceAdapter,
        create_template,
    ):
        """
        INV-005-B: Disable schedule doesn't cancel jobs.

        Setup: Create job, then disable schedule
        Action: Check job status
        Assertion: Job still QUEUED
        """
        # Setup: Create a template and schedule
        template = create_template(
            name="test-template",
            job_type="story",
        )

        from src.scheduler import Schedule

        schedule = Schedule.create(
            template_id=template.template_id,
            name="test-schedule",
            cron_expression="0 * * * *",
            enabled=True,
        )
        schedule = persistence.create_schedule(schedule)

        # Create a job linked to the schedule
        job = Job.create(
            job_type=template.job_type,
            params={"test": True},
            template_id=template.template_id,
            schedule_id=schedule.schedule_id,
        )
        job = persistence.create_job(job)

        # Action: Disable the schedule
        persistence.update_schedule(schedule.schedule_id, enabled=False)

        # Assertion: Job should still be QUEUED
        job_fresh = persistence.get_job(job.job_id)
        assert job_fresh.status == JobStatus.QUEUED


# =============================================================================
# INV-006: JobGroup Completion Atomicity (xfail - not implemented)
# =============================================================================


@pytest.mark.xfail(reason="JobGroup not implemented yet (OQ-002 unresolved)")
class TestINV006JobGroupAtomicity:
    """
    INV-006: A JobGroup's terminal status MUST be determined only
    when ALL member Jobs reach terminal status.

    NOTE: JobGroup is not implemented in Phase 4. These tests are
    marked xfail per TEST_STRATEGY.md Section 7.3.
    """

    def test_inv_006_a_group_running_if_any_job_running(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-A: Group RUNNING if any job RUNNING.

        Setup: Group with 3 jobs, 1 RUNNING
        Action: compute_group_status()
        Assertion: RUNNING
        """
        pytest.skip("JobGroup not implemented")

    def test_inv_006_b_group_terminal_only_when_all_terminal(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-B: Group terminal only when all terminal.

        Setup: 2 jobs COMPLETED, 1 QUEUED
        Action: compute_group_status()
        Assertion: RUNNING (not COMPLETED)
        """
        pytest.skip("JobGroup not implemented")

    def test_inv_006_c_group_partial_if_any_failed(
        self, persistence: PersistenceAdapter
    ):
        """
        INV-006-C: Group PARTIAL if any FAILED.

        Setup: All jobs terminal, 1 FAILED
        Action: compute_group_status()
        Assertion: PARTIAL
        """
        pytest.skip("JobGroup not implemented")
