# Task Scheduler Test Strategy

> **Status:** FINAL (Phase 6-A Validated)
> **Document Version:** 1.0.0
> **Application Version:** 2.0.3 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Purpose

This document defines an **invariant-driven test strategy** that makes future implementation safe.
All tests are designed to:

- Verify deterministic ordering
- Confirm correct state transitions
- Validate crash-safe recovery
- Guarantee Direct API next-slot reservation behavior
- Enforce retry semantics (max 3)
- Ensure webhook parity with API statuses

Tests are written to remain valid regardless of OQ-001/OQ-002 resolutions.

---

## Authoritative References

| Document | Test Focus |
|----------|------------|
| DESIGN_GUARDS.md | INV-001 ~ INV-006, DEC-004 ~ DEC-010 |
| PERSISTENCE_SCHEMA.md | Atomicity rules, storage invariants |
| RECOVERY_SCENARIOS.md | Crash recovery test cases |
| EXECUTION_FLOW.md | Scenario test definitions |
| API_CONTRACT.md | External status semantics |

---

## 1. Test Scope & Principles

### 1.1 Test Categories

| Category | Scope | Purpose |
|----------|-------|---------|
| **Unit Tests** | Single component in isolation | Verify component logic |
| **Integration Tests** | Multiple components with real SQLite | Verify component interaction |
| **Scenario Tests** | Full execution paths | Verify end-to-end behavior |
| **Recovery Tests** | Simulated crash + restart | Verify crash-safe recovery |

### 1.2 Determinism Requirements

All tests MUST be deterministic:

| Requirement | Enforcement |
|-------------|-------------|
| No random values | Use fixed seeds or deterministic generators |
| No wall-clock time | Use mocked clock (see below) |
| No external dependencies | Mock all external services |
| Ordered assertions | Queue order tests must assert exact order |

### 1.3 Time Control Strategy

**Mocked Clock Pattern**:
```
All time-dependent code must accept a Clock interface:
  - now() → current timestamp
  - sleep(duration) → advance time

Test clock:
  - Starts at fixed epoch (e.g., 2026-01-01T00:00:00Z)
  - Advances only when explicitly ticked
  - Enables deterministic timeout, backoff, expiration tests
```

**Why Required**:
- Retry backoff tests need predictable delays
- Reservation expiration needs controllable time
- Cron trigger tests need time manipulation

### 1.4 Idempotency Expectations

**Recovery Idempotency Rule**:
```
For any recovery test:
  1. Run recovery logic once
  2. Assert expected state
  3. Run recovery logic again (same input)
  4. Assert state unchanged (idempotent)
```

**Why Required**:
- Rapid restart scenario (crash → recover → crash → recover)
- Must not create duplicate retry tasks
- Must not duplicate FAILED markers

---

## 2. Invariant Test Matrix

### 2.1 INV-001: Task Immutability After Dispatch

**Statement**: Once a Task enters DISPATCHED/RUNNING state, its `params` field MUST NOT change.

**Where It Can Break**:
- API endpoint that modifies task params
- Bug in QueueManager.update_task()
- Direct SQLite manipulation

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-001-A | Reject params update on RUNNING task | Create task, set status=RUNNING | Call update_task(params={new}) | InvalidOperationError raised |
| INV-001-B | Allow params update on QUEUED task | Create task, status=QUEUED | Call update_task(params={new}) | Params updated successfully |
| INV-001-C | Priority update allowed on QUEUED | Create task, status=QUEUED | Call update_task(priority=10) | Priority updated |
| INV-001-D | Priority update rejected on RUNNING | Create task, status=RUNNING | Call update_task(priority=10) | InvalidOperationError raised |

---

### 2.2 INV-002: TaskRun Immutability

**Statement**: Once a TaskRun is created, only `finished_at`, `status`, `exit_code`, `error`, and `artifacts` may be updated.

**Where It Can Break**:
- Attempt to change task_id or params_snapshot
- Bug in update_taskrun()

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-002-A | Reject task_id modification | Create TaskRun | Call update(task_id=other) | InvalidOperationError raised |
| INV-002-B | Reject params_snapshot modification | Create TaskRun | Call update(params_snapshot={}) | InvalidOperationError raised |
| INV-002-C | Allow status update | Create TaskRun | Call update(status=COMPLETED) | Status updated |
| INV-002-D | Allow error update | Create TaskRun | Call update(error="msg") | Error updated |
| INV-002-E | Allow artifacts append | Create TaskRun | Call update(artifacts=[...]) | Artifacts updated |

---

### 2.3 INV-003: Single Running Task Per Worker

**Statement**: A worker MUST NOT execute more than one Task simultaneously.

**Where It Can Break**:
- Race condition in dispatcher
- Missing atomic claim

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-003-A | Second dispatch rejected while running | Task1 RUNNING | Try dispatch Task2 | Task2 not dispatched (waits or rejects) |
| INV-003-B | Dispatch allowed after completion | Task1 completes | Dispatch Task2 | Task2 dispatched successfully |

**Note**: This test must remain valid regardless of OQ-001 resolution. Test the single-worker case; future multi-worker tests will extend, not replace.

---

### 2.4 INV-004: Queue Order Consistency

**Statement**: Tasks MUST be dispatched in order of `(priority DESC, position ASC, created_at ASC)`.

**Where It Can Break**:
- Incorrect ORDER BY clause
- Position assignment bug
- Tie-breaker failure

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-004-A | Higher priority first | Task1(priority=5), Task2(priority=10) | get_next() | Returns Task2 |
| INV-004-B | Lower position first (same priority) | Task1(pos=200), Task2(pos=100), same priority | get_next() | Returns Task2 |
| INV-004-C | Earlier created_at first (same priority, position) | Task1(created=t1), Task2(created=t2), t1 < t2 | get_next() | Returns Task1 |
| INV-004-D | Full ordering test | 5 tasks with mixed priority/position/created_at | get_all_ordered() | Exact expected order |
| INV-004-E | Deterministic (same input → same output) | Fixed set of tasks | Run get_next() N times | Same order every time |

---

### 2.5 INV-005: Schedule-Task Isolation

**Statement**: A Schedule's state MUST NOT affect already-created Tasks.

**Where It Can Break**:
- Task references schedule params dynamically
- Schedule update modifies existing tasks

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-005-A | Task params snapshot is independent | Create task from schedule | Update schedule params | Task.params unchanged |
| INV-005-B | Disable schedule doesn't cancel tasks | Create task, then disable schedule | Check task status | Task still QUEUED |

---

### 2.6 INV-006: TaskGroup Completion Atomicity

**Statement**: A TaskGroup's terminal status MUST be determined only when ALL member Tasks reach terminal status.

**Where It Can Break**:
- Premature status calculation
- Missing task in status check

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-006-A | Group RUNNING if any task RUNNING | Group with 3 tasks, 1 RUNNING | compute_group_status() | RUNNING |
| INV-006-B | Group terminal only when all terminal | 2 tasks COMPLETED, 1 QUEUED | compute_group_status() | RUNNING (not COMPLETED) |
| INV-006-C | Group PARTIAL if any FAILED | All tasks terminal, 1 FAILED | compute_group_status() | PARTIAL |

**Note**: Test must remain valid regardless of OQ-002 resolution. Tests cover status derivation, not failure behavior.

---

### 2.7 Persistence Invariants (from PERSISTENCE_SCHEMA.md)

#### 2.7.1 No RUNNING Without TaskRun

**Statement**: A Task MUST NOT remain in RUNNING status without a corresponding TaskRun record.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-001-A | Dispatch creates both atomically | QUEUED task | dispatch() | Task RUNNING AND TaskRun exists |
| PERS-001-B | Transaction rollback on TaskRun failure | Simulate TaskRun INSERT failure | dispatch() | Task remains QUEUED |
| PERS-001-C | Recovery creates missing TaskRun | Task RUNNING, no TaskRun (corrupt) | recovery_on_startup() | FAILED TaskRun created |

#### 2.7.2 No Orphan TaskRuns

**Statement**: A TaskRun MUST NOT exist without a parent Task.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-002-A | TaskRun creation requires valid task_id | Attempt create with invalid task_id | create_taskrun() | Foreign key error |
| PERS-002-B | Cleanup removes orphans (defensive) | Manually insert orphan | cleanup_orphans() | Orphan removed |

#### 2.7.3 No Duplicate Execution

**Statement**: A Task MUST NOT be executed more than once.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-003-A | Concurrent dispatch claims atomically | Same task, two concurrent dispatch attempts | parallel dispatch() | Only one succeeds |
| PERS-003-B | RUNNING task cannot return to QUEUED | Task RUNNING | set_status(QUEUED) | Rejected or ignored |
| PERS-003-C | Retry creates NEW task | Task1 FAILED | create_retry() | Task2 created, Task1 unchanged |

#### 2.7.4 Queue Order Determinism

**Statement**: Given the same SQLite state, queue order MUST be identical.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-004-A | Order reproducible | Fixed set of QUEUED tasks | Query N times | Identical order each time |
| PERS-004-B | Order survives restart | Tasks in queue | Restart scheduler | Same order as before |

#### 2.7.5 Reservation Exclusivity

**Statement**: At most ONE Direct API reservation may be ACTIVE at any time.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-005-A | First reservation succeeds | No active reservation | reserve_next_slot() | ACTIVE reservation created |
| PERS-005-B | Second reservation waits/rejects | ACTIVE reservation exists | reserve_next_slot() | Waits or returns error |
| PERS-005-C | Reservation released allows next | Release reservation | reserve_next_slot() | Succeeds |

---

## 3. State Transition Tests

### 3.1 Task State Transitions

```
Valid transitions:
  QUEUED → RUNNING (dispatch)
  QUEUED → CANCELLED (cancel request)
  RUNNING → (terminal via TaskRun completion)
```

| Test ID | Description | From | To | Valid? |
|---------|-------------|------|-----|--------|
| ST-TASK-01 | Dispatch transitions to RUNNING | QUEUED | RUNNING | Yes |
| ST-TASK-02 | Cancel transitions to CANCELLED | QUEUED | CANCELLED | Yes |
| ST-TASK-03 | Cannot transition CANCELLED → QUEUED | CANCELLED | QUEUED | No (rejected) |
| ST-TASK-04 | Cannot transition RUNNING → QUEUED | RUNNING | QUEUED | No (rejected) |
| ST-TASK-05 | RUNNING task with terminal TaskRun | RUNNING | (check TaskRun) | Task.finished_at set |

### 3.2 TaskRun State Transitions

```
Valid terminal states:
  COMPLETED (success)
  FAILED (error)
  SKIPPED (intentionally skipped)
```

| Test ID | Description | Terminal Status | Valid? |
|---------|-------------|-----------------|--------|
| ST-RUN-01 | Successful execution | COMPLETED | Yes |
| ST-RUN-02 | Failed execution | FAILED | Yes |
| ST-RUN-03 | Skipped execution (dedup) | SKIPPED | Yes |
| ST-RUN-04 | Cannot change after COMPLETED | COMPLETED → FAILED | No (rejected) |
| ST-RUN-05 | Cannot change after FAILED | FAILED → COMPLETED | No (rejected) |

### 3.3 External vs Internal States

**Rule**: Internal states (if any) are never exposed via API or webhook.

| Test ID | Description | Action | Assertion |
|---------|-------------|--------|-----------|
| ST-EXT-01 | API returns only external Task statuses | GET /api/tasks/{id} | Status in {QUEUED, RUNNING, CANCELLED} |
| ST-EXT-02 | API returns only external TaskRun statuses | GET /api/task-runs/{id} | Status in {COMPLETED, FAILED, SKIPPED} |
| ST-EXT-03 | Webhook uses same status values | Capture webhook payload | Status matches API |

---

## 4. Execution Path Scenario Tests

### 4.1 Normal Queue Execution

**Scenario**: Task created → queued → dispatched → executed → completed

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-NORM-01 | 1. Create task<br>2. Wait for dispatch<br>3. Execute successfully | Task: QUEUED → RUNNING<br>TaskRun: COMPLETED<br>Webhook fired |
| EP-NORM-02 | 1. Create 3 tasks<br>2. Execute all | Execution order matches queue order |
| EP-NORM-03 | 1. Create task<br>2. Cancel before dispatch | Task: CANCELLED<br>No TaskRun created |

### 4.2 Direct API Next-Slot Reservation (DEC-004)

**Scenario**: Direct API reserves slot, waits for running task, executes, queue resumes

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-DIRECT-01 | 1. Task1 RUNNING<br>2. Direct API called<br>3. Task1 completes<br>4. Direct executes<br>5. Task2 dispatched | Direct executes between Task1 and Task2 |
| EP-DIRECT-02 | 1. Queue empty<br>2. Direct API called | Direct executes immediately |
| EP-DIRECT-03 | 1. Direct API<br>2. Another Direct API | Second waits for first to complete |
| EP-DIRECT-04 | 1. Direct reservation<br>2. Task1 completes<br>3. Verify queue paused | Task2 not dispatched until reservation released |
| EP-DIRECT-05 | 1. Reservation released | Queue dispatch resumes immediately |

**Invariant Check** (per DEC-004):
```
Execution order: [Current RUNNING] → [Direct] → [Remaining Queue]
No preemption: Running task always completes first
```

### 4.3 Retry Semantics (DEC-007)

**Scenario**: Task fails, automatic retry up to 3, then manual required

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-RETRY-01 | 1. Task1 fails | Retry Task2 created automatically |
| EP-RETRY-02 | 1. Task1 fails<br>2. Task2 fails<br>3. Task3 fails | Retry Task4 created |
| EP-RETRY-03 | 1. Task1-4 all fail (3 retries exhausted) | No Task5 created automatically |
| EP-RETRY-04 | 1. Max retries reached<br>2. Manual retry API | New Task created successfully |
| EP-RETRY-05 | 1. Task fails<br>2. Retry task created | retry_of field links to original |
| EP-RETRY-06 | 1. Multiple failures | Backoff delay increases exponentially |

**Retry Chain Verification**:
```
Task1 (original) → Task2 (retry_of: Task1) → Task3 (retry_of: Task2) → Task4 (retry_of: Task3)
Count traversal: 3 retries after original
```

### 4.4 Schedule-Triggered Task Creation

**Scenario**: Schedule cron fires, task created

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-SCHED-01 | 1. Create enabled schedule<br>2. Advance time to cron<br>3. Trigger fires | Task created with schedule_id reference |
| EP-SCHED-02 | 1. Disabled schedule<br>2. Advance time | No task created |
| EP-SCHED-03 | 1. Schedule with param_overrides | Task.params includes overrides |
| EP-SCHED-04 | 1. Trigger fires<br>2. Check last_triggered_at | Timestamp updated |

---

## 5. Crash/Restart Recovery Tests

### 5.1 Crash During RUNNING Task (from RECOVERY_SCENARIOS.md Scenario 1)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-RUN-01 | Task1 RUNNING, TaskRun1 non-terminal | Kill process | recovery_on_startup() | TaskRun1.status = FAILED |
| REC-RUN-02 | Task1 RUNNING, no TaskRun | Kill process | recovery_on_startup() | FAILED TaskRun created |
| REC-RUN-03 | Task1 RUNNING, TaskRun1 COMPLETED | Kill process | recovery_on_startup() | Task1.finished_at set only |
| REC-RUN-04 | Task1 RUNNING recovered | After recovery | Check retry | Retry task created if eligible |
| REC-RUN-05 | Same as REC-RUN-01 | Run recovery twice | Idempotency | No duplicate FAILED markers |

### 5.2 Crash During Direct API Reservation (from RECOVERY_SCENARIOS.md Scenario 2)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-RES-01 | Reservation ACTIVE, expired | Kill process | recovery_on_startup() | Reservation = EXPIRED |
| REC-RES-02 | Reservation ACTIVE, not expired | Kill process | recovery_on_startup() | Force expire (stale) |
| REC-RES-03 | After reservation expired | Check queue | Queue dispatch resumed |
| REC-RES-04 | Multiple restarts | Run recovery twice | Only one EXPIRED, no duplicates |

### 5.3 Crash During Retry Creation (from RECOVERY_SCENARIOS.md Scenario 3)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-RETRY-01 | TaskRun1 FAILED, no retry task | Kill before retry | recovery_on_startup() | Retry task created |
| REC-RETRY-02 | TaskRun1 FAILED, retry task exists | After retry created | recovery_on_startup() | No duplicate retry |
| REC-RETRY-03 | Max retries reached, no retry | Already at max | recovery_on_startup() | No retry created |

### 5.4 Crash During TaskRun Creation (from RECOVERY_SCENARIOS.md Scenario 4)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-TXN-01 | Uncommitted transaction | Kill mid-transaction | SQLite rollback | Task remains QUEUED |
| REC-TXN-02 | After rollback | Restart | Normal dispatch | Task dispatched again |

### 5.5 Multiple RUNNING Tasks Recovery (from RECOVERY_SCENARIOS.md Scenario 5)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-MULTI-01 | Task1, Task2 both RUNNING | Kill process | recovery_on_startup() | Both marked FAILED |
| REC-MULTI-02 | Both recovered | After recovery | Both get retry tasks (if eligible) |
| REC-MULTI-03 | Queue had Task3, Task4, Task5 | After recovery | Queue order preserved |

### 5.6 Rapid Restart Idempotency (from RECOVERY_SCENARIOS.md Scenario 6)

| Test ID | Setup State | Actions | Assertions |
|---------|-------------|---------|------------|
| REC-IDEM-01 | Task1 RUNNING | Crash → recover → crash → recover | Same final state as single recovery |
| REC-IDEM-02 | Multiple FAILED tasks needing retry | Run recovery N times | Same number of retry tasks |
| REC-IDEM-03 | Reservation ACTIVE | Run recovery N times | Only one EXPIRED transition |

---

## 6. Webhook Contract Verification

### 6.1 Schema Parity with API

**Rule**: Webhook payload schema MUST match API response schema for statuses.

| Test ID | Description | Assertion |
|---------|-------------|-----------|
| WH-SCHEMA-01 | Task status in webhook matches API | Webhook status ∈ {QUEUED, RUNNING, CANCELLED} |
| WH-SCHEMA-02 | TaskRun status in webhook matches API | Webhook status ∈ {COMPLETED, FAILED, SKIPPED} |
| WH-SCHEMA-03 | Webhook payload structure | Matches API_CONTRACT.md Section 8 |
| WH-SCHEMA-04 | All required fields present | run_id, task_id, status, timestamps |

### 6.2 Event Types

| Test ID | Event | Trigger | Payload Contains |
|---------|-------|---------|------------------|
| WH-EVENT-01 | task.run.completed | TaskRun status = COMPLETED | status: COMPLETED |
| WH-EVENT-02 | task.run.failed | TaskRun status = FAILED | status: FAILED, error |
| WH-EVENT-03 | task.run.skipped | TaskRun status = SKIPPED | status: SKIPPED |

### 6.3 Delivery Semantics (DEC-009)

| Test ID | Description | Assertion |
|---------|-------------|-----------|
| WH-DELIV-01 | Webhook fires on completion | HTTP request sent |
| WH-DELIV-02 | Retry on failure (up to 3) | After 1st failure, 2nd attempt made |
| WH-DELIV-03 | Max retries respected | After 3 failures, no more attempts |
| WH-DELIV-04 | Idempotent handling supported | Duplicate webhooks don't cause errors (client test) |

### 6.4 Recovery Webhook Tests

| Test ID | Description | Assertion |
|---------|-------------|-----------|
| WH-REC-01 | Crash-recovered task fires webhook | FAILED status webhook sent |
| WH-REC-02 | Retry task fires webhook on completion | New task's webhook sent |

---

## 7. Acceptance Criteria

### 7.1 Phase 3 Implementation Correctness

**Definition**: Phase 3 implementation is correct when:

| Criteria | Test Categories | Required Status |
|----------|-----------------|-----------------|
| All invariants hold | INV-*, PERS-* tests | 100% pass |
| State transitions valid | ST-* tests | 100% pass |
| Execution paths work | EP-* tests | 100% pass |
| Recovery is safe | REC-* tests | 100% pass |
| Webhooks are consistent | WH-* tests | 100% pass |

### 7.2 Merge Requirements

**Before merging to develop**:

| Category | Requirement |
|----------|-------------|
| Invariant tests | All INV-*, PERS-* tests pass |
| State transition tests | All ST-* tests pass |
| Core scenario tests | EP-NORM-*, EP-DIRECT-*, EP-RETRY-* pass |
| Critical recovery tests | REC-RUN-*, REC-RES-*, REC-IDEM-* pass |
| Webhook schema tests | WH-SCHEMA-*, WH-EVENT-* pass |

### 7.3 Optional for Later Phases

| Category | Reason | Status |
|----------|--------|--------|
| Schedule trigger tests (EP-SCHED-*) | Requires APScheduler integration | Pending |
| Full webhook delivery tests (WH-DELIV-*) | Requires external endpoint | Pending |
| INV-006 (TaskGroup) tests | OQ-002 resolved as DEC-012 | **COMPLETE** |

### 7.4 No Regressions Criteria

**OQ-001 and OQ-002 have been resolved**:

| Decision | Resolution | Test Status |
|----------|------------|-------------|
| OQ-001 → DEC-011 | Global single concurrency | Implemented, tested |
| OQ-002 → DEC-012 | Stop-on-failure for sequential groups | Implemented, tested |

| Criteria | Enforcement |
|----------|-------------|
| Existing invariant tests | Must still pass |
| Existing scenario tests | Must still pass |
| New tests may be added | But not replace existing |
| Single-worker tests | Remain valid (subset of multi-worker) |

**Future Test Extension Pattern**:
```
DEC-011 future changes (e.g., per-type limit):
  - Add new tests: INV-003-C, INV-003-D for multi-worker
  - Keep INV-003-A, INV-003-B (still valid for single-worker case)

DEC-012 future changes (e.g., configurable on_failure):
  - Add new tests for on_failure options (continue, skip)
  - Keep INV-006-* (still valid for status derivation)
```

---

## 8. Test Implementation Notes

### 8.1 Test Fixtures

**Recommended Fixture Pattern**:
```
Base fixtures:
  - Empty database
  - Mocked clock at fixed time
  - Clean queue state

Per-test fixtures:
  - Pre-populated tasks for ordering tests
  - Pre-populated RUNNING tasks for recovery tests
  - Pre-created reservations for exclusivity tests
```

### 8.2 Assertion Helpers

**Recommended Assertion Helpers**:
```
assert_task_status(task_id, expected_status)
assert_taskrun_status(run_id, expected_status)
assert_queue_order(expected_task_ids_in_order)
assert_reservation_state(expected_status)
assert_retry_chain_length(task_id, expected_length)
assert_webhook_fired(event_type, payload_contains)
```

### 8.3 Concurrency Test Strategy

For tests requiring concurrent access (PERS-003-A):
```
1. Use threading or async to simulate concurrent dispatch
2. Assert only one dispatch succeeds
3. Assert no data corruption
```

**Note**: Concurrency tests must NOT assume specific OQ-001 resolution.

---

## 9. Risk & Gap Analysis

### 9.1 Covered Risks

| Risk | Mitigation (Tests) |
|------|-------------------|
| Queue corruption on crash | REC-* tests |
| Duplicate execution | PERS-003-*, INV-003-* |
| Lost tasks | PERS-004-*, queue order tests |
| Stale reservations | REC-RES-* |
| Webhook inconsistency | WH-SCHEMA-* |

### 9.2 Known Gaps

| Gap | Reason | Future Action |
|-----|--------|---------------|
| Full APScheduler integration | Depends on Phase 4 | Add EP-SCHED-* when implemented |
| Multi-worker scenarios | OQ-001 unresolved | Extend INV-003-* when decided |
| TaskGroup failure behavior | OQ-002 unresolved | Extend INV-006-* when decided |
| Performance/load tests | Out of scope for Phase 3 | Separate performance test plan |

### 9.3 Assumptions

| Assumption | Dependency |
|------------|------------|
| SQLite ACID guarantees | SQLite correctly configured |
| Mocked clock works | Time abstraction implemented |
| Test isolation | Each test uses fresh database |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-18 | - | Initial test strategy |

---

## Related Documents

- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [E2E_TEST_PLAN.md](./E2E_TEST_PLAN.md) - E2E 테스트 계획
- [E2E_TEST_REPORT.md](./E2E_TEST_REPORT.md) - E2E 테스트 결과
- [RECOVERY_SCENARIOS.md](./RECOVERY_SCENARIOS.md) - 복구 시나리오
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

