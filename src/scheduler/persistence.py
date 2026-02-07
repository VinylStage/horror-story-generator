"""
Persistence Adapter for Task Scheduler.

Follows PERSISTENCE_SCHEMA.md and DESIGN_GUARDS.md:
- DEC-002: SQLite for task storage with WAL mode
- DEC-008: Queue persistence across restarts
- INV-001: Task immutability after dispatch
- INV-002: TaskRun immutability

Provides:
- Atomic Task + TaskRun creation during dispatch
- Recovery query helpers
- Position-based queue ordering
- Direct reservation persistence

Migration:
- Automatically renames old tables (jobs, job_runs, job_groups) to
  new names (tasks, task_runs, task_groups) on first connect.
- Renames columns: job_id -> task_id, job_type -> task_type.
- Adds execution_mode column to task_groups if missing.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator, Tuple

from .entities import (
    Task,
    TaskRun,
    TaskTemplate,
    Schedule,
    DirectReservation,
    TaskGroup,
    TaskStatus,
    TaskRunStatus,
    TaskGroupStatus,
    ReservationStatus,
)
from .errors import (
    InvalidOperationError,
    TaskNotFoundError,
    TaskRunNotFoundError,
    TemplateNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
    ConcurrencyViolationError,
)


# Gap size for position assignment (from PERSISTENCE_SCHEMA.md Section 3.2)
POSITION_GAP_SIZE = 100


class PersistenceAdapter:
    """
    SQLite-based persistence for all task-related entities.

    From IMPLEMENTATION_PLAN.md Section 1.5:
    - Abstracts SQLite storage
    - CRUD operations for Task, TaskRun, TaskTemplate, Schedule
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
        # First migrate old tables if they exist
        self._migrate_tables()

        with self._transaction() as conn:
            # TaskTemplate table (still job_templates for backward compat)
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

            # TaskGroup table (was job_groups, now task_groups)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_groups (
                    group_id TEXT PRIMARY KEY,
                    name TEXT,
                    status TEXT NOT NULL DEFAULT 'CREATED',
                    execution_mode TEXT NOT NULL DEFAULT 'sequential',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
            """)

            # Task table (was jobs, now tasks)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    template_id TEXT,
                    schedule_id TEXT,
                    group_id TEXT,
                    sequence_number INTEGER,
                    task_type TEXT NOT NULL,
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
                    FOREIGN KEY (group_id) REFERENCES task_groups(group_id),
                    FOREIGN KEY (retry_of) REFERENCES tasks(task_id)
                )
            """)

            # Index for queue ordering (INV-004)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_queue_order
                ON tasks (status, priority DESC, position ASC, created_at ASC)
            """)

            # Index for TaskGroup ordering (DEC-012)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_group_sequence
                ON tasks (group_id, sequence_number)
            """)

            # TaskRun table (was job_runs, now task_runs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    template_id TEXT,
                    params_snapshot TEXT NOT NULL,
                    status TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    exit_code INTEGER,
                    error TEXT,
                    artifacts TEXT NOT NULL DEFAULT '[]',
                    log_path TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Index for task -> runs lookup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_runs_task_id
                ON task_runs (task_id)
            """)

            # Direct reservation table (DEC-004) - unchanged
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

    def _migrate_tables(self) -> None:
        """Migrate old table names (jobs, job_runs, job_groups) to new names (tasks, task_runs, task_groups).

        Uses SQLite ALTER TABLE RENAME TO for safe migration.
        Also renames columns: job_id -> task_id, job_type -> task_type.
        Adds execution_mode column to task_groups if missing.
        """
        if self.db_path == ":memory:":
            return

        try:
            conn = self._get_connection()
            try:
                # Check if old tables exist
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}

                if "jobs" in tables and "tasks" not in tables:
                    # Rename job_groups -> task_groups first (referenced by jobs)
                    if "job_groups" in tables:
                        conn.execute("ALTER TABLE job_groups RENAME TO task_groups")
                        # Add execution_mode column if missing
                        try:
                            conn.execute("ALTER TABLE task_groups ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'sequential'")
                        except sqlite3.OperationalError:
                            pass  # Column already exists

                    # Rename jobs -> tasks
                    conn.execute("ALTER TABLE jobs RENAME TO tasks")
                    # Rename columns
                    try:
                        conn.execute("ALTER TABLE tasks RENAME COLUMN job_id TO task_id")
                        conn.execute("ALTER TABLE tasks RENAME COLUMN job_type TO task_type")
                    except sqlite3.OperationalError:
                        pass  # Columns already renamed or SQLite version doesn't support

                    # Rename job_runs -> task_runs
                    if "job_runs" in tables:
                        conn.execute("ALTER TABLE job_runs RENAME TO task_runs")
                        try:
                            conn.execute("ALTER TABLE task_runs RENAME COLUMN job_id TO task_id")
                        except sqlite3.OperationalError:
                            pass

                    # Drop old indexes and they'll be recreated
                    for idx in ["idx_jobs_queue_order", "idx_jobs_group_sequence", "idx_job_runs_job_id"]:
                        try:
                            conn.execute(f"DROP INDEX IF EXISTS {idx}")
                        except sqlite3.OperationalError:
                            pass

                    conn.commit()

                elif "task_groups" in tables:
                    # Tables already migrated, but check for execution_mode column
                    cols = {row[1] for row in conn.execute("PRAGMA table_info(task_groups)").fetchall()}
                    if "execution_mode" not in cols:
                        conn.execute("ALTER TABLE task_groups ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'sequential'")
                        conn.commit()

                elif "job_groups" in tables:
                    # job_groups exists but jobs doesn't and tasks doesn't - add execution_mode
                    cols = {row[1] for row in conn.execute("PRAGMA table_info(job_groups)").fetchall()}
                    if "execution_mode" not in cols:
                        conn.execute("ALTER TABLE job_groups ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'sequential'")
                        conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # Migration is best-effort; fresh DBs skip this

    # =========================================================================
    # TaskTemplate Operations
    # =========================================================================

    def create_template(self, template: TaskTemplate) -> TaskTemplate:
        """Create a new task template."""
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
                    template.task_type,
                    json.dumps(template.default_params),
                    json.dumps(template.retry_policy),
                    template.description,
                    template.created_at,
                    template.updated_at,
                ),
            )
        return template

    def get_template(self, template_id: str) -> Optional[TaskTemplate]:
        """Get a task template by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()

        if row is None:
            return None

        return TaskTemplate(
            template_id=row["template_id"],
            name=row["name"],
            task_type=row["job_type"],
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
    ) -> TaskTemplate:
        """
        Update a task template.

        Note: Changes apply only to future Tasks (INV-005).
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

    def list_templates(self) -> list[TaskTemplate]:
        """List all task templates."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_templates ORDER BY created_at DESC"
            ).fetchall()

        return [
            TaskTemplate(
                template_id=row["template_id"],
                name=row["name"],
                task_type=row["job_type"],
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
    # Task Operations
    # =========================================================================

    def create_task(self, task: Task) -> Task:
        """
        Create a new task with automatic position assignment.

        From PERSISTENCE_SCHEMA.md Section 3.2:
        Position = max(position for same priority) + GAP_SIZE
        """
        with self._transaction() as conn:
            # Assign position using gap strategy
            row = conn.execute(
                """
                SELECT MAX(position) as max_pos FROM tasks
                WHERE status = ? AND priority = ?
                """,
                (TaskStatus.QUEUED.value, task.priority),
            ).fetchone()

            max_pos = row["max_pos"] if row["max_pos"] is not None else 0
            task.position = max_pos + POSITION_GAP_SIZE

            conn.execute(
                """
                INSERT INTO tasks
                (task_id, template_id, schedule_id, group_id, sequence_number, task_type, params, status,
                 priority, position, retry_of, created_at, queued_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.template_id,
                    task.schedule_id,
                    task.group_id,
                    task.sequence_number,
                    task.task_type,
                    json.dumps(task.params),
                    task.status.value,
                    task.priority,
                    task.position,
                    task.retry_of,
                    task.created_at,
                    task.queued_at,
                    task.started_at,
                    task.finished_at,
                ),
            )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert a database row to a Task entity."""
        return Task(
            task_id=row["task_id"],
            template_id=row["template_id"],
            schedule_id=row["schedule_id"],
            group_id=row["group_id"],
            sequence_number=row["sequence_number"],
            task_type=row["task_type"],
            params=json.loads(row["params"]),
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            position=row["position"],
            retry_of=row["retry_of"],
            created_at=row["created_at"],
            queued_at=row["queued_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        priority: Optional[int] = None,
        position: Optional[int] = None,
        params: Optional[dict] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> Task:
        """
        Update a task.

        Enforces INV-001: Cannot modify params after dispatch.
        """
        task = self.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        # Enforce INV-001: params immutable after RUNNING
        if params is not None and task.status in (TaskStatus.RUNNING, TaskStatus.CANCELLED):
            raise InvalidOperationError("Cannot modify params after dispatch (INV-001)")

        # Enforce: priority/position immutable after RUNNING
        if (priority is not None or position is not None) and task.status != TaskStatus.QUEUED:
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
            values.append(task_id)
            with self._transaction() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
                    values,
                )

        return self.get_task(task_id)

    def atomic_claim_task(self, task_id: str) -> Tuple[Task, TaskRun]:
        """
        Atomically transition task QUEUED -> RUNNING and create TaskRun.

        From PERSISTENCE_SCHEMA.md Section 5.1:
        A Task MUST NOT remain in RUNNING status without a corresponding TaskRun.

        From PERSISTENCE_SCHEMA.md Section 5.3:
        Uses atomic claim to prevent duplicate execution.

        Raises:
            TaskNotFoundError: If task doesn't exist
            ConcurrencyViolationError: If task is not QUEUED (already claimed)
        """
        with self._transaction() as conn:
            # Atomic claim with status check
            cursor = conn.execute(
                """
                UPDATE tasks
                SET status = ?, started_at = ?
                WHERE task_id = ? AND status = ?
                """,
                (
                    TaskStatus.RUNNING.value,
                    datetime.utcnow().isoformat() + "Z",
                    task_id,
                    TaskStatus.QUEUED.value,
                ),
            )

            if cursor.rowcount == 0:
                # Either task doesn't exist or already claimed
                row = conn.execute(
                    "SELECT status FROM tasks WHERE task_id = ?",
                    (task_id,),
                ).fetchone()

                if row is None:
                    raise TaskNotFoundError(task_id)

                raise ConcurrencyViolationError(
                    task_id,
                    expected_status=TaskStatus.QUEUED.value,
                    actual_status=row["status"],
                )

            # Get the updated task
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            task = self._row_to_task(row)

            # Create TaskRun atomically in same transaction
            task_run = TaskRun.create(
                task_id=task.task_id,
                params_snapshot=task.params,
                template_id=task.template_id,
            )

            conn.execute(
                """
                INSERT INTO task_runs
                (run_id, task_id, template_id, params_snapshot, status, started_at,
                 finished_at, exit_code, error, artifacts, log_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_run.run_id,
                    task_run.task_id,
                    task_run.template_id,
                    json.dumps(task_run.params_snapshot),
                    None,  # status is null until terminal
                    task_run.started_at,
                    task_run.finished_at,
                    task_run.exit_code,
                    task_run.error,
                    json.dumps(task_run.artifacts),
                    task_run.log_path,
                ),
            )

        return task, task_run

    def list_tasks_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        """List tasks by status."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                LIMIT ?
                """,
                (status.value, limit),
            ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def list_tasks(self, limit: int = 100) -> list[Task]:
        """List all tasks ordered by created_at DESC."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def get_next_queued_task(self) -> Optional[Task]:
        """
        Get the next task to dispatch based on queue order.

        From INV-004: priority DESC, position ASC, created_at ASC
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                LIMIT 1
                """,
                (TaskStatus.QUEUED.value,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def count_tasks_by_status(self, status: TaskStatus) -> int:
        """Count tasks by status."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE status = ?",
                (status.value,),
            ).fetchone()

        return row["count"]

    def count_retry_chain(self, task_id: str) -> int:
        """
        Count the retry chain length for a task.

        From PERSISTENCE_SCHEMA.md Section 2.4:
        Follow retry_of chain to root, return count.
        """
        count = 0
        current_id = task_id

        with self._connection() as conn:
            while current_id:
                row = conn.execute(
                    "SELECT retry_of FROM tasks WHERE task_id = ?",
                    (current_id,),
                ).fetchone()

                if row is None or row["retry_of"] is None:
                    break

                count += 1
                current_id = row["retry_of"]

        return count

    def get_retry_task_for(self, original_task_id: str) -> Optional[Task]:
        """
        Check if a retry task exists for the given task.

        Used for idempotent recovery (RECOVERY_SCENARIOS.md Scenario 3).
        """
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE retry_of = ?",
                (original_task_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    # =========================================================================
    # TaskRun Operations
    # =========================================================================

    def create_task_run(self, task_run: TaskRun) -> TaskRun:
        """Create a new task run."""
        # Verify task exists
        if self.get_task(task_run.task_id) is None:
            raise TaskNotFoundError(task_run.task_id)

        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO task_runs
                (run_id, task_id, template_id, params_snapshot, status, started_at,
                 finished_at, exit_code, error, artifacts, log_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_run.run_id,
                    task_run.task_id,
                    task_run.template_id,
                    json.dumps(task_run.params_snapshot),
                    task_run.status.value if task_run.status else None,
                    task_run.started_at,
                    task_run.finished_at,
                    task_run.exit_code,
                    task_run.error,
                    json.dumps(task_run.artifacts),
                    task_run.log_path,
                ),
            )
        return task_run

    def get_task_run(self, run_id: str) -> Optional[TaskRun]:
        """Get a task run by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task_run(row)

    def get_task_run_for_task(self, task_id: str) -> Optional[TaskRun]:
        """Get the task run for a task (1:1 relationship per DEC-001)."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task_run(row)

    def _row_to_task_run(self, row: sqlite3.Row) -> TaskRun:
        """Convert a database row to a TaskRun entity."""
        return TaskRun(
            run_id=row["run_id"],
            task_id=row["task_id"],
            template_id=row["template_id"],
            params_snapshot=json.loads(row["params_snapshot"]),
            status=TaskRunStatus(row["status"]) if row["status"] else None,
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exit_code=row["exit_code"],
            error=row["error"],
            artifacts=json.loads(row["artifacts"]),
            log_path=row["log_path"],
        )

    def update_task_run(
        self,
        run_id: str,
        status: Optional[TaskRunStatus] = None,
        finished_at: Optional[str] = None,
        exit_code: Optional[int] = None,
        error: Optional[str] = None,
        artifacts: Optional[list] = None,
        log_path: Optional[str] = None,
    ) -> TaskRun:
        """
        Update a task run.

        Enforces INV-002: Only mutable fields can be updated.
        """
        task_run = self.get_task_run(run_id)
        if task_run is None:
            raise TaskRunNotFoundError(run_id)

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
                    f"UPDATE task_runs SET {', '.join(updates)} WHERE run_id = ?",
                    values,
                )

        return self.get_task_run(run_id)

    def list_task_runs(self, limit: int = 100) -> list[TaskRun]:
        """List task runs ordered by start time (newest first)."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [self._row_to_task_run(row) for row in rows]

    def get_task_run_stats(self) -> dict[str, int]:
        """
        Get cumulative task run statistics by status.

        Returns:
            Dict with keys: total_executed, succeeded, failed, skipped
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM task_runs
                WHERE status IS NOT NULL
                GROUP BY status
                """
            ).fetchall()

        stats = {
            "total_executed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
        }

        for row in rows:
            status = row["status"]
            count = row["count"]
            stats["total_executed"] += count

            if status == TaskRunStatus.COMPLETED.value:
                stats["succeeded"] = count
            elif status == TaskRunStatus.FAILED.value:
                stats["failed"] = count
            elif status == TaskRunStatus.SKIPPED.value:
                stats["skipped"] = count

        return stats

    def count_cancelled_tasks(self) -> int:
        """Count tasks with CANCELLED status."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE status = ?",
                (TaskStatus.CANCELLED.value,),
            ).fetchone()

        return row["count"]

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

    def get_running_tasks(self) -> list[Task]:
        """
        Get all RUNNING tasks.

        Used for crash recovery (RECOVERY_SCENARIOS.md).
        """
        return self.list_tasks_by_status(TaskStatus.RUNNING)

    def get_running_tasks_without_terminal_run(self) -> list[Tuple[Task, Optional[TaskRun]]]:
        """
        Get RUNNING tasks with their TaskRun status.

        From RECOVERY_SCENARIOS.md Scenario 1:
        - Task RUNNING, no TaskRun -> Crash before TaskRun creation
        - Task RUNNING, TaskRun non-terminal -> Execution was interrupted
        - Task RUNNING, TaskRun terminal -> Crash after completion
        """
        result = []

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT t.*, tr.run_id, tr.status as run_status
                FROM tasks t
                LEFT JOIN task_runs tr ON t.task_id = tr.task_id
                WHERE t.status = ?
                """,
                (TaskStatus.RUNNING.value,),
            ).fetchall()

        for row in rows:
            task = self._row_to_task(row)

            if row["run_id"] is None:
                task_run = None
            else:
                task_run = self.get_task_run(row["run_id"])

            result.append((task, task_run))

        return result

    def get_failed_runs_without_retry(self, max_attempts: int = 3) -> list[Tuple[Task, TaskRun]]:
        """
        Get FAILED TaskRuns that don't have a retry Task.

        From RECOVERY_SCENARIOS.md Scenario 3:
        Used to recover from crash during retry creation.
        """
        result = []

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT t.*, tr.run_id
                FROM tasks t
                JOIN task_runs tr ON t.task_id = tr.task_id
                WHERE tr.status = ?
                AND t.finished_at IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM tasks retry
                    WHERE retry.retry_of = t.task_id
                )
                """,
                (TaskRunStatus.FAILED.value,),
            ).fetchall()

        for row in rows:
            task = self._row_to_task(row)
            task_run = self.get_task_run(row["run_id"])

            # Check retry chain length
            chain_length = self.count_retry_chain(task.task_id)
            if chain_length < max_attempts:
                result.append((task, task_run))

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
    # TaskGroup Operations (DEC-012)
    # =========================================================================

    def create_task_group(self, group: TaskGroup) -> TaskGroup:
        """Create a new task group."""
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO task_groups
                (group_id, name, status, execution_mode, created_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group.group_id,
                    group.name,
                    group.status.value,
                    group.execution_mode,
                    group.created_at,
                    group.started_at,
                    group.finished_at,
                ),
            )
        return group

    def get_task_group(self, group_id: str) -> Optional[TaskGroup]:
        """Get a task group by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_groups WHERE group_id = ?",
                (group_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task_group(row)

    def _row_to_task_group(self, row: sqlite3.Row) -> TaskGroup:
        """Convert a database row to a TaskGroup entity."""
        return TaskGroup(
            group_id=row["group_id"],
            name=row["name"],
            status=TaskGroupStatus(row["status"]),
            execution_mode=row["execution_mode"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def update_task_group(
        self,
        group_id: str,
        status: Optional[TaskGroupStatus] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> TaskGroup:
        """Update a task group."""
        group = self.get_task_group(group_id)
        if group is None:
            raise InvalidOperationError(f"TaskGroup not found: {group_id}")

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
                    f"UPDATE task_groups SET {', '.join(updates)} WHERE group_id = ?",
                    values,
                )

        return self.get_task_group(group_id)

    def get_tasks_by_group(self, group_id: str) -> list[Task]:
        """
        Get all tasks in a group, ordered by sequence_number.

        From DEC-012: Tasks execute in order by sequence_number.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE group_id = ?
                ORDER BY sequence_number ASC
                """,
                (group_id,),
            ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def get_next_pending_task_in_group(self, group_id: str) -> Optional[Task]:
        """
        Get the next QUEUED task in a group by sequence order.

        Used for sequential execution: after one task completes,
        get the next one to dispatch.
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE group_id = ? AND status = ?
                ORDER BY sequence_number ASC
                LIMIT 1
                """,
                (group_id, TaskStatus.QUEUED.value),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def get_running_task_in_group(self, group_id: str) -> Optional[Task]:
        """
        Get the currently RUNNING task in a group, if any.

        From DEC-012: Only one task in a group runs at a time (sequential mode).

        Note: A task is "actively running" if status=RUNNING AND finished_at IS NULL.
        Tasks with finished_at set have completed (regardless of status).
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE group_id = ? AND status = ? AND finished_at IS NULL
                LIMIT 1
                """,
                (group_id, TaskStatus.RUNNING.value),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def count_tasks_in_group_by_status(self, group_id: str) -> dict[str, int]:
        """
        Count tasks in a group by status.

        Used for INV-006: TaskGroup Completion Atomicity.
        Returns dict with status -> count mapping.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) as count FROM tasks
                WHERE group_id = ?
                GROUP BY status
                """,
                (group_id,),
            ).fetchall()

        result = {status.value: 0 for status in TaskStatus}
        for row in rows:
            result[row["status"]] = row["count"]

        return result

    def get_groups_with_running_tasks(self) -> list[TaskGroup]:
        """
        Get all groups that have at least one RUNNING task.

        Used for recovery: identify groups that need completion handling.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT g.* FROM task_groups g
                JOIN tasks t ON g.group_id = t.group_id
                WHERE t.status = ?
                """,
                (TaskStatus.RUNNING.value,),
            ).fetchall()

        return [self._row_to_task_group(row) for row in rows]

    def get_non_terminal_groups(self) -> list[TaskGroup]:
        """
        Get all task groups that are not in a terminal state.

        Used for recovery: identify groups that may need status updates.
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_groups
                WHERE status NOT IN (?, ?, ?)
                """,
                (
                    TaskGroupStatus.COMPLETED.value,
                    TaskGroupStatus.PARTIAL.value,
                    TaskGroupStatus.CANCELLED.value,
                ),
            ).fetchall()

        return [self._row_to_task_group(row) for row in rows]

    def compute_group_status(self, group_id: str) -> TaskGroupStatus:
        """
        Compute a TaskGroup's status from its member Tasks.

        From INV-006 (TaskGroup Completion Atomicity):
        - Group terminal status determined only when ALL member tasks terminal
        - RUNNING if any task actively RUNNING (status=RUNNING and no finished_at)
        - PARTIAL if all terminal and any had FAILED TaskRun
        - COMPLETED if all terminal and all had COMPLETED TaskRuns
        - CANCELLED if all terminal and all CANCELLED (no FAILED runs)

        A task is terminal if:
        - status == CANCELLED, OR
        - finished_at is set (execution completed)

        Args:
            group_id: The group to compute status for

        Returns:
            The computed TaskGroupStatus
        """
        tasks = self.get_tasks_by_group(group_id)
        if not tasks:
            return TaskGroupStatus.CREATED

        has_active_running = False  # RUNNING with no finished_at
        has_queued = False
        has_cancelled = False
        has_failed_run = False
        all_terminal = True

        for task in tasks:
            # Determine if task is terminal
            # A task is terminal if: cancelled OR finished_at is set
            task_is_terminal = (
                task.status == TaskStatus.CANCELLED or
                task.finished_at is not None
            )

            if not task_is_terminal:
                all_terminal = False

                if task.status == TaskStatus.RUNNING:
                    # Actively running (not yet finished)
                    has_active_running = True
                elif task.status == TaskStatus.QUEUED:
                    has_queued = True
            else:
                # Task is terminal - check the outcome
                if task.status == TaskStatus.CANCELLED:
                    has_cancelled = True

                # Check TaskRun status for outcome
                task_run = self.get_task_run_for_task(task.task_id)
                if task_run and task_run.status == TaskRunStatus.FAILED:
                    has_failed_run = True

        # Determine status based on task states
        if has_active_running:
            return TaskGroupStatus.RUNNING

        if has_queued:
            # Still tasks to process
            return TaskGroupStatus.QUEUED

        # All tasks are terminal
        if all_terminal:
            if has_failed_run:
                return TaskGroupStatus.PARTIAL
            elif has_cancelled and not has_failed_run:
                # All cancelled but no failures (manual cancellation)
                return TaskGroupStatus.CANCELLED
            else:
                return TaskGroupStatus.COMPLETED

        # Default: still running
        return TaskGroupStatus.RUNNING

    def is_task_blocked_by_group(self, task: Task) -> bool:
        """
        Check if a task is blocked from execution due to group constraints.

        From DEC-012: Tasks in a group execute sequentially by sequence_number.
        A task is blocked if:
        1. It belongs to a group
        2. The group's execution_mode is "sequential" (concurrent groups don't block)
        3. Another task in the same group is RUNNING, OR
        4. There's a task in the same group with lower sequence_number that is QUEUED

        Args:
            task: The task to check

        Returns:
            True if task is blocked, False if eligible for dispatch
        """
        if task.group_id is None:
            return False

        # Check execution mode - concurrent groups don't block
        group = self.get_task_group(task.group_id)
        if group is not None and group.execution_mode == "concurrent":
            return False

        # Check if any task in the group is RUNNING
        running_task = self.get_running_task_in_group(task.group_id)
        if running_task is not None:
            return True

        # Check if there's a QUEUED task with lower sequence number
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count FROM tasks
                WHERE group_id = ?
                AND status = ?
                AND sequence_number < ?
                """,
                (task.group_id, TaskStatus.QUEUED.value, task.sequence_number),
            ).fetchone()

        return row["count"] > 0

    def get_next_dispatchable_task(self) -> Optional[Task]:
        """
        Get the next task eligible for dispatch, respecting group constraints.

        This extends get_next_queued_task() to handle TaskGroup sequencing:
        - Non-group tasks: dispatch by normal priority/position order
        - Group tasks: only dispatch if not blocked by group constraints

        From INV-004: priority DESC, position ASC, created_at ASC
        From DEC-012: TaskGroup sequential execution
        """
        with self._connection() as conn:
            # Get all QUEUED tasks in dispatch order
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY priority DESC, position ASC, created_at ASC
                """,
                (TaskStatus.QUEUED.value,),
            ).fetchall()

        for row in rows:
            task = self._row_to_task(row)

            # Check if blocked by group constraints
            if not self.is_task_blocked_by_group(task):
                return task

        return None

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================

    # Task operations (old Job names)
    create_job = create_task
    get_job = get_task
    _row_to_job = _row_to_task
    update_job = update_task
    atomic_claim_job = atomic_claim_task
    list_jobs_by_status = list_tasks_by_status
    list_jobs = list_tasks
    get_next_queued_job = get_next_queued_task
    count_jobs_by_status = count_tasks_by_status
    get_retry_job_for = get_retry_task_for

    # TaskRun operations (old JobRun names)
    create_job_run = create_task_run
    get_job_run = get_task_run
    get_job_run_for_job = get_task_run_for_task
    _row_to_job_run = _row_to_task_run
    update_job_run = update_task_run
    list_job_runs = list_task_runs
    get_job_run_stats = get_task_run_stats
    count_cancelled_jobs = count_cancelled_tasks

    # Recovery operations (old Job names)
    get_running_jobs = get_running_tasks
    get_running_jobs_without_terminal_run = get_running_tasks_without_terminal_run

    # TaskGroup operations (old JobGroup names)
    create_job_group = create_task_group
    get_job_group = get_task_group
    _row_to_job_group = _row_to_task_group
    update_job_group = update_task_group
    get_jobs_by_group = get_tasks_by_group
    get_next_pending_job_in_group = get_next_pending_task_in_group
    get_running_job_in_group = get_running_task_in_group
    count_jobs_in_group_by_status = count_tasks_in_group_by_status
    get_groups_with_running_jobs = get_groups_with_running_tasks
    is_job_blocked_by_group = is_task_blocked_by_group
    get_next_dispatchable_job = get_next_dispatchable_task
