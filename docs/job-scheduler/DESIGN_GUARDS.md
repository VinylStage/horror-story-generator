# Job Scheduler Design Guards

> **Status:** DRAFT
> **Version:** 0.1.0
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

### DEC-004: Direct API Priority Interrupt

**Decision**: Direct APIs (`/story/generate`, `/research/run`) do not create Jobs. They execute immediately with highest priority.

**Alternatives Considered**:
1. Direct APIs create high-priority Jobs (rejected: user expects synchronous response)
2. Separate execution path with no scheduler awareness (rejected: resource conflicts)

**Rationale**: User expectation of immediate response. Scheduler awareness enables graceful resource sharing.

**Implications**:
- Scheduler must expose "pause queue" signal
- Direct execution must notify scheduler when complete
- Resource manager must handle both paths

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

## Open Questions (Do Not Implement Until Resolved)

### OQ-001: Concurrency Limit Strategy

**Question**: How should we limit concurrent job execution?

**Options**:
1. **Global limit**: Max N jobs running across all types
2. **Per-type limit**: Max N story jobs, M research jobs
3. **Resource-based**: Based on available GPU/memory
4. **Group-based**: Jobs in same group share concurrency budget

**Current Thinking**: Per-type limit seems most practical for this use case.

**Blocking**: Dispatcher implementation

---

### OQ-002: Failed Job Retry Policy

**Question**: How should retries be handled?

**Options**:
1. **Automatic retry**: Up to N retries with exponential backoff
2. **Manual retry**: User explicitly requests retry
3. **Configurable per-template**: Template defines retry policy

**Current Thinking**: Configurable per-template with default of manual.

**Blocking**: JobTemplate schema, Job creation logic

---

### OQ-003: Queue Persistence Across Restarts

**Question**: What happens to QUEUED jobs when the scheduler restarts?

**Options**:
1. **Resume all**: Continue where we left off
2. **Stale detection**: Jobs older than X hours are marked STALE
3. **Selective resume**: Only resume jobs from last N hours

**Current Thinking**: Resume all with STALE marking for jobs older than configurable threshold.

**Blocking**: Scheduler initialization logic

---

### OQ-004: Direct API Resource Conflict

**Question**: What if a direct API request comes when the shared resource (Ollama) is in use?

**Options**:
1. **Wait with timeout**: Direct API waits for resource
2. **Fail fast**: Return 503 if resource busy
3. **Preempt**: Kill running job, execute direct, restart job
4. **Graceful pause**: Wait for current job to finish, then execute

**Current Thinking**: Graceful pause (Option 4) aligns with stated requirements.

**Blocking**: Resource manager design, direct API implementation

---

### OQ-005: JobGroup Sequential Failure Behavior

**Question**: In a sequential JobGroup, what happens when one job fails?

**Options**:
1. **Stop immediately**: Don't execute remaining jobs
2. **Continue all**: Execute remaining regardless of failure
3. **Configurable**: `on_failure: stop | continue | skip`

**Current Thinking**: Configurable with default of "stop".

**Blocking**: JobGroup execution logic

---

### OQ-006: Schedule Timezone Handling

**Question**: How do we handle timezone for cron expressions?

**Options**:
1. **UTC only**: All crons interpreted as UTC
2. **Per-schedule timezone**: Each schedule has timezone field
3. **Server timezone**: Use server's local timezone

**Current Thinking**: Per-schedule timezone with default of UTC.

**Blocking**: Schedule schema, APScheduler configuration

---

### OQ-007: Webhook Delivery Guarantees

**Question**: What delivery guarantees do we provide for webhooks?

**Options**:
1. **Fire and forget**: Best effort, no retry
2. **At-least-once**: Retry with exponential backoff
3. **Exactly-once**: Idempotency keys and dedup

**Current Thinking**: At-least-once with 3 retries (aligns with current implementation).

**Blocking**: Webhook service refactoring

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

