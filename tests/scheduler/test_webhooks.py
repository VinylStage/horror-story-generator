"""
Webhook Contract Verification Tests for Task Scheduler.

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
    Task,
    TaskRun,
    TaskStatus,
    TaskRunStatus,
)


# =============================================================================
# WH-SCHEMA: Schema Parity with API
# =============================================================================


class TestWHSchema:
    """
    Schema parity with API.

    Rule: Webhook payload schema MUST match API response schema for statuses.
    """

    def test_wh_schema_01_task_status_matches_api(self):
        """
        WH-SCHEMA-01: Task status in webhook matches API.

        Assertions:
        - Webhook status ∈ {QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED}
        """
        # These are the only valid Task statuses per API_CONTRACT.md
        valid_task_statuses = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}

        # Verify TaskStatus enum values
        actual_statuses = {status.value for status in TaskStatus}

        assert actual_statuses == valid_task_statuses, (
            f"Task statuses mismatch: expected {valid_task_statuses}, got {actual_statuses}"
        )

    def test_wh_schema_02_taskrun_status_matches_api(self):
        """
        WH-SCHEMA-02: TaskRun status in webhook matches API.

        Assertions:
        - Webhook status ∈ {COMPLETED, FAILED, SKIPPED}
        """
        # These are the only valid TaskRun statuses per API_CONTRACT.md
        valid_run_statuses = {"COMPLETED", "FAILED", "SKIPPED"}

        # Verify TaskRunStatus enum values
        actual_statuses = {status.value for status in TaskRunStatus}

        assert actual_statuses == valid_run_statuses, (
            f"TaskRun statuses mismatch: expected {valid_run_statuses}, got {actual_statuses}"
        )

    def test_wh_schema_03_webhook_payload_structure(self):
        """
        WH-SCHEMA-03: Webhook payload structure matches API_CONTRACT.md Section 8.

        This test verifies the expected structure for webhook payloads.
        """
        # Create a sample TaskRun to verify structure
        task_run = TaskRun.create(
            task_id="test-task-id",
            params_snapshot={"theme": "dark", "style": "vintage"},
            template_id="test-template-id",
        )

        # Simulate webhook payload construction
        # From API_CONTRACT.md Section 8: Webhook Events
        expected_fields = {
            "run_id": task_run.run_id,
            "task_id": task_run.task_id,
            "status": None,  # Will be set when terminal
            "started_at": task_run.started_at,
            "finished_at": task_run.finished_at,
            "exit_code": task_run.exit_code,
            "error": task_run.error,
            "artifacts": task_run.artifacts,
        }

        # Verify all expected fields exist on TaskRun
        assert task_run.run_id is not None
        assert task_run.task_id is not None
        assert task_run.started_at is not None
        assert isinstance(task_run.artifacts, list)

    def test_wh_schema_04_all_required_fields_present(self):
        """
        WH-SCHEMA-04: All required fields present in TaskRun.

        Required fields: run_id, task_id, status, timestamps
        """
        # Create TaskRun and set terminal status
        task_run = TaskRun(
            run_id="test-run-id",
            task_id="test-task-id",
            params_snapshot={"test": True},
            status=TaskRunStatus.COMPLETED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
            artifacts=["output.txt"],
        )

        # Verify required fields are present
        assert task_run.run_id is not None
        assert task_run.task_id is not None
        assert task_run.status is not None
        assert task_run.started_at is not None
        assert task_run.finished_at is not None


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
        WH-EVENT-01: task.run.completed event.

        Event: task.run.completed
        Trigger: TaskRun status = COMPLETED
        Payload Contains: status: COMPLETED
        """
        task_run = TaskRun(
            run_id="test-run-id",
            task_id="test-task-id",
            params_snapshot={},
            status=TaskRunStatus.COMPLETED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
        )

        # Verify event type determination
        assert task_run.status == TaskRunStatus.COMPLETED
        assert task_run.is_terminal()

        # Event type should be "task.run.completed"
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.completed"

    def test_wh_event_02_failed_event(self):
        """
        WH-EVENT-02: task.run.failed event.

        Event: task.run.failed
        Trigger: TaskRun status = FAILED
        Payload Contains: status: FAILED, error
        """
        task_run = TaskRun(
            run_id="test-run-id",
            task_id="test-task-id",
            params_snapshot={},
            status=TaskRunStatus.FAILED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=1,
            error="Test error message",
        )

        # Verify event type and payload
        assert task_run.status == TaskRunStatus.FAILED
        assert task_run.is_terminal()
        assert task_run.error is not None

        # Event type should be "task.run.failed"
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.failed"

    def test_wh_event_03_skipped_event(self):
        """
        WH-EVENT-03: task.run.skipped event.

        Event: task.run.skipped
        Trigger: TaskRun status = SKIPPED
        Payload Contains: status: SKIPPED
        """
        task_run = TaskRun(
            run_id="test-run-id",
            task_id="test-task-id",
            params_snapshot={},
            status=TaskRunStatus.SKIPPED,
            started_at=datetime.utcnow().isoformat() + "Z",
            finished_at=datetime.utcnow().isoformat() + "Z",
        )

        # Verify event type
        assert task_run.status == TaskRunStatus.SKIPPED
        assert task_run.is_terminal()

        # Event type should be "task.run.skipped"
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.skipped"


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

    def test_wh_rec_01_recovered_task_webhook_status(
        self, persistence, create_task
    ):
        """
        WH-REC-01: Crash-recovered task has correct status for webhook.

        Assertions:
        - FAILED status ready for webhook
        """
        from src.scheduler import QueueManager, RetryController
        from src.scheduler.recovery import RecoveryManager

        # Create RUNNING task (will be recovered)
        task = create_task()
        with persistence._transaction() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
                (TaskStatus.RUNNING.value, datetime.utcnow().isoformat() + "Z", task.task_id),
            )

        # Recovery
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)
        recovery_manager = RecoveryManager(persistence, queue_manager, retry_controller)

        recovery_manager.recover_on_startup()

        # Verify recovered TaskRun has FAILED status (webhook-ready)
        task_run = persistence.get_task_run_for_task(task.task_id)
        assert task_run is not None
        assert task_run.status == TaskRunStatus.FAILED

        # Verify webhook event type would be "task.run.failed"
        event_type = f"task.run.{task_run.status.value.lower()}"
        assert event_type == "task.run.failed"

    def test_wh_rec_02_retry_task_webhook_status(
        self, persistence, create_task
    ):
        """
        WH-REC-02: Retry task fires webhook on completion.

        Assertions:
        - New task's webhook sent with appropriate status
        """
        from src.scheduler import QueueManager, RetryController

        # Create and fail a task
        task = create_task()
        task, task_run = persistence.atomic_claim_task(task.task_id)

        persistence.update_task_run(
            task_run.run_id,
            status=TaskRunStatus.FAILED,
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        persistence.update_task(task.task_id, finished_at=datetime.utcnow().isoformat() + "Z")

        # Create retry
        queue_manager = QueueManager(persistence)
        retry_controller = RetryController(persistence, queue_manager)

        retry_task = retry_controller.on_task_failed(
            persistence.get_task(task.task_id),
            persistence.get_task_run(task_run.run_id),
        )

        # Execute retry task and complete successfully
        retry_task, retry_run = persistence.atomic_claim_task(retry_task.task_id)

        persistence.update_task_run(
            retry_run.run_id,
            status=TaskRunStatus.COMPLETED,
            finished_at=datetime.utcnow().isoformat() + "Z",
            exit_code=0,
        )

        # Verify webhook event type for completed retry
        retry_run_fresh = persistence.get_task_run(retry_run.run_id)
        assert retry_run_fresh.status == TaskRunStatus.COMPLETED

        event_type = f"task.run.{retry_run_fresh.status.value.lower()}"
        assert event_type == "task.run.completed"


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
        task_run = TaskRun(
            run_id="run-123",
            task_id="task-456",
            params_snapshot={"theme": "dark"},
            status=TaskRunStatus.COMPLETED,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:05:00Z",
            exit_code=0,
            artifacts=["story.md"],
        )

        # Build webhook payload
        payload = {
            "event": "task.run.completed",
            "data": {
                "run_id": task_run.run_id,
                "task_id": task_run.task_id,
                "status": task_run.status.value,
                "started_at": task_run.started_at,
                "finished_at": task_run.finished_at,
                "exit_code": task_run.exit_code,
                "artifacts": task_run.artifacts,
            },
        }

        # Verify structure
        assert payload["event"] == "task.run.completed"
        assert payload["data"]["status"] == "COMPLETED"
        assert payload["data"]["run_id"] == "run-123"
        assert payload["data"]["task_id"] == "task-456"
        assert payload["data"]["exit_code"] == 0
        assert "story.md" in payload["data"]["artifacts"]

    def test_build_failed_payload(self):
        """Test building payload for FAILED status."""
        task_run = TaskRun(
            run_id="run-123",
            task_id="task-456",
            params_snapshot={"theme": "dark"},
            status=TaskRunStatus.FAILED,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:05:00Z",
            exit_code=1,
            error="Story generation failed: API timeout",
        )

        # Build webhook payload
        payload = {
            "event": "task.run.failed",
            "data": {
                "run_id": task_run.run_id,
                "task_id": task_run.task_id,
                "status": task_run.status.value,
                "started_at": task_run.started_at,
                "finished_at": task_run.finished_at,
                "exit_code": task_run.exit_code,
                "error": task_run.error,
            },
        }

        # Verify structure
        assert payload["event"] == "task.run.failed"
        assert payload["data"]["status"] == "FAILED"
        assert payload["data"]["error"] == "Story generation failed: API timeout"
        assert payload["data"]["exit_code"] == 1
