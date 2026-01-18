"""
Persistence Adapter for Job Scheduler.

Follows PERSISTENCE_SCHEMA.md and DESIGN_GUARDS.md:
- DEC-002: SQLite for job storage with WAL mode
- DEC-008: Queue persistence across restarts
- INV-001: Job immutability after dispatch
- INV-002: JobRun immutability

Provides:
- Atomic Job + JobRun creation during dispatch
- Recovery query helpers
- Position-based queue ordering
- Direct reservation persistence
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator, Tuple

from .entities import (
    Job,
    JobRun,
    JobTemplate,
    Schedule,
    DirectReservation,
    JobGroup,
    JobStatus,
    JobRunStatus,
    JobGroupStatus,
    ReservationStatus,
)
from .errors import (
    InvalidOperationError,
    JobNotFoundError,
    JobRunNotFoundError,
    TemplateNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
    ConcurrencyViolationError,
)


# Gap size for position assignment (from PERSISTENCE_SCHEMA.md Section 3.2)
POSITION_GAP_SIZE = 100


class PersistenceAdapter:
    """
    SQLite-based persistence for all job-related entities.

    From IMPLEMENTATION_PLAN.md Section 1.5:
    - Abstracts SQLite storage
    - CRUD operations for Job, JobRun, JobTemplate, Schedule
    - Does NOT contain business logic
    - Does NOT validate beyond schema constraints
    - Transaction management is caller's responsibility for multi-operations
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize persistence adapter.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for testing.
        """
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (DEC-002)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._transaction() as conn:
            # JobTemplate table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_templates (
                    template_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    default_params TEXT NOT NULL DEFAULT '{}',
                    retry_policy TEXT NOT NULL DEFAULT '{"max_attempts": 3}',
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Schedule table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    param_overrides TEXT,
                    last_triggered_at TEXT,
                    next_trigger_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (template_id) REFERENCES job_templates(template_id)
                )
            """)

            # JobGroup table (DEC-012)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_groups (
                    group_id TEXT PRIMARY KEY,
                    name TEXT,
                    status TEXT NOT NULL DEFAULT 'CREATED',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
            """)

            # Job table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    template_id TEXT,
                    schedule_id TEXT,
                    group_id TEXT,
                    sequence_number INTEGER,
                    job_type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    position INTEGER NOT NULL DEFAULT 0,
                    retry_of TEXT,
                    created_at TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY (template_id) REFERENCES job_templates(template_id),
                    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id),
                    FOREIGN KEY (group_id) REFERENCES job_groups(group_id),
                    FOREIGN KEY (retry_of) REFERENCES jobs(job_id)
                )
            """)

            # Index for queue ordering (INV-004)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_queue_order
                ON jobs (status, priority DESC, position ASC, created_at ASC)
            """)

            # Index for JobGroup ordering (DEC-012)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_group_sequence
                ON jobs (group_id, sequence_number)
            """)

            # JobRun table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    template_id TEXT,
                    params_snapshot TEXT NOT NULL,
                    status TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    exit_code INTEGER,
                    error TEXT,
                    artifacts TEXT NOT NULL DEFAULT '[]',
                    log_path TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
            """)

            # Index for job -> runs lookup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_runs_job_id
                ON job_runs (job_id)
            """)

            # Direct reservation table (DEC-004)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS direct_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    reserved_by TEXT NOT NULL,
                    reserved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            # Index for active reservations
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reservations_status
                ON direct_reservations (status)
            """)

    # =========================================================================
    # JobTemplate Operations
    # =========================================================================

    def create_template(self, template: JobTemplate) -> JobTemplate:
        """Create a new job template."""
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO job_templates
                (template_id, name, job_type, default_params, retry_policy, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.template_id,
                    template.name,
                    template.job_type,
                    json.dumps(template.default_params),
                    json.dumps(template.retry_policy),
                    template.description,
                    template.created_at,
                    template.updated_at,
                ),
            )
        return template

    def get_template(self, template_id: str) -> Optional[JobTemplate]:
        """Get a job template by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()

        if row is None:
            return None

        return JobTemplate(
            template_id=row["template_id"],
            name=row["name"],
            job_type=row["job_type"],
            default_params=json.loads(row["default_params"]),
            retry_policy=json.loads(row["retry_policy"]),
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        default_params: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> JobTemplate:
        """
        Update a job template.

        Note: Changes apply only to future Jobs (INV-005).
        """
        template = self.get_template(template_id)
        if template is None:
            raise TemplateNotFoundError(template_id)

        updates = []
        values = []

        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if default_params is not None:
            updates.append("default_params = ?")
            values.append(json.dumps(default_params))
        if retry_policy is not None:
            updates.append("retry_policy = ?")
            values.append(json.dumps(retry_policy))
        if description is not None:
            updates.append("description = ?")
            values.append(description)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.utcnow().isoformat() + "Z")
            values.append(template_id)

            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE job_templates SET {', '.join(updates)} WHERE template_id = ?",
                    values,
                )

        return self.get_template(template_id)

    def list_templates(self) -> list[JobTemplate]:
        """List all job templates."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_templates ORDER BY created_at DESC"
            ).fetchall()

        return [
            JobTemplate(
                template_id=row["template_id"],
                name=row["name"],
                job_type=row["job_type"],
                default_params=json.loads(row["default_params"]),
                retry_policy=json.loads(row["retry_policy"]),
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    # =========================================================================
    # Schedule Operations
    # =========================================================================

    def create_schedule(self, schedule: Schedule) -> Schedule:
        """Create a new schedule."""
        # Verify template exists
        if self.get_template(schedule.template_id) is None:
            raise TemplateNotFoundError(schedule.template_id)

        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO schedules
                (schedule_id, template_id, name, cron_expression, timezone, enabled,
                 param_overrides, last_triggered_at, next_trigger_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.schedule_id,
                    schedule.template_id,
                    schedule.name,
                    schedule.cron_expression,
                    schedule.timezone,
                    1 if schedule.enabled else 0,
                    json.dumps(schedule.param_overrides) if schedule.param_overrides else None,
                    schedule.last_triggered_at,
                    schedule.next_trigger_at,
                    schedule.created_at,
                ),
            )
        return schedule

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()

        if row is None:
            return None

        return Schedule(
            schedule_id=row["schedule_id"],
            template_id=row["template_id"],
            name=row["name"],
            cron_expression=row["cron_expression"],
            timezone=row["timezone"],
            enabled=bool(row["enabled"]),
            param_overrides=json.loads(row["param_overrides"]) if row["param_overrides"] else None,
            last_triggered_at=row["last_triggered_at"],
            next_trigger_at=row["next_trigger_at"],
            created_at=row["created_at"],
        )

    def update_schedule(
        self,
        schedule_id: str,
        enabled: Optional[bool] = None,
        cron_expression: Optional[str] = None,
        timezone: Optional[str] = None,
        param_overrides: Optional[dict] = None,
        last_triggered_at: Optional[str] = None,
        next_trigger_at: Optional[str] = None,
    ) -> Schedule:
        """Update a schedule."""
        schedule = self.get_schedule(schedule_id)
        if schedule is None:
            raise InvalidOperationError(f"Schedule not found: {schedule_id}")

        updates = []
        values = []

        if enabled is not None:
            updates.append("enabled = ?")
            values.append(1 if enabled else 0)
        if cron_expression is not None:
            updates.append("cron_expression = ?")
            values.append(cron_expression)
        if timezone is not None:
            updates.append("timezone = ?")
            values.append(timezone)
        if param_overrides is not None:
            updates.append("param_overrides = ?")
            values.append(json.dumps(param_overrides))
        if last_triggered_at is not None:
            updates.append("last_triggered_at = ?")
            values.append(last_triggered_at)
        if next_trigger_at is not None:
            updates.append("next_trigger_at = ?")
            values.append(next_trigger_at)

        if updates:
            values.append(schedule_id)
            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE schedules SET {', '.join(updates)} WHERE schedule_id = ?",
                    values,
                )

        return self.get_schedule(schedule_id)

    def list_enabled_schedules(self) -> list[Schedule]:
        """List all enabled schedules."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE enabled = 1 ORDER BY created_at"
            ).fetchall()

        return [
            Schedule(
                schedule_id=row["schedule_id"],
                template_id=row["template_id"],
                name=row["name"],
                cron_expression=row["cron_expression"],
                timezone=row["timezone"],
                enabled=bool(row["enabled"]),
                param_overrides=json.loads(row["param_overrides"]) if row["param_overrides"] else None,
                last_triggered_at=row["last_triggered_at"],
                next_trigger_at=row["next_trigger_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # =========================================================================
    # Job Operations
    # =========================================================================

    def create_job(self, job: Job) -> Job:
        """
        Create a new job with automatic position assignment.

        From PERSISTENCE_SCHEMA.md Section 3.2:
        Position = max(position for same priority) + GAP_SIZE
        """
        with self._transaction() as conn:
            # Assign position using gap strategy
            row = conn.execute(
                """
                SELECT MAX(position) as max_pos FROM jobs
                WHERE status = ? AND priority = ?
                """,
                (JobStatus.QUEUED.value, job.priority),
            ).fetchone()

            max_pos = row["max_pos"] if row["max_pos"] is not None else 0
            job.position = max_pos + POSITION_GAP_SIZE

            conn.execute(
                """
                INSERT INTO jobs
                (job_id, template_id, schedule_id, group_id, sequence_number, job_type, params, status,
                 priority, position, retry_of, created_at, queued_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.template_id,
                    job.schedule_id,
                    job.group_id,
                    job.sequence_number,
                    job.job_type,
                    json.dumps(job.params),
                    job.status.value,
                    job.priority,
                    job.position,
                    job.retry_of,
                    job.created_at,
                    job.queued_at,
                    job.started_at,
                    job.finished_at,
                ),
            )
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert a database row to a Job entity."""
        return Job(
            job_id=row["job_id"],
            template_id=row["template_id"],
            schedule_id=row["schedule_id"],
            group_id=row["group_id"],
            sequence_number=row["sequence_number"],
            job_type=row["job_type"],
            params=json.loads(row["params"]),
            status=JobStatus(row["status"]),
            priority=row["priority"],
            position=row["position"],
            retry_of=row["retry_of"],
            created_at=row["created_at"],
            queued_at=row["queued_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        priority: Optional[int] = None,
        position: Optional[int] = None,
        params: Optional[dict] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> Job:
        """
        Update a job.

        Enforces INV-001: Cannot modify params after dispatch.
        """
        job = self.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        # Enforce INV-001: params immutable after RUNNING
        if params is not None and job.status in (JobStatus.RUNNING, JobStatus.CANCELLED):
            raise InvalidOperationError("Cannot modify params after dispatch (INV-001)")

        # Enforce: priority/position immutable after RUNNING
        if (priority is not None or position is not None) and job.status != JobStatus.QUEUED:
            raise InvalidOperationError("Cannot modify priority/position after dispatch")

        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status.value)
        if priority is not None:
            updates.append("priority = ?")
            values.append(priority)
        if position is not None:
            updates.append("position = ?")
            values.append(position)
        if params is not None:
            updates.append("params = ?")
            values.append(json.dumps(params))
        if started_at is not None:
            updates.append("started_at = ?")
            values.append(started_at)
        if finished_at is not None:
            updates.append("finished_at = ?")
            values.append(finished_at)

        if updates:
            values.append(job_id)
            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?",
                    values,
                )

        return self.get_job(job_id)

    def atomic_claim_job(self, job_id: str) -> Tuple[Job, JobRun]:
        """
        Atomically transition job QUEUED -> RUNNING and create JobRun.

        From PERSISTENCE_SCHEMA.md Section 5.1:
        A Job MUST NOT remain in RUNNING status without a corresponding JobRun.

        From PERSISTENCE_SCHEMA.md Section 5.3:
        Uses atomic claim to prevent duplicate execution.

        Raises:
            JobNotFoundError: If job doesn't exist
            ConcurrencyViolationError: If job is not QUEUED (already claimed)
        """
        with self._transaction() as conn:
            # Atomic claim with status check
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = ?
                WHERE job_id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    datetime.utcnow().isoformat() + "Z",
                    job_id,
                    JobStatus.QUEUED.value,
                ),
            )

            if cursor.rowcount == 0:
                # Either job doesn't exist or already claimed
                row = conn.execute(
                    "SELECT status FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()

                if row is None:
                    raise JobNotFoundError(job_id)

                raise ConcurrencyViolationError(
                    job_id,
                    expected_status=JobStatus.QUEUED.value,
                    actual_status=row["status"],
                )

            # Get the updated job
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            job = self._row_to_job(row)

            # Create JobRun atomically in same transaction
            job_run = JobRun.create(
                job_id=job.job_id,
                params_snapshot=job.params,
                template_id=job.template_id,
            )

            conn.execute(
                """
                INSERT INTO job_runs
                (run_id, job_id, template_id, params_snapshot, status, started_at,
                 finished_at, exit_code, error, artifacts, log_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_run.run_id,
                    job_run.job_id,
                    job_run.template_id,
                    json.dumps(job_run.params_snapshot),
                    None,  # status is null until terminal
                    job_run.started_at,
                    job_run.finished_at,
                    job_run.exit_code,
                    job_run.error,
                    json.dumps(job_run.artifacts),
                    job_run.log_path,
                ),
            )

        return job, job_run

    def list_jobs_by_status(self, status: JobStatus, limit: int = 100) -> list[Job]:
        """List jobs by status."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                LIMIT ?
                """,
                (status.value, limit),
            ).fetchall()

        return [self._row_to_job(row) for row in rows]

    def get_next_queued_job(self) -> Optional[Job]:
        """
        Get the next job to dispatch based on queue order.

        From INV-004: priority DESC, position ASC, created_at ASC
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                LIMIT 1
                """,
                (JobStatus.QUEUED.value,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def count_jobs_by_status(self, status: JobStatus) -> int:
        """Count jobs by status."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE status = ?",
                (status.value,),
            ).fetchone()

        return row["count"]

    def count_retry_chain(self, job_id: str) -> int:
        """
        Count the retry chain length for a job.

        From PERSISTENCE_SCHEMA.md Section 2.4:
        Follow retry_of chain to root, return count.
        """
        count = 0
        current_id = job_id

        with self._connection() as conn:
            while current_id:
                row = conn.execute(
                    "SELECT retry_of FROM jobs WHERE job_id = ?",
                    (current_id,),
                ).fetchone()

                if row is None or row["retry_of"] is None:
                    break

                count += 1
                current_id = row["retry_of"]

        return count

    def get_retry_job_for(self, original_job_id: str) -> Optional[Job]:
        """
        Check if a retry job exists for the given job.

        Used for idempotent recovery (RECOVERY_SCENARIOS.md Scenario 3).
        """
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE retry_of = ?",
                (original_job_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    # =========================================================================
    # JobRun Operations
    # =========================================================================

    def create_job_run(self, job_run: JobRun) -> JobRun:
        """Create a new job run."""
        # Verify job exists
        if self.get_job(job_run.job_id) is None:
            raise JobNotFoundError(job_run.job_id)

        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO job_runs
                (run_id, job_id, template_id, params_snapshot, status, started_at,
                 finished_at, exit_code, error, artifacts, log_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_run.run_id,
                    job_run.job_id,
                    job_run.template_id,
                    json.dumps(job_run.params_snapshot),
                    job_run.status.value if job_run.status else None,
                    job_run.started_at,
                    job_run.finished_at,
                    job_run.exit_code,
                    job_run.error,
                    json.dumps(job_run.artifacts),
                    job_run.log_path,
                ),
            )
        return job_run

    def get_job_run(self, run_id: str) -> Optional[JobRun]:
        """Get a job run by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job_run(row)

    def get_job_run_for_job(self, job_id: str) -> Optional[JobRun]:
        """Get the job run for a job (1:1 relationship per DEC-001)."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_runs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job_run(row)

    def _row_to_job_run(self, row: sqlite3.Row) -> JobRun:
        """Convert a database row to a JobRun entity."""
        return JobRun(
            run_id=row["run_id"],
            job_id=row["job_id"],
            template_id=row["template_id"],
            params_snapshot=json.loads(row["params_snapshot"]),
            status=JobRunStatus(row["status"]) if row["status"] else None,
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exit_code=row["exit_code"],
            error=row["error"],
            artifacts=json.loads(row["artifacts"]),
            log_path=row["log_path"],
        )

    def update_job_run(
        self,
        run_id: str,
        status: Optional[JobRunStatus] = None,
        finished_at: Optional[str] = None,
        exit_code: Optional[int] = None,
        error: Optional[str] = None,
        artifacts: Optional[list] = None,
        log_path: Optional[str] = None,
    ) -> JobRun:
        """
        Update a job run.

        Enforces INV-002: Only mutable fields can be updated.
        """
        job_run = self.get_job_run(run_id)
        if job_run is None:
            raise JobRunNotFoundError(run_id)

        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status.value)
        if finished_at is not None:
            updates.append("finished_at = ?")
            values.append(finished_at)
        if exit_code is not None:
            updates.append("exit_code = ?")
            values.append(exit_code)
        if error is not None:
            updates.append("error = ?")
            values.append(error)
        if artifacts is not None:
            updates.append("artifacts = ?")
            values.append(json.dumps(artifacts))
        if log_path is not None:
            updates.append("log_path = ?")
            values.append(log_path)

        if updates:
            values.append(run_id)
            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE job_runs SET {', '.join(updates)} WHERE run_id = ?",
                    values,
                )

        return self.get_job_run(run_id)

    def list_job_runs(self, limit: int = 100) -> list[JobRun]:
        """List job runs ordered by start time (newest first)."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [self._row_to_job_run(row) for row in rows]

    # =========================================================================
    # Direct Reservation Operations (DEC-004)
    # =========================================================================

    def create_reservation(self, reservation: DirectReservation) -> DirectReservation:
        """
        Create a new direct execution reservation.

        Enforces PERS-005: At most ONE reservation may be ACTIVE at any time.
        """
        with self._transaction() as conn:
            # Check for existing active reservation
            row = conn.execute(
                "SELECT reservation_id FROM direct_reservations WHERE status = ?",
                (ReservationStatus.ACTIVE.value,),
            ).fetchone()

            if row is not None:
                raise ReservationConflictError(row["reservation_id"])

            conn.execute(
                """
                INSERT INTO direct_reservations
                (reservation_id, reserved_by, reserved_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reservation.reservation_id,
                    reservation.reserved_by,
                    reservation.reserved_at,
                    reservation.expires_at,
                    reservation.status.value,
                ),
            )

        return reservation

    def get_reservation(self, reservation_id: str) -> Optional[DirectReservation]:
        """Get a reservation by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM direct_reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()

        if row is None:
            return None

        return DirectReservation(
            reservation_id=row["reservation_id"],
            reserved_by=row["reserved_by"],
            reserved_at=row["reserved_at"],
            expires_at=row["expires_at"],
            status=ReservationStatus(row["status"]),
        )

    def get_active_reservation(self) -> Optional[DirectReservation]:
        """Get the currently active reservation, if any."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM direct_reservations WHERE status = ?",
                (ReservationStatus.ACTIVE.value,),
            ).fetchone()

        if row is None:
            return None

        return DirectReservation(
            reservation_id=row["reservation_id"],
            reserved_by=row["reserved_by"],
            reserved_at=row["reserved_at"],
            expires_at=row["expires_at"],
            status=ReservationStatus(row["status"]),
        )

    def update_reservation_status(
        self,
        reservation_id: str,
        status: ReservationStatus,
    ) -> DirectReservation:
        """Update a reservation's status."""
        reservation = self.get_reservation(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        with self._transaction() as conn:
            conn.execute(
                "UPDATE direct_reservations SET status = ? WHERE reservation_id = ?",
                (status.value, reservation_id),
            )

        return self.get_reservation(reservation_id)

    # =========================================================================
    # Recovery Operations (DEC-008, RECOVERY_SCENARIOS.md)
    # =========================================================================

    def get_running_jobs(self) -> list[Job]:
        """
        Get all RUNNING jobs.

        Used for crash recovery (RECOVERY_SCENARIOS.md).
        """
        return self.list_jobs_by_status(JobStatus.RUNNING)

    def get_running_jobs_without_terminal_run(self) -> list[Tuple[Job, Optional[JobRun]]]:
        """
        Get RUNNING jobs with their JobRun status.

        From RECOVERY_SCENARIOS.md Scenario 1:
        - Job RUNNING, no JobRun → Crash before JobRun creation
        - Job RUNNING, JobRun non-terminal → Execution was interrupted
        - Job RUNNING, JobRun terminal → Crash after completion
        """
        result = []

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT j.*, jr.run_id, jr.status as run_status
                FROM jobs j
                LEFT JOIN job_runs jr ON j.job_id = jr.job_id
                WHERE j.status = ?
                """,
                (JobStatus.RUNNING.value,),
            ).fetchall()

        for row in rows:
            job = self._row_to_job(row)

            if row["run_id"] is None:
                job_run = None
            else:
                job_run = self.get_job_run(row["run_id"])

            result.append((job, job_run))

        return result

    def get_failed_runs_without_retry(self, max_attempts: int = 3) -> list[Tuple[Job, JobRun]]:
        """
        Get FAILED JobRuns that don't have a retry Job.

        From RECOVERY_SCENARIOS.md Scenario 3:
        Used to recover from crash during retry creation.
        """
        result = []

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT j.*, jr.run_id
                FROM jobs j
                JOIN job_runs jr ON j.job_id = jr.job_id
                WHERE jr.status = ?
                AND j.finished_at IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM jobs retry
                    WHERE retry.retry_of = j.job_id
                )
                """,
                (JobRunStatus.FAILED.value,),
            ).fetchall()

        for row in rows:
            job = self._row_to_job(row)
            job_run = self.get_job_run(row["run_id"])

            # Check retry chain length
            chain_length = self.count_retry_chain(job.job_id)
            if chain_length < max_attempts:
                result.append((job, job_run))

        return result

    def get_active_reservations_for_recovery(self) -> list[DirectReservation]:
        """
        Get ACTIVE reservations for recovery.

        From RECOVERY_SCENARIOS.md Scenario 2:
        All ACTIVE reservations on startup are stale.
        """
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM direct_reservations WHERE status = ?",
                (ReservationStatus.ACTIVE.value,),
            ).fetchall()

        return [
            DirectReservation(
                reservation_id=row["reservation_id"],
                reserved_by=row["reserved_by"],
                reserved_at=row["reserved_at"],
                expires_at=row["expires_at"],
                status=ReservationStatus(row["status"]),
            )
            for row in rows
        ]

    # =========================================================================
    # JobGroup Operations (DEC-012)
    # =========================================================================

    def create_job_group(self, group: JobGroup) -> JobGroup:
        """Create a new job group."""
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO job_groups
                (group_id, name, status, created_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    group.group_id,
                    group.name,
                    group.status.value,
                    group.created_at,
                    group.started_at,
                    group.finished_at,
                ),
            )
        return group

    def get_job_group(self, group_id: str) -> Optional[JobGroup]:
        """Get a job group by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_groups WHERE group_id = ?",
                (group_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job_group(row)

    def _row_to_job_group(self, row: sqlite3.Row) -> JobGroup:
        """Convert a database row to a JobGroup entity."""
        return JobGroup(
            group_id=row["group_id"],
            name=row["name"],
            status=JobGroupStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def update_job_group(
        self,
        group_id: str,
        status: Optional[JobGroupStatus] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> JobGroup:
        """Update a job group."""
        group = self.get_job_group(group_id)
        if group is None:
            raise InvalidOperationError(f"JobGroup not found: {group_id}")

        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status.value)
        if started_at is not None:
            updates.append("started_at = ?")
            values.append(started_at)
        if finished_at is not None:
            updates.append("finished_at = ?")
            values.append(finished_at)

        if updates:
            values.append(group_id)
            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE job_groups SET {', '.join(updates)} WHERE group_id = ?",
                    values,
                )

        return self.get_job_group(group_id)

    def get_jobs_by_group(self, group_id: str) -> list[Job]:
        """
        Get all jobs in a group, ordered by sequence_number.

        From DEC-012: Jobs execute in order by sequence_number.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE group_id = ?
                ORDER BY sequence_number ASC
                """,
                (group_id,),
            ).fetchall()

        return [self._row_to_job(row) for row in rows]

    def get_next_pending_job_in_group(self, group_id: str) -> Optional[Job]:
        """
        Get the next QUEUED job in a group by sequence order.

        Used for sequential execution: after one job completes,
        get the next one to dispatch.
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE group_id = ? AND status = ?
                ORDER BY sequence_number ASC
                LIMIT 1
                """,
                (group_id, JobStatus.QUEUED.value),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def get_running_job_in_group(self, group_id: str) -> Optional[Job]:
        """
        Get the currently RUNNING job in a group, if any.

        From DEC-012: Only one job in a group runs at a time.
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE group_id = ? AND status = ?
                LIMIT 1
                """,
                (group_id, JobStatus.RUNNING.value),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def count_jobs_in_group_by_status(self, group_id: str) -> dict[str, int]:
        """
        Count jobs in a group by status.

        Used for INV-006: JobGroup Completion Atomicity.
        Returns dict with status -> count mapping.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) as count FROM jobs
                WHERE group_id = ?
                GROUP BY status
                """,
                (group_id,),
            ).fetchall()

        result = {status.value: 0 for status in JobStatus}
        for row in rows:
            result[row["status"]] = row["count"]

        return result

    def get_groups_with_running_jobs(self) -> list[JobGroup]:
        """
        Get all groups that have at least one RUNNING job.

        Used for recovery: identify groups that need completion handling.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT g.* FROM job_groups g
                JOIN jobs j ON g.group_id = j.group_id
                WHERE j.status = ?
                """,
                (JobStatus.RUNNING.value,),
            ).fetchall()

        return [self._row_to_job_group(row) for row in rows]

    def get_non_terminal_groups(self) -> list[JobGroup]:
        """
        Get all job groups that are not in a terminal state.

        Used for recovery: identify groups that may need status updates.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM job_groups
                WHERE status NOT IN (?, ?, ?)
                """,
                (
                    JobGroupStatus.COMPLETED.value,
                    JobGroupStatus.PARTIAL.value,
                    JobGroupStatus.CANCELLED.value,
                ),
            ).fetchall()

        return [self._row_to_job_group(row) for row in rows]

    def compute_group_status(self, group_id: str) -> JobGroupStatus:
        """
        Compute a JobGroup's status from its member Jobs.

        From INV-006 (JobGroup Completion Atomicity):
        - Group terminal status determined only when ALL member jobs terminal
        - RUNNING if any job actively RUNNING (status=RUNNING and no finished_at)
        - PARTIAL if all terminal and any had FAILED JobRun
        - COMPLETED if all terminal and all had COMPLETED JobRuns
        - CANCELLED if all terminal and all CANCELLED (no FAILED runs)

        A job is terminal if:
        - status == CANCELLED, OR
        - finished_at is set (execution completed)

        Args:
            group_id: The group to compute status for

        Returns:
            The computed JobGroupStatus
        """
        jobs = self.get_jobs_by_group(group_id)
        if not jobs:
            return JobGroupStatus.CREATED

        has_active_running = False  # RUNNING with no finished_at
        has_queued = False
        has_cancelled = False
        has_failed_run = False
        all_terminal = True

        for job in jobs:
            # Determine if job is terminal
            # A job is terminal if: cancelled OR finished_at is set
            job_is_terminal = (
                job.status == JobStatus.CANCELLED or
                job.finished_at is not None
            )

            if not job_is_terminal:
                all_terminal = False

                if job.status == JobStatus.RUNNING:
                    # Actively running (not yet finished)
                    has_active_running = True
                elif job.status == JobStatus.QUEUED:
                    has_queued = True
            else:
                # Job is terminal - check the outcome
                if job.status == JobStatus.CANCELLED:
                    has_cancelled = True

                # Check JobRun status for outcome
                job_run = self.get_job_run_for_job(job.job_id)
                if job_run and job_run.status == JobRunStatus.FAILED:
                    has_failed_run = True

        # Determine status based on job states
        if has_active_running:
            return JobGroupStatus.RUNNING

        if has_queued:
            # Still jobs to process
            return JobGroupStatus.QUEUED

        # All jobs are terminal
        if all_terminal:
            if has_failed_run:
                return JobGroupStatus.PARTIAL
            elif has_cancelled and not has_failed_run:
                # All cancelled but no failures (manual cancellation)
                return JobGroupStatus.CANCELLED
            else:
                return JobGroupStatus.COMPLETED

        # Default: still running
        return JobGroupStatus.RUNNING

    def is_job_blocked_by_group(self, job: Job) -> bool:
        """
        Check if a job is blocked from execution due to group constraints.

        From DEC-012: Jobs in a group execute sequentially by sequence_number.
        A job is blocked if:
        1. It belongs to a group
        2. Another job in the same group is RUNNING, OR
        3. There's a job in the same group with lower sequence_number that is QUEUED

        Args:
            job: The job to check

        Returns:
            True if job is blocked, False if eligible for dispatch
        """
        if job.group_id is None:
            return False

        # Check if any job in the group is RUNNING
        running_job = self.get_running_job_in_group(job.group_id)
        if running_job is not None:
            return True

        # Check if there's a QUEUED job with lower sequence number
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count FROM jobs
                WHERE group_id = ?
                AND status = ?
                AND sequence_number < ?
                """,
                (job.group_id, JobStatus.QUEUED.value, job.sequence_number),
            ).fetchone()

        return row["count"] > 0

    def get_next_dispatchable_job(self) -> Optional[Job]:
        """
        Get the next job eligible for dispatch, respecting group constraints.

        This extends get_next_queued_job() to handle JobGroup sequencing:
        - Non-group jobs: dispatch by normal priority/position order
        - Group jobs: only dispatch if no prior sequence job is QUEUED/RUNNING

        From INV-004: priority DESC, position ASC, created_at ASC
        From DEC-012: JobGroup sequential execution
        """
        with self._connection() as conn:
            # Get all QUEUED jobs in dispatch order
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                """,
                (JobStatus.QUEUED.value,),
            ).fetchall()

        for row in rows:
            job = self._row_to_job(row)

            # Check if blocked by group constraints
            if not self.is_job_blocked_by_group(job):
                return job

        return None
