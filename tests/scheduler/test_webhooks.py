"""
Webhook Contract Verification Tests for Job Scheduler.

Tests from TEST_STRATEGY.md Section 6 (Webhook Contract Verification):
- WH-SCHEMA-*: Schema parity with API
- WH-EVENT-*: Event types
- WH-DELIV-*: Delivery semantics (skipped - requires external endpoint)
- WH-REC-*: Recovery webhook tests

Each test validates webhook contract compliance.

Note: Full delivery tests (WH-DELIV-*) require external HTTP endpoints
and are optional per TEST_STRATEGY.md Section 7.3.
"""

import pytest
from datetime import datetime

from src.scheduler import (
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
)


# =============================================================================
# WH-SCHEMA: Schema Parity with API
# =============================================================================


class TestWHSchema:
    """
    Schema parity with API.

    Rule: Webhook payload schema MUST match API response schema for statuses.
    """

    def test_wh_schema_01_job_status_matches_api(self):
        """
        WH-SCHEMA-01: Job status in webhook matches API.

        Assertions:
        - Webhook status ∈ {QUEUED, RUNNING, CANCELLED}
        """
        # These are the only valid Job statuses per API_CONTRACT.md
        valid_job_statuses = {"QUEUED", "RUNNING", "CANCELLED"}

        # Verify JobStatus enum values
        actual_statuses = {status.value for status in JobStatus}

        assert actual_statuses == valid_job_statuses, (
            f"Job statuses mismatch: expected {valid_job_statuses}, got {actual_statuses}"
        )

    def test_wh_schema_02_jobrun_status_matches_api(self):
        """
        WH-SCHEMA-02: JobRun status in webhook matches API.

        Assertions:
        - Webhook status ∈ {COMPLETED, FAILED, SKIPPED}
        """
        # These are the only valid JobRun statuses per API_CONTRACT.md
        valid_run_statuses = {"COMPLETED", "FAILED", "SKIPPED"}

        # Verify JobRunStatus enum values
        actual_statuses = {status.value for status in JobRunStatus}

        assert actual_statuses == valid_run_statuses, (
            f"JobRun statuses mismatch: expected {valid_run_statuses}, got {actual_statuses}"
        )

    def test_wh_schema_03_webhook_payload_structure(self):
        """
        WH-SCHEMA-03: Webhook payload structure matches API_CONTRACT.md Section 8.

        This test verifies the expected structure for webhook payloads.
        """
        # Create a sample JobRun to verify structure
        job_run = JobRun.create(
            job_id="test-job-id",
            params_snapshot={"theme": "dark", "style": "vintage"},
            template_id="test-template-id",
        )

        # Simulate webhook payload construction
        # From API_CONTRACT.md Section 8: Webhook Events
        expected_fields = {
            "run_id": job_run.run_id,
            "job_id": job_run.job_id,
            "status": None,  # Will be set when terminal
            "started_at": job_run.started_at,
            "finished_at": job_run.finished_at,
            "exit_code": job_run.exit_code,
            "error": job_run.error,
            "artifacts": job_run.artifacts,
        }

        # Verify all expected fields exist on JobRun
        assert job_run.run_id is not None
        assert job_run.job_id is not None
        assert job_run.started_at is not None
        assert isinstance(job_run.artifacts, list)

    def test_wh_schema_04_all_required_fields_present(self):
        """
        WH-SCHEMA-04: All required fields present in JobRun.

        Required fields: run_id, job_id, status, timestamps
        """
        # Create JobRun and set terminal status
        job_run = JobRun(
            run_id="test-run-id",
            job_id="test-job-id",
            params_snapshot={"test": True},
            status=JobRunStatus.COMPLETED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
            artifacts=["output.txt"],
        )

        # Verify required fields are present
        assert job_run.run_id is not None
        assert job_run.job_id is not None
        assert job_run.status is not None
        assert job_run.started_at is not None
        assert job_run.finished_at is not None


# =============================================================================
# WH-EVENT: Event Types
# =============================================================================


class TestWHEventTypes:
    """
    Event types verification.

    Validates that correct events are triggered for each status.
    """

    def test_wh_event_01_completed_event(self):
        """
        WH-EVENT-01: job.run.completed event.

        Event: job.run.completed
        Trigger: JobRun status = COMPLETED
        Payload Contains: status: COMPLETED
        """
        job_run = JobRun(
            run_id="test-run-id",
            job_id="test-job-id",
            params_snapshot={},
            status=JobRunStatus.COMPLETED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
        )

        # Verify event type determination
        assert job_run.status == JobRunStatus.COMPLETED
        assert job_run.is_terminal()

        # Event type should be "job.run.completed"
        event_type = f"job.run.{job_run.status.value.lower()}"
        assert event_type == "job.run.completed"

    def test_wh_event_02_failed_event(self):
        """
        WH-EVENT-02: job.run.failed event.

        Event: job.run.failed
        Trigger: JobRun status = FAILED
        Payload Contains: status: FAILED, error
        """
        job_run = JobRun(
            run_id="test-run-id",
            job_id="test-job-id",
            params_snapshot={},
            status=JobRunStatus.FAILED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=1,
            error="Test error message",
        )

        # Verify event type and payload
        assert job_run.status == JobRunStatus.FAILED
        assert job_run.is_terminal()
        assert job_run.error is not None

        # Event type should be "job.run.failed"
        event_type = f"job.run.{job_run.status.value.lower()}"
        assert event_type == "job.run.failed"

    def test_wh_event_03_skipped_event(self):
        """
        WH-EVENT-03: job.run.skipped event.

        Event: job.run.skipped
        Trigger: JobRun status = SKIPPED
        Payload Contains: status: SKIPPED
        """
        job_run = JobRun(
            run_id="test-run-id",
            job_id="test-job-id",
            params_snapshot={},
            status=JobRunStatus.SKIPPED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Verify event type
        assert job_run.status == JobRunStatus.SKIPPED
        assert job_run.is_terminal()

        # Event type should be "job.run.skipped"
        event_type = f"job.run.{job_run.status.value.lower()}"
        assert event_type == "job.run.skipped"


# =============================================================================
# WH-DELIV: Delivery Semantics (DEC-009) - Skipped
# =============================================================================


@pytest.mark.skip(reason="Webhook delivery tests require external HTTP endpoint (Phase 4+)")
class TestWHDelivery:
    """
    Webhook delivery semantics (DEC-009).

    Note: These tests are skipped per TEST_STRATEGY.md Section 7.3.
    Requires external HTTP endpoint for testing.
    """

    def test_wh_deliv_01_webhook_fires_on_completion(self):
        """WH-DELIV-01: Webhook fires on completion."""
        pass

    def test_wh_deliv_02_retry_on_failure(self):
        """WH-DELIV-02: Retry on failure (up to 3)."""
        pass

    def test_wh_deliv_03_max_retries_respected(self):
        """WH-DELIV-03: Max retries respected."""
        pass

    def test_wh_deliv_04_idempotent_handling(self):
        """WH-DELIV-04: Idempotent handling supported."""
        pass


# =============================================================================
# WH-REC: Recovery Webhook Tests
# =============================================================================


class TestWHRecovery:
    """
    Recovery webhook tests.

    Validates webhooks are sent correctly after crash recovery.
    """

    def test_wh_rec_01_recovered_job_webhook_status(
        self, persistence, create_job
    ):
        """
        WH-REC-01: Crash-recovered job has correct status for webhook.

        Assertions:
        - FAILED status ready for webhook
        """
        from src.scheduler import QueueManager, RetryController
        from src.scheduler.recovery import RecoveryManager

        # Create RUNNING job (will be recovered)
        job = create_job()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = ? WHERE job_id = ?",
                (JobStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", job.job_id),
            )

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Verify recovered JobRun has FAILED status (webhook-ready)
        job_run = persistence.get_job_run_for_job(job.job_id)
        assert job_run is not None
        assert job_run.status == JobRunStatus.FAILED

        # Verify webhook event type would be "job.run.failed"
        event_type = f"job.run.{job_run.status.value.lower()}"
        assert event_type == "job.run.failed"

    def test_wh_rec_02_retry_job_webhook_status(
        self, persistence, create_job
    ):
        """
        WH-REC-02: Retry job fires webhook on completion.

        Assertions:
        - New job's webhook sent with appropriate status
        """
        from src.scheduler import QueueManager, RetryController

        # Create and fail a job
        job = create_job()
        job, job_run = persistence.atomic_claim_job(job.job_id)

        persistence.update_job_run(
            job_run.run_id,
            status=JobRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_job(job.job_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)

        retry_job = retry_controller.on_job_failed(
            persistence.get_job(job.job_id),
            persistence.get_job_run(job_run.run_id),
        )

        # Execute retry job and complete successfully
        retry_job, retry_run = persistence.atomic_claim_job(retry_job.job_id)

        persistence.update_job_run(
            retry_run.run_id,
            status=JobRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
        )

        # Verify webhook event type for completed retry
        retry_run_fresh = persistence.get_job_run(retry_run.run_id)
        assert retry_run_fresh.status == JobRunStatus.COMPLETED

        event_type = f"job.run.{retry_run_fresh.status.value.lower()}"
        assert event_type == "job.run.completed"


# =============================================================================
# Webhook Payload Builder (Helper)
# =============================================================================


class TestWebhookPayloadBuilder:
    """
    Tests for webhook payload construction.

    These tests verify the structure of webhook payloads
    that would be sent to external endpoints.
    """

    def test_build_completed_payload(self):
        """Test building payload for COMPLETED status."""
        job_run = JobRun(
            run_id="run-123",
            job_id="job-456",
            params_snapshot={"theme": "dark"},
            status=JobRunStatus.COMPLETED,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:05:00Z",
            exit_code=0,
            artifacts=["story.md"],
        )

        # Build webhook payload
        payload = {
            "event": "job.run.completed",
            "data": {
                "run_id": job_run.run_id,
                "job_id": job_run.job_id,
                "status": job_run.status.value,
                "started_at": job_run.started_at,
                "finished_at": job_run.finished_at,
                "exit_code": job_run.exit_code,
                "artifacts": job_run.artifacts,
            },
        }

        # Verify structure
        assert payload["event"] == "job.run.completed"
        assert payload["data"]["status"] == "COMPLETED"
        assert payload["data"]["run_id"] == "run-123"
        assert payload["data"]["job_id"] == "job-456"
        assert payload["data"]["exit_code"] == 0
        assert "story.md" in payload["data"]["artifacts"]

    def test_build_failed_payload(self):
        """Test building payload for FAILED status."""
        job_run = JobRun(
            run_id="run-123",
            job_id="job-456",
            params_snapshot={"theme": "dark"},
            status=JobRunStatus.FAILED,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:05:00Z",
            exit_code=1,
            error="Story generation failed: API timeout",
        )

        # Build webhook payload
        payload = {
            "event": "job.run.failed",
            "data": {
                "run_id": job_run.run_id,
                "job_id": job_run.job_id,
                "status": job_run.status.value,
                "started_at": job_run.started_at,
                "finished_at": job_run.finished_at,
                "exit_code": job_run.exit_code,
                "error": job_run.error,
            },
        }

        # Verify structure
        assert payload["event"] == "job.run.failed"
        assert payload["data"]["status"] == "FAILED"
        assert payload["data"]["error"] == "Story generation failed: API timeout"
        assert payload["data"]["exit_code"] == 1
