# Job Scheduler Design Guards

> **Status:** DRAFT
> **Version:** 0.3.0
> **Last Updated:** 2026-01-18

---

## Overview

This document captures the **invariants, constraints, and critical decisions** that guard the Job Scheduler design. It serves as a contract for implementation and a reference for design reviews.

---

## Invariants (Must Never Be Violated)

### INV-001: Job Immutability After Dispatch

**Statement**: Once a Job enters `DISPATCHED` state, its `params` field MUST NOT change.

**Rationale**: Execution consistency requires stable parameters. If params could change mid-execution, workers would have inconsistent views of what they're running.

**Enforcement**:
```python
def update_job(job_id: str, **updates):
    job = load_job(job_id)
    if job.status in [JobStatus.DISPATCHED, JobStatus.RUNNING]:
        if "params" in updates:
            raise InvalidOperationError("Cannot modify params after dispatch")
```

---

### INV-002: JobRun Immutability

**Statement**: Once a JobRun is created, only `finished_at`, `status`, `exit_code`, `error`, and `artifacts` may be updated. All other fields are immutable.

**Rationale**: JobRun is an audit record. Historical accuracy requires immutability.

**Enforcement**:
```python
JOBRUN_MUTABLE_FIELDS = {"finished_at", "status", "exit_code", "error", "artifacts"}

def update_jobrun(run_id: str, **updates):
    invalid = set(updates.keys()) - JOBRUN_MUTABLE_FIELDS
    if invalid:
        raise InvalidOperationError(f"Cannot modify immutable fields: {invalid}")
```

---

### INV-003: Single Running Job Per Worker

**Statement**: A worker MUST NOT execute more than one Job simultaneously (unless explicitly configured for parallel execution).

**Rationale**: Prevents resource contention and simplifies state management.

**Enforcement**:
- Worker claims job with atomic operation
- Database constraint on `(worker_id, status=RUNNING)`
- Worker rejects new work if already running

---

### INV-004: Queue Order Consistency

**Statement**: Jobs MUST be dispatched in order of `(priority DESC, position ASC, created_at ASC)` unless explicitly bypassed.

**Rationale**: Predictable scheduling behavior is essential for user expectations.

**Enforcement**:
```sql
SELECT * FROM jobs
WHERE status = 'QUEUED'
ORDER BY priority DESC, position ASC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED
```

---

### INV-005: Schedule-Job Isolation

**Statement**: A Schedule's state (enabled, cron, params) MUST NOT affect already-created Jobs.

**Rationale**: Jobs are snapshots of intent at creation time. Changing a schedule should not retroactively affect jobs.

**Enforcement**:
- Jobs store `params` as snapshot, not reference
- Job.schedule_id is for audit trail only, not for parameter lookup

---

### INV-006: JobGroup Completion Atomicity

**Statement**: A JobGroup's terminal status MUST be determined only when ALL member Jobs reach terminal status.

**Rationale**: Prevents premature completion signals and ensures accurate aggregate status.

**Enforcement**:
```python
def compute_group_status(group: JobGroup) -> GroupStatus:
    job_statuses = [load_job(jid).status for jid in group.job_ids]
    if not all(is_terminal(s) for s in job_statuses):
        return GroupStatus.RUNNING
    # ... determine COMPLETED, PARTIAL, or CANCELLED
```

---

## Critical Design Decisions

### DEC-001: 1:1 Job-to-JobRun Relationship

**Decision**: Each Job produces exactly one JobRun. Retries create new Jobs.

**Alternatives Considered**:
1. 1:N with JobRun per attempt (rejected: complex state management)
2. No JobRun, all data in Job (rejected: audit trail loss)

**Rationale**: Simpler state machine, clearer audit trail, easier debugging.

**Implications**:
- Retry logic creates new Job with `retry_of` reference
- Max retries tracked via chain traversal, not counter

---

### DEC-002: SQLite for Job Storage

**Decision**: Use SQLite as the primary job storage backend.

**Alternatives Considered**:
1. PostgreSQL (rejected: overkill for single-machine workload)
2. Redis (rejected: persistence concerns, complexity)
3. File-based JSON (current) (rejected: no transactions, race conditions)

**Rationale**: ACID transactions, embedded (no server), sufficient for expected scale (~100 jobs/day).

**Implications**:
- Write-ahead logging (WAL) mode for concurrency
- Connection pooling required for async access
- Backup strategy needed

---

### DEC-003: APScheduler for Cron Scheduling

**Decision**: Use APScheduler library for cron expression handling and trigger management.

**Alternatives Considered**:
1. Custom cron parser (rejected: reinventing wheel)
2. Celery Beat (rejected: heavy dependency, requires Redis/RabbitMQ)
3. systemd timers (rejected: external to application)

**Rationale**: Lightweight, proven, supports cron expressions and timezone handling.

**Implications**:
- APScheduler job store separate from our Job entity
- Trigger creates our Job, APScheduler job is just the trigger

---

### DEC-004: Direct API Next-Slot Reservation

**Decision**: Direct APIs (`/story/generate`, `/research/run`) do not create Jobs. They reserve the next execution slot without preempting running jobs.

**Behavior**:
1. If no job is running → execute immediately
2. If a job is running → wait for it to finish, then execute
3. Queue resumes after direct execution completes

**Alternatives Considered**:
1. Direct APIs create high-priority Jobs (rejected: user expects synchronous response)
2. Preempt running job (rejected: wastes work, complex state recovery)
3. Fail fast if busy (rejected: poor user experience)

**Rationale**: Guarantees responsiveness without interrupting running work.

**Implications**:
- Scheduler exposes "reserve next slot" API
- No preemption logic needed
- Deterministic execution order: [current] → [direct] → [queue]

---

### DEC-005: Position-Based Ordering Within Priority

**Decision**: Jobs within the same priority level are ordered by explicit `position` field, not insertion time.

**Alternatives Considered**:
1. FIFO only (rejected: no reordering capability)
2. Floating-point positions (rejected: precision issues over time)
3. Linked list (rejected: complex updates)

**Rationale**: Enables explicit reordering via position swap. Integer positions can be re-normalized periodically.

**Implications**:
- Insert at position N shifts positions N+ by 1
- Batch position updates for large reorders
- Consider position gap strategy (insert at 10, 20, 30...)

---

### DEC-006: Unified Status Model

**Decision**: Use consistent status names across API responses, webhooks, and internal state.

**Job Status** (queue-level, external):
| Status | Meaning |
|--------|---------|
| QUEUED | Waiting in queue |
| RUNNING | Currently executing |
| CANCELLED | Cancelled before completion |

**JobRun Status** (execution result, external):
| Status | Meaning |
|--------|---------|
| COMPLETED | Execution finished successfully |
| FAILED | Execution encountered error |
| SKIPPED | Execution intentionally skipped |

**Rationale**: Single source of truth for status semantics. Webhooks use identical schema to API responses.

**Deprecated**:
- `succeeded` → use `COMPLETED`
- `error` → use `FAILED`
- `dispatched` → internal only, not exposed

---

### DEC-007: Automatic Retry Policy

**Decision**: Failed jobs are automatically retried up to 3 attempts. Further retries require manual invocation.

**Behavior**:
1. On failure, scheduler creates new Job with `retry_of` reference
2. Automatic retries: max 3 attempts per original job
3. After 3 failures: job marked as permanently failed
4. Manual retry always allowed via `POST /api/job-runs/{run_id}/retry`

**Rationale**: Balances automation with control. Prevents infinite retry loops while handling transient failures.

**Implications**:
- JobTemplate includes `retry_policy.max_attempts` (default: 3)
- Retry chain tracked via `retry_of` field
- Exponential backoff between attempts

---

### DEC-008: Queue Persistence Across Restarts

**Decision**: QUEUED jobs are persisted and resumed from storage on scheduler restart.

**Behavior**:
1. All job state stored in SQLite
2. On startup, scheduler loads all QUEUED jobs
3. RUNNING jobs from previous session marked as FAILED (crash recovery)
4. Queue order preserved

**Rationale**: Durability is expected. Users should not lose queued work due to restarts.

**Implications**:
- SQLite is the source of truth
- Startup recovery logic required
- Orphaned RUNNING jobs need cleanup

---

### DEC-009: Webhook Delivery Guarantees

**Decision**: Webhooks use at-least-once delivery with maximum 3 retries.

**Behavior**:
1. Webhook fired on job completion
2. On failure, retry up to 3 times with exponential backoff
3. After 3 failures, webhook marked as failed (no further retries)
4. Webhook payload matches API response schema

**Rationale**: Balances reliability with simplicity. Matches current implementation.

**Implications**:
- Clients must handle duplicate deliveries (idempotency)
- Webhook status tracked per job
- No exactly-once guarantees

---

### DEC-010: Schedule Timezone Handling

**Decision**: Each schedule has a timezone field with UTC as default.

**Behavior**:
1. Schedule.timezone defaults to "UTC"
2. Cron expression interpreted in specified timezone
3. Timezone changes apply to next trigger, not current

**Rationale**: Flexibility for global deployments. UTC default is safe and predictable.

**Implications**:
- APScheduler configured with timezone per trigger
- Timezone validation required (pytz/zoneinfo)
- DST transitions handled by APScheduler

---

### DEC-011: Concurrency Limit Strategy

**Decision**: Global single concurrency — maximum 1 job running at any time.

**Behavior**:
1. Dispatcher checks for any RUNNING job before dispatch
2. If any job is RUNNING, new dispatch waits
3. No type-based or resource-based partitioning in Phase 4

**Alternatives Considered**:
1. Per-type concurrency (deferred: adds complexity without immediate benefit)
2. Resource-based pools (deferred: over-engineering for current scale)

**Rationale**: Matches CON-002 (Ollama exclusivity). Simplest implementation with zero configuration risk.

**Migration Path**:
- Phase 5+: Add per-type or resource-based limits when remote API parallelization needed
- Existing single-worker tests remain valid (single-worker is subset)

**Reference**: See `CONCURRENCY_OPTIONS.md` for full decision analysis.

---

### DEC-012: JobGroup Sequential Failure Behavior

**Decision**: Stop-on-failure — if any job in a sequential group fails, cancel remaining jobs.

**Behavior**:
1. Sequential group executes jobs in order
2. If Job N fails (after retry exhaustion), cancel Job N+1, N+2, ...
3. Cancelled jobs get status `CANCELLED` with reason "predecessor failed"
4. Group status becomes `PARTIAL`

**Alternatives Considered**:
1. Continue-on-failure (deferred: may waste resources on doomed work)
2. Configurable policy (deferred: adds API complexity without demand signal)

**Rationale**: Safest default — prevents cascading failures. Users expect sequential to mean "dependent".

**Retry Interaction**:
- Failed job is retried per DEC-007 before group decides to stop
- Remaining jobs cancelled only after retry chain exhaustion

**Migration Path**:
- Phase 5+: Add `on_failure: stop | continue | skip` field when user requests flexibility
- Default value `stop` ensures backward compatibility

**Reference**: See `JOBGROUP_BEHAVIOR_OPTIONS.md` for full decision analysis.

---

## Open Questions (Do Not Implement Until Resolved)

*No open questions. All blocking questions have been resolved.*

---

## Resolved Questions (Promoted to Decisions)

The following questions have been resolved and documented as decisions:

| Former ID | Resolution | Decision |
|-----------|------------|----------|
| OQ-001 | Concurrency Limit Strategy | DEC-011: Global single concurrency |
| OQ-002 (orig) | Retry Policy | DEC-007: Automatic up to 3, then manual |
| OQ-002 (new) | JobGroup Failure Behavior | DEC-012: Stop-on-failure for sequential groups |
| OQ-003 | Queue Persistence | DEC-008: Resume from SQLite |
| OQ-004 | Direct API Conflict | DEC-004: Next-slot reservation |
| OQ-006 | Timezone Handling | DEC-010: Per-schedule with UTC default |
| OQ-007 | Webhook Guarantees | DEC-009: At-least-once, max 3 retries |

---

## Constraints

### CON-001: Single Machine Deployment

**Constraint**: The scheduler runs on a single machine. No distributed coordination required.

**Implications**:
- SQLite is sufficient
- No distributed locks needed
- Worker is same process or subprocess

---

### CON-002: Ollama Resource Exclusivity

**Constraint**: Ollama (local LLM) can only handle one request at a time effectively.

**Implications**:
- Default concurrency limit of 1 for jobs using Ollama
- Resource tagging for jobs (ollama vs remote API)
- Different concurrency limits per resource type

---

### CON-003: Graceful Shutdown

**Constraint**: On shutdown signal, scheduler must complete running jobs before terminating.

**Implications**:
- SIGTERM handler with grace period
- Queue pause on shutdown signal
- State persistence before exit

---

### CON-004: Backward Compatibility Period

**Constraint**: Legacy `/jobs/*` endpoints must remain functional during migration.

**Implications**:
- Coexistence layer required
- Version negotiation or prefix routing
- Deprecation warnings before removal

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQLite write contention under load | Medium | Medium | WAL mode, connection pooling |
| APScheduler missed triggers | Low | High | Catchup on restart, monitoring |
| Orphaned jobs on crash | Medium | Medium | Heartbeat timeout, auto-recovery |
| Queue starvation (high priority flood) | Low | Medium | Priority aging, fairness quotas |
| Webhook infinite retry loops | Low | Low | Max retry limit, circuit breaker |

---

## Acceptance Criteria Template

For each invariant and decision, implementation must demonstrate:

1. **Unit Test**: Validates the rule in isolation
2. **Integration Test**: Validates the rule in realistic scenario
3. **Error Case**: Shows proper rejection of violations
4. **Documentation**: API docs reflect the constraint

Example for INV-001:
```python
def test_cannot_modify_params_after_dispatch():
    job = create_job(template_id="test", params={"key": "value"})
    dispatch_job(job.job_id)

    with pytest.raises(InvalidOperationError, match="Cannot modify params"):
        update_job(job.job_id, params={"key": "new_value"})
```

---

## Review Checklist

Before implementation of any component:

- [ ] All relevant invariants identified and testable
- [ ] No open questions block this component
- [ ] Constraints are respected
- [ ] Risks are acknowledged and mitigated
- [ ] Backward compatibility considered

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-18 | - | Initial draft |
| 0.2.0 | 2026-01-18 | - | Aligned with API_CONTRACT.md: unified status model, promoted 5 OQs to decisions, updated DEC-004 to next-slot reservation |
| 0.3.0 | 2026-01-18 | - | Locked DEC-011 (concurrency) and DEC-012 (JobGroup failure); all open questions resolved |

