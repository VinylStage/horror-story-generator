# Job Scheduler Persistence Schema Design

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 1.5.0 (managed by release-please)
> **Last Updated:** 2026-01-18

---

## Purpose

This document defines the persistence layer design that guarantees:

- **Deterministic execution order** — Queue ordering is never ambiguous
- **Crash-safe recovery** — No silent data loss on unexpected termination
- **Resume-on-restart** — QUEUED jobs survive scheduler restarts
- **Atomicity** — State transitions are all-or-nothing

This design makes queue corruption or ambiguity **practically impossible**.

---

## Authoritative References

| Document | Constraint |
|----------|------------|
| DESIGN_GUARDS.md DEC-002 | SQLite for job storage |
| DESIGN_GUARDS.md DEC-008 | Queue persistence across restarts |
| DESIGN_GUARDS.md INV-001 | Job immutability after dispatch |
| DESIGN_GUARDS.md INV-002 | JobRun immutability |
| IMPLEMENTATION_PLAN.md | Component responsibilities |

---

## 1. Storage Roles

### 1.1 Two-Tier Storage Model

The persistence layer uses two storage tiers with distinct responsibilities:

| Tier | Technology | Purpose |
|------|------------|---------|
| **Durable Store** | SQLite | Source of truth for all job state |
| **Volatile Cache** | In-memory (dict/redis-like) | Ephemeral operational state |

---

### 1.2 Durable Store (SQLite)

**Why It Exists**:
- Single source of truth for job state
- Survives process crashes and restarts
- Provides ACID transactions for state transitions
- Enables queue order reconstruction

**What MUST Be Stored**:
| Data | Reason |
|------|--------|
| Job entities | Primary work units, must survive restart |
| JobRun entities | Audit trail, immutable history |
| JobTemplate entities | Reusable job definitions |
| Schedule entities | Cron trigger configurations |
| Queue ordering metadata | Priority, position, created_at |
| Retry chain references | `retry_of` linkage |
| Direct reservation flag | Survives crash during reservation |

**Persistence Guarantees**:
- Write-ahead logging (WAL) mode enabled
- All state transitions are transactional
- No in-memory-only job state

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
| Job status | Would be lost on crash |
| Queue position | Would corrupt ordering on restart |
| JobRun data | Audit trail must be durable |
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

### 2.1 Job

**Primary Key**: `job_id` (UUID, immutable)

**Required Fields**:
| Field | Type | Mutability | Purpose |
|-------|------|------------|---------|
| `job_id` | UUID | Immutable | Unique identifier |
| `template_id` | UUID (nullable) | Immutable | Source template reference |
| `schedule_id` | UUID (nullable) | Immutable | Triggering schedule (if any) |
| `group_id` | UUID (nullable) | Immutable | JobGroup membership |
| `job_type` | String | Immutable | "story" / "research" |
| `params` | JSON | Immutable after RUNNING | Execution parameters |
| `status` | Enum | Mutable | QUEUED / RUNNING / CANCELLED |
| `priority` | Integer | Mutable (while QUEUED) | Dispatch priority |
| `position` | Integer | Mutable (while QUEUED) | Queue position |
| `retry_of` | UUID (nullable) | Immutable | Previous job in retry chain |
| `created_at` | Timestamp | Immutable | Creation time |
| `queued_at` | Timestamp | Immutable | When added to queue |
| `started_at` | Timestamp (nullable) | Write-once | Execution start |
| `finished_at` | Timestamp (nullable) | Write-once | Execution end |

**Lifecycle Ownership**: QueueManager (creation, ordering), Dispatcher (status transitions)

**Persistence Timing**:
| Event | Write Action |
|-------|--------------|
| Job created | INSERT with status=QUEUED |
| Job dispatched | UPDATE status=RUNNING, started_at=now |
| Job completed | UPDATE finished_at=now (status unchanged; outcome in JobRun) |
| Job cancelled | UPDATE status=CANCELLED |
| Position changed | UPDATE position (within transaction) |

---

### 2.2 JobRun

**Primary Key**: `run_id` (UUID, immutable)

**Required Fields**:
| Field | Type | Mutability | Purpose |
|-------|------|------------|---------|
| `run_id` | UUID | Immutable | Unique identifier |
| `job_id` | UUID | Immutable | Parent job reference |
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

Retry information is stored **within the Job entity** via `retry_of` field.

**Chain Structure**:
```
Job1 (original)      → retry_of: NULL
  └── Job2 (retry)   → retry_of: Job1.job_id
        └── Job3     → retry_of: Job2.job_id
              └── Job4 → retry_of: Job3.job_id (max reached)
```

**Retry Count Calculation**:
```
To count attempts for JobN:
  1. Start with attempt = 0
  2. Follow retry_of chain to root
  3. Count chain length
  4. Return count
```

**No Separate Retry Table**: All retry metadata is derived from Job entities and their `retry_of` relationships. This ensures:
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
| `priority` | DESC | Higher priority jobs first |
| `position` | ASC | Explicit ordering within priority |
| `created_at` | ASC | Tiebreaker for equal priority+position |

**Ordering Query Pattern**:
```
SELECT * FROM jobs
WHERE status = 'QUEUED'
ORDER BY priority DESC, position ASC, created_at ASC
LIMIT 1
```

---

### 3.2 Position Assignment Strategy

**On Job Insert**:
```
1. Find max position among QUEUED jobs with same priority
2. Assign position = max + GAP_SIZE (e.g., 100)
3. If no jobs exist at priority, position = GAP_SIZE
```

**Gap Strategy Benefits**:
- Insertions between jobs don't require shifting
- Reordering is a simple position swap
- Periodic normalization (optional) to prevent overflow

**Position Normalization** (periodic maintenance):
```
1. Load all QUEUED jobs ordered by (priority, position, created_at)
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
   a. Do not dispatch any QUEUED job
   b. Wait for reservation to be RELEASED or EXPIRED
3. If not found:
   a. Proceed with normal dispatch
```

**Fairness Preservation**:
- Reservation does NOT modify queue order
- Queue remains intact during reservation
- First QUEUED job after release is the same as before reservation

---

### 3.4 Persistence Failure During Transition

**Scenario**: SQLite write fails mid-transition

**Mitigation Strategy**:
| Transition | Failure Behavior |
|------------|------------------|
| Job INSERT fails | No job created; caller gets error |
| QUEUED → RUNNING fails | Job remains QUEUED; retry dispatch |
| JobRun INSERT fails | Job is RUNNING but no record; crash recovery handles |
| Status UPDATE fails | Retry update; if unrecoverable, manual intervention |

**Transaction Boundaries**:
```
Dispatch Transaction:
  BEGIN
    UPDATE job SET status='RUNNING', started_at=now WHERE job_id=?
    INSERT INTO job_runs (run_id, job_id, started_at, ...) VALUES (...)
  COMMIT

If transaction fails → job stays QUEUED, no JobRun exists.
```

---

## 4. Restart & Recovery Scenarios

### 4.1 Clean Shutdown Restart

**Trigger**: Scheduler receives SIGTERM, completes gracefully

**Pre-Shutdown Actions**:
1. Stop accepting new jobs
2. Wait for RUNNING jobs to complete (grace period)
3. Persist final state
4. Exit

**On Restart**:
| State | Action |
|-------|--------|
| QUEUED jobs | Load into queue, preserve order |
| No RUNNING jobs | Normal (clean shutdown completed them) |
| Direct reservation RELEASED | Normal |

**Result**: Queue resumes exactly where it left off.

---

### 4.2 Crash During RUNNING Job

**Trigger**: Process killed while Job.status = RUNNING

**On Restart**:
```
1. Query: SELECT * FROM jobs WHERE status = 'RUNNING'
2. For each RUNNING job:
   a. Check if JobRun exists
      → YES with terminal status: Job was finishing, update Job
      → YES without terminal status: Execution was interrupted
      → NO: Crash before JobRun creation
   b. Mark JobRun as FAILED (error = "Scheduler crash recovery")
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

**Trigger**: Process killed after JobRun.status = FAILED but before new retry Job created

**On Restart**:
```
1. Query: SELECT jr.*, j.retry_of FROM job_runs jr
          JOIN jobs j ON jr.job_id = j.job_id
          WHERE jr.status = 'FAILED'
          AND j.finished_at IS NOT NULL
2. For each FAILED JobRun:
   a. Count retry chain length
   b. Check if retry Job already exists (retry_of = this job)
      → YES: Retry was created, no action
      → NO and attempts < max: Create retry Job now
      → NO and attempts >= max: Mark permanently failed
```

**Idempotency Guarantee**:
- Retry creation is idempotent (check before create)
- If retry exists, skip creation
- If retry doesn't exist and eligible, create it

---

### 4.5 Recovery Decision Matrix

| Pre-Crash State | JobRun Exists? | JobRun Terminal? | Recovery Action |
|-----------------|----------------|------------------|-----------------|
| QUEUED | N/A | N/A | Resume in queue (no action) |
| RUNNING | No | N/A | Create FAILED JobRun, retry |
| RUNNING | Yes | No | Update to FAILED, retry |
| RUNNING | Yes | Yes | Update Job.finished_at only |
| Direct Reservation ACTIVE | N/A | N/A | Expire if stale, resume queue |

---

## 5. Atomicity & Consistency Rules

### 5.1 Invariant: No RUNNING Without JobRun

**Rule**: A Job MUST NOT remain in RUNNING status without a corresponding JobRun record.

**Enforcement**:
```
Dispatch Transaction (atomic):
  1. UPDATE job SET status = 'RUNNING'
  2. INSERT job_run

If step 2 fails → transaction rolls back → job stays QUEUED.
```

**Recovery Check**:
```
On startup:
  SELECT j.* FROM jobs j
  LEFT JOIN job_runs jr ON j.job_id = jr.job_id
  WHERE j.status = 'RUNNING' AND jr.run_id IS NULL

If any rows returned → create FAILED JobRun for each.
```

---

### 5.2 Invariant: No Orphan JobRuns

**Rule**: A JobRun MUST NOT exist without a parent Job.

**Enforcement**:
- Foreign key constraint: `job_runs.job_id REFERENCES jobs.job_id`
- JobRun creation always follows Job existence check

**Cleanup** (defensive, should never trigger):
```
DELETE FROM job_runs
WHERE job_id NOT IN (SELECT job_id FROM jobs)
```

---

### 5.3 Invariant: No Duplicate Execution

**Rule**: A Job MUST NOT be executed more than once.

**Enforcement**:
```
1. Job.status transition: QUEUED → RUNNING is one-way
2. RUNNING job cannot return to QUEUED
3. Dispatch uses atomic claim:

   UPDATE jobs SET status = 'RUNNING'
   WHERE job_id = ? AND status = 'QUEUED'
   RETURNING *

   If 0 rows affected → job was already dispatched (race condition).
```

**Crash Recovery Exception**:
- Crashed RUNNING jobs → FAILED (not re-queued)
- Retry creates NEW Job (different job_id)
- Original job is never re-executed

---

### 5.4 Invariant: Queue Order Determinism

**Rule**: Given the same SQLite state, queue order MUST be identical.

**Enforcement**:
- Order depends only on persisted fields: priority, position, created_at
- No random or time-based tiebreakers beyond created_at
- Position gaps don't affect relative order

**Verification Query**:
```
SELECT job_id, priority, position, created_at
FROM jobs
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
| Global limit (N workers) | Add `worker_id` to jobs, track active count |
| Per-type limit | Add `job_type` index, count by type |
| Resource-based | Add `resource_tags` column to jobs |

**Placeholder**:
- `jobs.worker_id` column (nullable) reserved for future use
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

### 6.3 JobGroup Concurrency (DEFERRED)

**Current State**: JobGroup execution semantics not fully designed.

**Schema Placeholder**:
- `jobs.group_id` exists
- No `job_groups` table defined yet
- OQ-002 (failure behavior) unresolved

**Future Addition** (when needed):
```
job_groups:
  group_id
  mode (parallel/sequential)
  on_failure (stop/continue/skip)
  status (derived from member jobs)
```

---

## 7. Consistency Checklist

Before any implementation, verify:

- [ ] All Job state transitions are transactional
- [ ] JobRun is created atomically with RUNNING transition
- [ ] No in-memory-only job state exists
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

