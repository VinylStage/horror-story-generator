# Task Scheduler Design Guards

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 1.7.0 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Overview

This document captures the **invariants, constraints, and critical decisions** that guard the Task Scheduler design. It serves as a contract for implementation and a reference for design reviews.

### Implementation Status

| Design Guard | Status | Verified By |
|--------------|--------|-------------|
| INV-001 to INV-006 | Implemented | test_invariants.py |
| DEC-004 | Implemented | test_e2e.py::TestE2EDirectExecution |
| DEC-007 | Implemented | test_e2e.py::TestE2ERetryFlow |
| DEC-011 | Implemented | Single-worker constraint enforced |
| DEC-012 | Implemented | test_e2e.py::TestE2ETaskGroup |

---

## Invariants (Must Never Be Violated)

### INV-001: Task Immutability After Dispatch

**Statement**: Once a Task enters `RUNNING` state, its `params` field MUST NOT change.

**Rationale**: Execution consistency requires stable parameters. If params could change mid-execution, workers would have inconsistent views of what they're running.

**Enforcement**:
```python
def update_task(task_id: str, **updates):
    task = load_task(task_id)
    if task.status == TaskStatus.RUNNING:
        if "params" in updates:
            raise InvalidOperationError("Cannot modify params after dispatch")
```

---

### INV-002: TaskRun Immutability

**Statement**: Once a TaskRun is created, only `finished_at`, `status`, `exit_code`, `error`, and `artifacts` may be updated. All other fields are immutable.

**Rationale**: TaskRun is an audit record. Historical accuracy requires immutability.

**Enforcement**:
```python
TASKRUN_MUTABLE_FIELDS = {"finished_at", "status", "exit_code", "error", "artifacts"}

def update_taskrun(run_id: str, **updates):
    invalid = set(updates.keys()) - TASKRUN_MUTABLE_FIELDS
    if invalid:
        raise InvalidOperationError(f"Cannot modify immutable fields: {invalid}")
```

---

### INV-003: Single Running Task Per Worker

**Statement**: A worker MUST NOT execute more than one Task simultaneously (unless explicitly configured for parallel execution).

**Rationale**: Prevents resource contention and simplifies state management.

**Enforcement**:
- Worker claims task with atomic operation
- Database constraint on `(worker_id, status=RUNNING)`
- Worker rejects new work if already running

---

### INV-004: Queue Order Consistency

**Statement**: Tasks MUST be dispatched in order of `(priority DESC, position ASC, created_at ASC)` unless explicitly bypassed.

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

### INV-005: Schedule-Task Isolation

**Statement**: A Schedule's state (enabled, cron, params) MUST NOT affect already-created Tasks.

**Rationale**: Tasks are snapshots of intent at creation time. Changing a schedule should not retroactively affect tasks.

**Enforcement**:
- Tasks store `params` as snapshot, not reference
- Task.schedule_id is for audit trail only, not for parameter lookup

---

### INV-006: TaskGroup Completion Atomicity

**Statement**: A TaskGroup's terminal status MUST be determined only when ALL member Tasks reach terminal status.

**Rationale**: Prevents premature completion signals and ensures accurate aggregate status.

**Enforcement**:
```python
def compute_group_status(group: TaskGroup) -> GroupStatus:
    task_statuses = [load_task(jid).status for jid in group.task_ids]
    if not all(is_terminal(s) for s in task_statuses):
        return GroupStatus.RUNNING
    # ... determine COMPLETED, PARTIAL, or CANCELLED
```

---

## Critical Design Decisions

### DEC-001: 1:1 Task-to-TaskRun Relationship

**Decision**: Each Task produces exactly one TaskRun. Retries create new Tasks.

**Alternatives Considered**:
1. 1:N with TaskRun per attempt (rejected: complex state management)
2. No TaskRun, all data in Task (rejected: audit trail loss)

**Rationale**: Simpler state machine, clearer audit trail, easier debugging.

**Implications**:
- Retry logic creates new Task with `retry_of` reference
- Max retries tracked via chain traversal, not counter

---

### DEC-002: SQLite for Task Storage

**Decision**: Use SQLite as the primary task storage backend.

**Alternatives Considered**:
1. PostgreSQL (rejected: overkill for single-machine workload)
2. Redis (rejected: persistence concerns, complexity)
3. File-based JSON (current) (rejected: no transactions, race conditions)

**Rationale**: ACID transactions, embedded (no server), sufficient for expected scale (~100 tasks/day).

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
- APScheduler job store separate from our Task entity
- Trigger creates our Task, APScheduler job is just the trigger

---

### DEC-004: Direct API Next-Slot Reservation

**Decision**: Direct APIs (`/story/generate`, `/research/run`) do not create Tasks. They reserve the next execution slot without preempting running tasks.

**Behavior**:
1. If no task is running → execute immediately
2. If a task is running → wait for it to finish, then execute
3. Queue resumes after direct execution completes

**Alternatives Considered**:
1. Direct APIs create high-priority Tasks (rejected: user expects synchronous response)
2. Preempt running task (rejected: wastes work, complex state recovery)
3. Fail fast if busy (rejected: poor user experience)

**Rationale**: Guarantees responsiveness without interrupting running work.

**Implications**:
- Scheduler exposes "reserve next slot" API
- No preemption logic needed
- Deterministic execution order: [current] → [direct] → [queue]

---

### DEC-005: Position-Based Ordering Within Priority

**Decision**: Tasks within the same priority level are ordered by explicit `position` field, not insertion time.

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

**Task Status** (queue-level, external):
| Status | Meaning |
|--------|---------|
| QUEUED | Waiting in queue |
| RUNNING | Currently executing |
| CANCELLED | Cancelled before completion |

**TaskRun Status** (execution result, external):
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

**Decision**: Failed tasks are automatically retried up to 3 attempts. Further retries require manual invocation.

**Behavior**:
1. On failure, scheduler creates new Task with `retry_of` reference
2. Automatic retries: max 3 attempts per original task
3. After 3 failures: task marked as permanently failed
4. Manual retry always allowed via `POST /api/task-runs/{run_id}/retry`

**Rationale**: Balances automation with control. Prevents infinite retry loops while handling transient failures.

**Implications**:
- TaskTemplate includes `retry_policy.max_attempts` (default: 3)
- Retry chain tracked via `retry_of` field
- Exponential backoff between attempts

---

### DEC-008: Queue Persistence Across Restarts

**Decision**: QUEUED tasks are persisted and resumed from storage on scheduler restart.

**Behavior**:
1. All task state stored in SQLite
2. On startup, scheduler loads all QUEUED tasks
3. RUNNING tasks from previous session marked as FAILED (crash recovery)
4. Queue order preserved

**Rationale**: Durability is expected. Users should not lose queued tasks due to restarts.

**Implications**:
- SQLite is the source of truth
- Startup recovery logic required
- Orphaned RUNNING tasks need cleanup

---

### DEC-009: Webhook Delivery Guarantees

**Decision**: Webhooks use at-least-once delivery with maximum 3 retries.

**Behavior**:
1. Webhook fired on task completion
2. On failure, retry up to 3 times with exponential backoff
3. After 3 failures, webhook marked as failed (no further retries)
4. Webhook payload matches API response schema

**Rationale**: Balances reliability with simplicity. Matches current implementation.

**Implications**:
- Clients must handle duplicate deliveries (idempotency)
- Webhook status tracked per task
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

**Decision**: Global single concurrency — maximum 1 task running at any time.

**Behavior**:
1. Dispatcher checks for any RUNNING task before dispatch
2. If any task is RUNNING, new dispatch waits
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

### DEC-012: TaskGroup Sequential Failure Behavior

**Decision**: Stop-on-failure — if any task in a sequential group fails, cancel remaining tasks.

**Behavior**:
1. Sequential group executes tasks in order
2. If Task N fails (after retry exhaustion), cancel Task N+1, N+2, ...
3. Cancelled tasks get status `CANCELLED` with reason "predecessor failed"
4. Group status becomes `PARTIAL`

**Alternatives Considered**:
1. Continue-on-failure (deferred: may waste resources on doomed work)
2. Configurable policy (deferred: adds API complexity without demand signal)

**Rationale**: Safest default — prevents cascading failures. Users expect sequential to mean "dependent".

**Retry Interaction**:
- Failed task is retried per DEC-007 before group decides to stop
- Remaining tasks cancelled only after retry chain exhaustion

**Migration Path**:
- Phase 5+: Add `on_failure: stop | continue | skip` field when user requests flexibility
- Default value `stop` ensures backward compatibility

**Reference**: See `TASKGROUP_BEHAVIOR_OPTIONS.md` for full decision analysis.

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
| OQ-002 (new) | TaskGroup Failure Behavior | DEC-012: Stop-on-failure for sequential groups |
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
- Default concurrency limit of 1 for tasks using Ollama
- Resource tagging for tasks (ollama vs remote API)
- Different concurrency limits per resource type

---

### CON-003: Graceful Shutdown

**Constraint**: On shutdown signal, scheduler must complete running tasks before terminating.

**Implications**:
- SIGTERM handler with grace period
- Queue pause on shutdown signal
- State persistence before exit

---

### CON-004: Legacy Endpoint Removal (v2.0.0)

**Status**: Resolved. Legacy `/jobs/*` endpoints have been fully removed in v2.0.0.

**Implications**:
- `POST /tasks` is the sole interface for asynchronous task creation
- No backward compatibility layer needed
- Clients must use the new Task API

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQLite write contention under load | Medium | Medium | WAL mode, connection pooling |
| APScheduler missed triggers | Low | High | Catchup on restart, monitoring |
| Orphaned tasks on crash | Medium | Medium | Heartbeat timeout, auto-recovery |
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
    task = create_task(template_id="test", params={"key": "value"})
    dispatch_task(task.task_id)

    with pytest.raises(InvalidOperationError, match="Cannot modify params"):
        update_task(task.task_id, params={"key": "new_value"})
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
| 0.3.0 | 2026-01-18 | - | Locked DEC-011 (concurrency) and DEC-012 (TaskGroup failure); all open questions resolved |

---

## Related Documents

- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [PERSISTENCE_SCHEMA.md](./PERSISTENCE_SCHEMA.md) - 영속성 스키마
- [API_CONTRACT.md](./API_CONTRACT.md) - API 계약
- [TEST_STRATEGY.md](./TEST_STRATEGY.md) - 테스트 전략
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

