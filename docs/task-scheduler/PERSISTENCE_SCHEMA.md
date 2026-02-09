# Task Scheduler Persistence Schema Design

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 2.0.0 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Purpose

This document defines the persistence layer design that guarantees:

- **Deterministic execution order** — Queue ordering is never ambiguous
- **Crash-safe recovery** — No silent data loss on unexpected termination
- **Resume-on-restart** — QUEUED tasks survive scheduler restarts
- **Atomicity** — State transitions are all-or-nothing

This design makes queue corruption or ambiguity **practically impossible**.

---

## Authoritative References

| Document | Constraint |
|----------|------------|
| DESIGN_GUARDS.md DEC-002 | SQLite for task storage |
| DESIGN_GUARDS.md DEC-008 | Queue persistence across restarts |
| DESIGN_GUARDS.md INV-001 | Task immutability after dispatch |
| DESIGN_GUARDS.md INV-002 | TaskRun immutability |
| IMPLEMENTATION_PLAN.md | Component responsibilities |

---

## 1. Storage Roles

### 1.1 Two-Tier Storage Model

The persistence layer uses two storage tiers with distinct responsibilities:

| Tier | Technology | Purpose |
|------|------------|---------|
| **Durable Store** | SQLite | Source of truth for all task state |
| **Volatile Cache** | In-memory (dict/redis-like) | Ephemeral operational state |

---

### 1.2 Durable Store (SQLite)

**Why It Exists**:
- Single source of truth for task state
- Survives process crashes and restarts
- Provides ACID transactions for state transitions
- Enables queue order reconstruction

**What MUST Be Stored**:
| Data | Reason |
|------|--------|
| Task entities | Primary work units, must survive restart |
| TaskRun entities | Audit trail, immutable history |
| TaskTemplate entities | Reusable task definitions |
| Schedule entities | Cron trigger configurations |
| Queue ordering metadata | Priority, position, created_at |
| Retry chain references | `retry_of` linkage |
| Direct reservation flag | Survives crash during reservation |

**Persistence Guarantees**:
- Write-ahead logging (WAL) mode enabled
- All state transitions are transactional
- No in-memory-only task state

---

### 1.3 Volatile Cache (In-Memory)

**Why It Exists**:
- Fast access to frequently-read data
- Reduce SQLite query load during dispatch loop
- Cache computed values (e.g., queue length)

**What MAY Be Stored**:
| Data | Reason |
|------|--------|
| Queue snapshot (read-only) | Fast dispatch decisions |
| Active worker references | Process handles, not reconstructable |
| Temporary computation results | Performance optimization |

**What MUST NOT Be Stored (Volatile Only)**:
| Data | Why Not |
|------|---------|
| Task status | Would be lost on crash |
| Queue position | Would corrupt ordering on restart |
| TaskRun data | Audit trail must be durable |
| Retry decisions | Must survive scheduler restart |
| Direct API reservation | Must survive crash to prevent duplicate execution |

**Cache Invalidation Rule**:
```
On any SQLite write → invalidate relevant cache entries
On startup → rebuild cache from SQLite (cold start)
```

---

### 1.4 Storage Decision Matrix

| Question | Answer |
|----------|--------|
| "Can this data be reconstructed from SQLite?" | If YES → may cache in memory |
| "Would losing this data cause incorrect behavior?" | If YES → must be in SQLite |
| "Does this data affect queue ordering?" | If YES → must be in SQLite |
| "Is this transient process state (PID, handle)?" | If YES → volatile only is acceptable |

---

## 2. Core Entities & Persistence Mapping

### 2.1 Task

**Primary Key**: `task_id` (UUID, immutable)

**Required Fields**:
| Field | Type | Mutability | Purpose |
|-------|------|------------|---------|
| `task_id` | UUID | Immutable | Unique identifier |
| `template_id` | UUID (nullable) | Immutable | Source template reference |
| `schedule_id` | UUID (nullable) | Immutable | Triggering schedule (if any) |
| `group_id` | UUID (nullable) | Immutable | TaskGroup membership |
| `task_type` | String | Immutable | "story" / "research" |
| `params` | JSON | Immutable after RUNNING | Execution parameters |
| `status` | Enum | Mutable | QUEUED / RUNNING / CANCELLED |
| `priority` | Integer | Mutable (while QUEUED) | Dispatch priority |
| `position` | Integer | Mutable (while QUEUED) | Queue position |
| `retry_of` | UUID (nullable) | Immutable | Previous task in retry chain |
| `created_at` | Timestamp | Immutable | Creation time |
| `queued_at` | Timestamp | Immutable | When added to queue |
| `started_at` | Timestamp (nullable) | Write-once | Execution start |
| `finished_at` | Timestamp (nullable) | Write-once | Execution end |

**Lifecycle Ownership**: QueueManager (creation, ordering), Dispatcher (status transitions)

**Persistence Timing**:
| Event | Write Action |
|-------|--------------|
| Task created | INSERT with status=QUEUED |
| Task dispatched | UPDATE status=RUNNING, started_at=now |
| Task completed | UPDATE finished_at=now (status unchanged; outcome in TaskRun) |
| Task cancelled | UPDATE status=CANCELLED |
| Position changed | UPDATE position (within transaction) |

---

### 2.2 TaskRun

**Primary Key**: `run_id` (UUID, immutable)

**Required Fields**:
| Field | Type | Mutability | Purpose |
|-------|------|------------|---------|
| `run_id` | UUID | Immutable | Unique identifier |
| `task_id` | UUID | Immutable | Parent task reference |
| `template_id` | UUID (nullable) | Immutable | Snapshot of template used |
| `params_snapshot` | JSON | Immutable | Snapshot of execution params |
| `status` | Enum | Write-once | COMPLETED / FAILED / SKIPPED |
| `started_at` | Timestamp | Immutable | Execution start |
| `finished_at` | Timestamp (nullable) | Write-once | Execution end |
| `exit_code` | Integer (nullable) | Write-once | Process exit code |
| `error` | Text (nullable) | Write-once | Error message if failed |
| `artifacts` | JSON | Append-only | Produced file paths |
| `log_path` | String (nullable) | Write-once | Execution log location |

**Lifecycle Ownership**: Executor (creation and finalization)

**Persistence Timing**:
| Event | Write Action |
|-------|--------------|
| Execution starts | INSERT with started_at=now, status pending |
| Execution succeeds | UPDATE status=COMPLETED, finished_at, artifacts |
| Execution fails | UPDATE status=FAILED, finished_at, error |
| Execution skipped | UPDATE status=SKIPPED, finished_at |

**Critical Invariant (INV-002)**:
```
Once status is set to terminal (COMPLETED/FAILED/SKIPPED),
only finished_at, exit_code, error, and artifacts may be updated.
All other fields are permanently immutable.
```

---

### 2.3 Schedule

**Primary Key**: `schedule_id` (UUID, immutable)

**Required Fields**:
| Field | Type | Mutability | Purpose |
|-------|------|------------|---------|
| `schedule_id` | UUID | Immutable | Unique identifier |
| `template_id` | UUID | Mutable | Target template |
| `name` | String | Mutable | Human-readable label |
| `cron_expression` | String | Mutable | Cron pattern |
| `timezone` | String | Mutable | Timezone for cron (default: UTC) |
| `enabled` | Boolean | Mutable | Active/inactive toggle |
| `param_overrides` | JSON (nullable) | Mutable | Override template params |
| `last_triggered_at` | Timestamp (nullable) | Write-on-trigger | Last successful trigger |
| `next_trigger_at` | Timestamp (nullable) | Computed | Next scheduled trigger |
| `created_at` | Timestamp | Immutable | Creation time |

**Lifecycle Ownership**: ScheduleTrigger (trigger events), API (CRUD)

**Persistence Timing**:
| Event | Write Action |
|-------|--------------|
| Schedule created | INSERT |
| Schedule updated | UPDATE (cron, timezone, enabled, etc.) |
| Trigger fires | UPDATE last_triggered_at |

---

### 2.4 Retry Metadata

Retry information is stored **within the Task entity** via `retry_of` field.

**Chain Structure**:
```
Task1 (original)      → retry_of: NULL
  └── Task2 (retry)   → retry_of: Task1.task_id
        └── Task3     → retry_of: Task2.task_id
              └── Task4 → retry_of: Task3.task_id (max reached)
```

**Retry Count Calculation**:
```
To count attempts for TaskN:
  1. Start with attempt = 0
  2. Follow retry_of chain to root
  3. Count chain length
  4. Return count
```

**No Separate Retry Table**: All retry metadata is derived from Task entities and their `retry_of` relationships. This ensures:
- No orphaned retry records
- Chain is always traversable
- Single source of truth

---

### 2.5 Direct Execution Reservation

**Storage Location**: Dedicated record in SQLite (not in-memory only)

**Required Fields**:
| Field | Type | Purpose |
|-------|------|---------|
| `reservation_id` | UUID | Unique identifier |
| `reserved_at` | Timestamp | When reservation was made |
| `reserved_by` | String | Identifier of reserving process/request |
| `status` | Enum | ACTIVE / RELEASED / EXPIRED |
| `expires_at` | Timestamp | Timeout for stale reservations |

**Why Persisted**:
- If scheduler crashes during Direct API handling, restart must detect stale reservation
- Prevents queue dispatch while reservation is active
- Enables timeout-based recovery

**Lifecycle**:
| Event | Write Action |
|-------|--------------|
| Direct API starts | INSERT with status=ACTIVE |
| Direct execution completes | UPDATE status=RELEASED |
| Scheduler restart finds ACTIVE | Check expiry → EXPIRED if stale |

**Single Reservation Rule**:
```
At most ONE reservation may be ACTIVE at any time.
Attempt to reserve while ACTIVE → wait or reject.
```

---

## 3. Queue Ordering Model

### 3.1 Ordering Representation

Queue order is determined by three persisted fields:

| Field | Sort Order | Purpose |
|-------|------------|---------|
| `priority` | DESC | Higher priority tasks first |
| `position` | ASC | Explicit ordering within priority |
| `created_at` | ASC | Tiebreaker for equal priority+position |

**Ordering Query Pattern**:
```
SELECT * FROM tasks
WHERE status = 'QUEUED'
ORDER BY priority DESC, position ASC, created_at ASC
LIMIT 1
```

---

### 3.2 Position Assignment Strategy

**On Task Insert**:
```
1. Find max position among QUEUED tasks with same priority
2. Assign position = max + GAP_SIZE (e.g., 100)
3. If no tasks exist at priority, position = GAP_SIZE
```

**Gap Strategy Benefits**:
- Insertions between tasks don't require shifting
- Reordering is a simple position swap
- Periodic normalization (optional) to prevent overflow

**Position Normalization** (periodic maintenance):
```
1. Load all QUEUED tasks ordered by (priority, position, created_at)
2. Reassign positions: 100, 200, 300, ...
3. Single transaction to prevent inconsistency
```

---

### 3.3 Next-Slot Reservation Persistence

**How It's Represented**:
- Dedicated `direct_reservations` record with status=ACTIVE
- Dispatcher checks for ACTIVE reservation before dispatching

**Dispatcher Logic**:
```
1. Query: SELECT FROM direct_reservations WHERE status = 'ACTIVE'
2. If found:
   a. Do not dispatch any QUEUED task
   b. Wait for reservation to be RELEASED or EXPIRED
3. If not found:
   a. Proceed with normal dispatch
```

**Fairness Preservation**:
- Reservation does NOT modify queue order
- Queue remains intact during reservation
- First QUEUED task after release is the same as before reservation

---

### 3.4 Persistence Failure During Transition

**Scenario**: SQLite write fails mid-transition

**Mitigation Strategy**:
| Transition | Failure Behavior |
|------------|------------------|
| Task INSERT fails | No task created; caller gets error |
| QUEUED → RUNNING fails | Task remains QUEUED; retry dispatch |
| TaskRun INSERT fails | Task is RUNNING but no record; crash recovery handles |
| Status UPDATE fails | Retry update; if unrecoverable, manual intervention |

**Transaction Boundaries**:
```
Dispatch Transaction:
  BEGIN
    UPDATE task SET status='RUNNING', started_at=now WHERE task_id=?
    INSERT INTO task_runs (run_id, task_id, started_at, ...) VALUES (...)
  COMMIT

If transaction fails → task stays QUEUED, no TaskRun exists.
```

---

## 4. Restart & Recovery Scenarios

### 4.1 Clean Shutdown Restart

**Trigger**: Scheduler receives SIGTERM, completes gracefully

**Pre-Shutdown Actions**:
1. Stop accepting new tasks
2. Wait for RUNNING tasks to complete (grace period)
3. Persist final state
4. Exit

**On Restart**:
| State | Action |
|-------|--------|
| QUEUED tasks | Load into queue, preserve order |
| No RUNNING tasks | Normal (clean shutdown completed them) |
| Direct reservation RELEASED | Normal |

**Result**: Queue resumes exactly where it left off.

---

### 4.2 Crash During RUNNING Task

**Trigger**: Process killed while Task.status = RUNNING

**On Restart**:
```
1. Query: SELECT * FROM tasks WHERE status = 'RUNNING'
2. For each RUNNING task:
   a. Check if TaskRun exists
      → YES with terminal status: Task was finishing, update Task
      → YES without terminal status: Execution was interrupted
      → NO: Crash before TaskRun creation
   b. Mark TaskRun as FAILED (error = "Scheduler crash recovery")
   c. Trigger RetryController evaluation
   d. Fire webhook notification
```

**Why FAILED, Not Resumed**:
- Cannot verify partial execution state
- May have side effects (partial file writes)
- Retry mechanism handles recovery
- Conservative approach prevents duplicate work

---

### 4.3 Crash During Direct API Reservation

**Trigger**: Process killed while direct_reservations.status = ACTIVE

**On Restart**:
```
1. Query: SELECT * FROM direct_reservations WHERE status = 'ACTIVE'
2. For each ACTIVE reservation:
   a. Check expires_at
      → EXPIRED: Update status = 'EXPIRED', resume queue
      → NOT EXPIRED: This should not happen (crash means no response)
   b. Log recovery action
3. Resume normal dispatch
```

**Why Expiration Check**:
- Stale reservations must not block queue forever
- Timeout provides upper bound on blocking
- Recommended expiry: 5-10 minutes

**Direct API Caller Behavior**:
- Caller's request failed (no response received)
- Caller may retry, which creates new reservation
- No duplicate execution (original never started)

---

### 4.4 Crash During Retry Scheduling

**Trigger**: Process killed after TaskRun.status = FAILED but before new retry task created

**On Restart**:
```
1. Query: SELECT jr.*, j.retry_of FROM task_runs jr
          JOIN tasks j ON jr.task_id = j.task_id
          WHERE jr.status = 'FAILED'
          AND j.finished_at IS NOT NULL
2. For each FAILED TaskRun:
   a. Count retry chain length
   b. Check if retry task already exists (retry_of = this task)
      → YES: Retry was created, no action
      → NO and attempts < max: Create retry task now
      → NO and attempts >= max: Mark permanently failed
```

**Idempotency Guarantee**:
- Retry creation is idempotent (check before create)
- If retry exists, skip creation
- If retry doesn't exist and eligible, create it

---

### 4.5 Recovery Decision Matrix

| Pre-Crash State | TaskRun Exists? | TaskRun Terminal? | Recovery Action |
|-----------------|----------------|------------------|-----------------|
| QUEUED | N/A | N/A | Resume in queue (no action) |
| RUNNING | No | N/A | Create FAILED TaskRun, retry |
| RUNNING | Yes | No | Update to FAILED, retry |
| RUNNING | Yes | Yes | Update Task.finished_at only |
| Direct Reservation ACTIVE | N/A | N/A | Expire if stale, resume queue |

---

## 5. Atomicity & Consistency Rules

### 5.1 Invariant: No RUNNING Without TaskRun

**Rule**: A Task MUST NOT remain in RUNNING status without a corresponding TaskRun record.

**Enforcement**:
```
Dispatch Transaction (atomic):
  1. UPDATE task SET status = 'RUNNING'
  2. INSERT task_run

If step 2 fails → transaction rolls back → task stays QUEUED.
```

**Recovery Check**:
```
On startup:
  SELECT j.* FROM tasks j
  LEFT JOIN task_runs jr ON j.task_id = jr.task_id
  WHERE j.status = 'RUNNING' AND jr.run_id IS NULL

If any rows returned → create FAILED TaskRun for each.
```

---

### 5.2 Invariant: No Orphan TaskRuns

**Rule**: A TaskRun MUST NOT exist without a parent Task.

**Enforcement**:
- Foreign key constraint: `task_runs.task_id REFERENCES tasks.task_id`
- TaskRun creation always follows Task existence check

**Cleanup** (defensive, should never trigger):
```
DELETE FROM task_runs
WHERE task_id NOT IN (SELECT task_id FROM tasks)
```

---

### 5.3 Invariant: No Duplicate Execution

**Rule**: A Task MUST NOT be executed more than once.

**Enforcement**:
```
1. Task.status transition: QUEUED → RUNNING is one-way
2. RUNNING task cannot return to QUEUED
3. Dispatch uses atomic claim:

   UPDATE tasks SET status = 'RUNNING'
   WHERE task_id = ? AND status = 'QUEUED'
   RETURNING *

   If 0 rows affected → task was already dispatched (race condition).
```

**Crash Recovery Exception**:
- Crashed RUNNING tasks → FAILED (not re-queued)
- Retry creates NEW Task (different task_id)
- Original task is never re-executed

---

### 5.4 Invariant: Queue Order Determinism

**Rule**: Given the same SQLite state, queue order MUST be identical.

**Enforcement**:
- Order depends only on persisted fields: priority, position, created_at
- No random or time-based tiebreakers beyond created_at
- Position gaps don't affect relative order

**Verification Query**:
```
SELECT task_id, priority, position, created_at
FROM tasks
WHERE status = 'QUEUED'
ORDER BY priority DESC, position ASC, created_at ASC
```

Same input → same output, always.

---

### 5.5 Invariant: Reservation Exclusivity

**Rule**: At most ONE Direct API reservation may be ACTIVE at any time.

**Enforcement**:
```
Before INSERT into direct_reservations:
  1. Check: SELECT COUNT(*) FROM direct_reservations WHERE status = 'ACTIVE'
  2. If count > 0:
     a. Wait for release (with timeout)
     b. OR reject with "resource busy"
  3. If count = 0:
     a. INSERT new reservation
```

**Atomicity**:
```
BEGIN
  SELECT ... FOR UPDATE (lock check)
  INSERT ... (if allowed)
COMMIT
```

---

## 6. Future Extension Points

### 6.1 OQ-001: Concurrency Limits (NOT DECIDED)

**Current Design Impact**: None. Single-worker assumption.

**Future Extension Points**:
| Extension | Schema Change |
|-----------|---------------|
| Global limit (N workers | Add `worker_id` to tasks, track active count |
| Per-type limit | Add `task_type` index, count by type |
| Resource-based | Add `resource_tags` column to tasks |

**Placeholder**:
- `tasks.worker_id` column (nullable) reserved for future use
- No enforcement logic until OQ-001 resolved

---

### 6.2 Distributed Workers (EXPLICITLY NOT IMPLEMENTED)

**Current Constraint**: CON-001 (Single Machine Deployment)

**What This Means**:
- No distributed locking required
- SQLite sufficient (no PostgreSQL/CockroachDB)
- Worker is same process or subprocess

**If Ever Needed** (out of scope):
| Requirement | Change |
|-------------|--------|
| Multiple machines | Replace SQLite with network DB |
| Distributed locks | Add Redis/etcd coordination |
| Worker heartbeats | Add `last_heartbeat_at` column |

**Current Design**: Does NOT accommodate distributed workers. Explicit non-goal.

---

### 6.3 TaskGroup Concurrency (DEFERRED)

**Current State**: TaskGroup execution semantics not fully designed.

**Schema Placeholder**:
- `tasks.group_id` exists
- No `task_groups` table defined yet
- OQ-002 (failure behavior) unresolved

**Future Addition** (when needed):
```
task_groups:
  group_id
  mode (parallel/sequential)
  on_failure (stop/continue/skip)
  status (derived from member tasks)
```

---

## 7. Consistency Checklist

Before any implementation, verify:

- [ ] All Task state transitions are transactional
- [ ] TaskRun is created atomically with RUNNING transition
- [ ] No in-memory-only task state exists
- [ ] Queue order is deterministic from SQLite query
- [ ] Direct reservation survives crash
- [ ] Retry chain is traceable via `retry_of`
- [ ] All invariants have enforcement mechanism
- [ ] Recovery scenarios are documented and tested

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-18 | - | Initial persistence schema design |

---

## Related Documents

- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [ENTITY_RELATIONSHIPS.md](./ENTITY_RELATIONSHIPS.md) - 엔티티 관계 정의
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [RECOVERY_SCENARIOS.md](./RECOVERY_SCENARIOS.md) - 복구 시나리오
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

