"""
Tests for scheduler domain entities.

Covers:
- Enum values: TaskStatus, TaskRunStatus, ReservationStatus, TaskGroupStatus
- .create() factory methods for all entities
- is_terminal() methods
- Backward compatibility aliases
"""

import re

import pytest

from src.scheduler.entities import (
    TaskStatus,
    TaskRunStatus,
    ReservationStatus,
    TaskGroupStatus,
    TaskTemplate,
    Schedule,
    Task,
    TaskRun,
    DirectReservation,
    TaskGroup,
    generate_uuid,
    now_iso,
    # Backward compatibility aliases
    JobStatus,
    JobRunStatus,
    JobGroupStatus,
    Job,
    JobRun,
    JobTemplate,
    JobGroup,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
ISO_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


# ===========================================================================
# Helper Utilities
# ===========================================================================
class TestGenerateUuid:
    """Tests for generate_uuid()."""

    def test_returns_valid_uuid4(self):
        uid = generate_uuid()
        assert UUID_PATTERN.match(uid)

    def test_unique_per_call(self):
        ids = {generate_uuid() for _ in range(100)}
        assert len(ids) == 100


class TestNowIso:
    """Tests for now_iso()."""

    def test_returns_iso_format_with_z(self):
        ts = now_iso()
        assert ISO_TIMESTAMP_PATTERN.match(ts)
        assert ts.endswith("Z")


# ===========================================================================
# Enum Values
# ===========================================================================
class TestTaskStatus:
    """Tests for TaskStatus enum."""

    EXPECTED_VALUES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}

    def test_all_values_present(self):
        actual = {s.value for s in TaskStatus}
        assert actual == self.EXPECTED_VALUES

    def test_is_str_enum(self):
        assert isinstance(TaskStatus.QUEUED, str)
        assert TaskStatus.QUEUED == "QUEUED"


class TestTaskRunStatus:
    """Tests for TaskRunStatus enum."""

    EXPECTED_VALUES = {"COMPLETED", "FAILED", "SKIPPED"}

    def test_all_values_present(self):
        actual = {s.value for s in TaskRunStatus}
        assert actual == self.EXPECTED_VALUES

    def test_is_str_enum(self):
        assert isinstance(TaskRunStatus.COMPLETED, str)


class TestReservationStatus:
    """Tests for ReservationStatus enum."""

    EXPECTED_VALUES = {"ACTIVE", "RELEASED", "EXPIRED"}

    def test_all_values_present(self):
        actual = {s.value for s in ReservationStatus}
        assert actual == self.EXPECTED_VALUES


class TestTaskGroupStatus:
    """Tests for TaskGroupStatus enum."""

    EXPECTED_VALUES = {"CREATED", "QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "CANCELLED"}

    def test_all_values_present(self):
        actual = {s.value for s in TaskGroupStatus}
        assert actual == self.EXPECTED_VALUES


# ===========================================================================
# TaskTemplate
# ===========================================================================
class TestTaskTemplate:
    """Tests for TaskTemplate entity."""

    def test_create_generates_uuid(self):
        t = TaskTemplate.create(name="gen-story", task_type="story")
        assert UUID_PATTERN.match(t.template_id)

    def test_create_sets_name_and_type(self):
        t = TaskTemplate.create(name="gen-story", task_type="story")
        assert t.name == "gen-story"
        assert t.task_type == "story"

    def test_create_default_params(self):
        t = TaskTemplate.create(name="t", task_type="story")
        assert t.default_params == {}
        assert t.retry_policy == {"max_attempts": 3}
        assert t.description is None

    def test_create_custom_params(self):
        params = {"model": "gpt-4"}
        retry = {"max_attempts": 5}
        t = TaskTemplate.create(
            name="t",
            task_type="research",
            default_params=params,
            retry_policy=retry,
            description="My template",
        )
        assert t.default_params == params
        assert t.retry_policy == retry
        assert t.description == "My template"

    def test_create_timestamps(self):
        t = TaskTemplate.create(name="t", task_type="story")
        assert ISO_TIMESTAMP_PATTERN.match(t.created_at)
        assert ISO_TIMESTAMP_PATTERN.match(t.updated_at)


# ===========================================================================
# Schedule
# ===========================================================================
class TestSchedule:
    """Tests for Schedule entity."""

    def test_create_generates_uuid(self):
        s = Schedule.create(
            template_id="tmpl-1", name="daily-story", cron_expression="0 9 * * *"
        )
        assert UUID_PATTERN.match(s.schedule_id)

    def test_create_defaults(self):
        s = Schedule.create(
            template_id="tmpl-1", name="daily", cron_expression="0 9 * * *"
        )
        assert s.timezone == "UTC"
        assert s.enabled is True
        assert s.param_overrides is None
        assert s.last_triggered_at is None
        assert s.next_trigger_at is None

    def test_create_custom(self):
        s = Schedule.create(
            template_id="tmpl-1",
            name="custom",
            cron_expression="0 */6 * * *",
            timezone="US/Eastern",
            enabled=False,
            param_overrides={"count": 3},
        )
        assert s.timezone == "US/Eastern"
        assert s.enabled is False
        assert s.param_overrides == {"count": 3}


# ===========================================================================
# Task
# ===========================================================================
class TestTask:
    """Tests for Task entity."""

    def test_create_generates_uuid(self):
        t = Task.create(task_type="story", params={"test": True})
        assert UUID_PATTERN.match(t.task_id)

    def test_create_initial_status_is_queued(self):
        t = Task.create(task_type="story", params={})
        assert t.status == TaskStatus.QUEUED

    def test_create_timestamps(self):
        t = Task.create(task_type="story", params={})
        assert ISO_TIMESTAMP_PATTERN.match(t.created_at)
        assert ISO_TIMESTAMP_PATTERN.match(t.queued_at)
        assert t.created_at == t.queued_at

    def test_create_defaults(self):
        t = Task.create(task_type="story", params={})
        assert t.priority == 0
        assert t.position == 0
        assert t.template_id is None
        assert t.schedule_id is None
        assert t.group_id is None
        assert t.sequence_number is None
        assert t.retry_of is None
        assert t.started_at is None
        assert t.finished_at is None

    def test_create_custom(self):
        t = Task.create(
            task_type="research",
            params={"topic": "AI"},
            priority=5,
            position=2,
            template_id="tmpl-1",
            schedule_id="sched-1",
            group_id="grp-1",
            sequence_number=0,
            retry_of="prev-task-id",
        )
        assert t.task_type == "research"
        assert t.params == {"topic": "AI"}
        assert t.priority == 5
        assert t.position == 2
        assert t.template_id == "tmpl-1"
        assert t.schedule_id == "sched-1"
        assert t.group_id == "grp-1"
        assert t.sequence_number == 0
        assert t.retry_of == "prev-task-id"

    @pytest.mark.parametrize(
        "status,finished_at,expected",
        [
            (TaskStatus.QUEUED, None, False),
            (TaskStatus.RUNNING, None, False),
            (TaskStatus.COMPLETED, "2026-01-01T00:00:00Z", True),
            (TaskStatus.FAILED, "2026-01-01T00:00:00Z", True),
            (TaskStatus.CANCELLED, None, True),
            (TaskStatus.CANCELLED, "2026-01-01T00:00:00Z", True),
        ],
    )
    def test_is_terminal(self, status, finished_at, expected):
        t = Task.create(task_type="story", params={})
        t.status = status
        t.finished_at = finished_at
        assert t.is_terminal() is expected


# ===========================================================================
# TaskRun
# ===========================================================================
class TestTaskRun:
    """Tests for TaskRun entity."""

    def test_create_generates_uuid(self):
        r = TaskRun.create(task_id="task-1", params_snapshot={"x": 1})
        assert UUID_PATTERN.match(r.run_id)

    def test_create_sets_started_at(self):
        r = TaskRun.create(task_id="task-1", params_snapshot={})
        assert ISO_TIMESTAMP_PATTERN.match(r.started_at)

    def test_create_defaults(self):
        r = TaskRun.create(task_id="task-1", params_snapshot={})
        assert r.task_id == "task-1"
        assert r.template_id is None
        assert r.status is None
        assert r.finished_at is None
        assert r.exit_code is None
        assert r.error is None
        assert r.artifacts == []
        assert r.log_path is None

    def test_create_custom(self):
        r = TaskRun.create(
            task_id="task-1",
            params_snapshot={"p": 1},
            template_id="tmpl-1",
            log_path="/var/log/run.log",
        )
        assert r.template_id == "tmpl-1"
        assert r.log_path == "/var/log/run.log"

    @pytest.mark.parametrize(
        "status,expected",
        [
            (None, False),
            (TaskRunStatus.COMPLETED, True),
            (TaskRunStatus.FAILED, True),
            (TaskRunStatus.SKIPPED, True),
        ],
    )
    def test_is_terminal(self, status, expected):
        r = TaskRun.create(task_id="task-1", params_snapshot={})
        r.status = status
        assert r.is_terminal() is expected


# ===========================================================================
# DirectReservation
# ===========================================================================
class TestDirectReservation:
    """Tests for DirectReservation entity."""

    def test_create_generates_uuid(self):
        r = DirectReservation.create(
            reserved_by="test-client", expires_at="2026-01-01T01:00:00Z"
        )
        assert UUID_PATTERN.match(r.reservation_id)

    def test_create_status_is_active(self):
        r = DirectReservation.create(
            reserved_by="test-client", expires_at="2026-01-01T01:00:00Z"
        )
        assert r.status == ReservationStatus.ACTIVE

    def test_create_fields(self):
        r = DirectReservation.create(
            reserved_by="api-user", expires_at="2026-12-31T23:59:59Z"
        )
        assert r.reserved_by == "api-user"
        assert r.expires_at == "2026-12-31T23:59:59Z"
        assert ISO_TIMESTAMP_PATTERN.match(r.reserved_at)


# ===========================================================================
# TaskGroup
# ===========================================================================
class TestTaskGroup:
    """Tests for TaskGroup entity."""

    def test_create_generates_uuid(self):
        g = TaskGroup.create(name="batch-1")
        assert UUID_PATTERN.match(g.group_id)

    def test_create_defaults(self):
        g = TaskGroup.create()
        assert g.name is None
        assert g.status == TaskGroupStatus.CREATED
        assert g.execution_mode == "sequential"
        assert g.started_at is None
        assert g.finished_at is None

    def test_create_custom(self):
        g = TaskGroup.create(name="parallel-batch", execution_mode="concurrent")
        assert g.name == "parallel-batch"
        assert g.execution_mode == "concurrent"

    @pytest.mark.parametrize(
        "status,expected",
        [
            (TaskGroupStatus.CREATED, False),
            (TaskGroupStatus.QUEUED, False),
            (TaskGroupStatus.RUNNING, False),
            (TaskGroupStatus.COMPLETED, True),
            (TaskGroupStatus.PARTIAL, True),
            (TaskGroupStatus.CANCELLED, True),
        ],
    )
    def test_is_terminal(self, status, expected):
        g = TaskGroup.create()
        g.status = status
        assert g.is_terminal() is expected


# ===========================================================================
# Backward Compatibility Aliases
# ===========================================================================
class TestBackwardCompatAliases:
    """Tests for backward compatibility aliases."""

    def test_job_status_is_task_status(self):
        assert JobStatus is TaskStatus

    def test_job_run_status_is_task_run_status(self):
        assert JobRunStatus is TaskRunStatus

    def test_job_group_status_is_task_group_status(self):
        assert JobGroupStatus is TaskGroupStatus

    def test_job_is_task(self):
        assert Job is Task

    def test_job_run_is_task_run(self):
        assert JobRun is TaskRun

    def test_job_template_is_task_template(self):
        assert JobTemplate is TaskTemplate

    def test_job_group_is_task_group(self):
        assert JobGroup is TaskGroup
