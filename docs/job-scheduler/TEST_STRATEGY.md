# Job Scheduler Test Strategy

> **Status:** DRAFT
> **Version:** 0.1.0
> **Phase:** 3-C (Test Strategy)
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
- Must not create duplicate retry jobs
- Must not duplicate FAILED markers

---

## 2. Invariant Test Matrix

### 2.1 INV-001: Job Immutability After Dispatch

**Statement**: Once a Job enters DISPATCHED/RUNNING state, its `params` field MUST NOT change.

**Where It Can Break**:
- API endpoint that modifies job params
- Bug in QueueManager.update_job()
- Direct SQLite manipulation

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-001-A | Reject params update on RUNNING job | Create job, set status=RUNNING | Call update_job(params={new}) | InvalidOperationError raised |
| INV-001-B | Allow params update on QUEUED job | Create job, status=QUEUED | Call update_job(params={new}) | Params updated successfully |
| INV-001-C | Priority update allowed on QUEUED | Create job, status=QUEUED | Call update_job(priority=10) | Priority updated |
| INV-001-D | Priority update rejected on RUNNING | Create job, status=RUNNING | Call update_job(priority=10) | InvalidOperationError raised |

---

### 2.2 INV-002: JobRun Immutability

**Statement**: Once a JobRun is created, only `finished_at`, `status`, `exit_code`, `error`, and `artifacts` may be updated.

**Where It Can Break**:
- Attempt to change job_id or params_snapshot
- Bug in update_jobrun()

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-002-A | Reject job_id modification | Create JobRun | Call update(job_id=other) | InvalidOperationError raised |
| INV-002-B | Reject params_snapshot modification | Create JobRun | Call update(params_snapshot={}) | InvalidOperationError raised |
| INV-002-C | Allow status update | Create JobRun | Call update(status=COMPLETED) | Status updated |
| INV-002-D | Allow error update | Create JobRun | Call update(error="msg") | Error updated |
| INV-002-E | Allow artifacts append | Create JobRun | Call update(artifacts=[...]) | Artifacts updated |

---

### 2.3 INV-003: Single Running Job Per Worker

**Statement**: A worker MUST NOT execute more than one Job simultaneously.

**Where It Can Break**:
- Race condition in dispatcher
- Missing atomic claim

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-003-A | Second dispatch rejected while running | Job1 RUNNING | Try dispatch Job2 | Job2 not dispatched (waits or rejects) |
| INV-003-B | Dispatch allowed after completion | Job1 completes | Dispatch Job2 | Job2 dispatched successfully |

**Note**: This test must remain valid regardless of OQ-001 resolution. Test the single-worker case; future multi-worker tests will extend, not replace.

---

### 2.4 INV-004: Queue Order Consistency

**Statement**: Jobs MUST be dispatched in order of `(priority DESC, position ASC, created_at ASC)`.

**Where It Can Break**:
- Incorrect ORDER BY clause
- Position assignment bug
- Tie-breaker failure

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-004-A | Higher priority first | Job1(priority=5), Job2(priority=10) | get_next() | Returns Job2 |
| INV-004-B | Lower position first (same priority) | Job1(pos=200), Job2(pos=100), same priority | get_next() | Returns Job2 |
| INV-004-C | Earlier created_at first (same priority, position) | Job1(created=t1), Job2(created=t2), t1 < t2 | get_next() | Returns Job1 |
| INV-004-D | Full ordering test | 5 jobs with mixed priority/position/created_at | get_all_ordered() | Exact expected order |
| INV-004-E | Deterministic (same input → same output) | Fixed set of jobs | Run get_next() N times | Same order every time |

---

### 2.5 INV-005: Schedule-Job Isolation

**Statement**: A Schedule's state MUST NOT affect already-created Jobs.

**Where It Can Break**:
- Job references schedule params dynamically
- Schedule update modifies existing jobs

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-005-A | Job params snapshot is independent | Create job from schedule | Update schedule params | Job.params unchanged |
| INV-005-B | Disable schedule doesn't cancel jobs | Create job, then disable schedule | Check job status | Job still QUEUED |

---

### 2.6 INV-006: JobGroup Completion Atomicity

**Statement**: A JobGroup's terminal status MUST be determined only when ALL member Jobs reach terminal status.

**Where It Can Break**:
- Premature status calculation
- Missing job in status check

**Minimal Tests**:

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| INV-006-A | Group RUNNING if any job RUNNING | Group with 3 jobs, 1 RUNNING | compute_group_status() | RUNNING |
| INV-006-B | Group terminal only when all terminal | 2 jobs COMPLETED, 1 QUEUED | compute_group_status() | RUNNING (not COMPLETED) |
| INV-006-C | Group PARTIAL if any FAILED | All jobs terminal, 1 FAILED | compute_group_status() | PARTIAL |

**Note**: Test must remain valid regardless of OQ-002 resolution. Tests cover status derivation, not failure behavior.

---

### 2.7 Persistence Invariants (from PERSISTENCE_SCHEMA.md)

#### 2.7.1 No RUNNING Without JobRun

**Statement**: A Job MUST NOT remain in RUNNING status without a corresponding JobRun record.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-001-A | Dispatch creates both atomically | QUEUED job | dispatch() | Job RUNNING AND JobRun exists |
| PERS-001-B | Transaction rollback on JobRun failure | Simulate JobRun INSERT failure | dispatch() | Job remains QUEUED |
| PERS-001-C | Recovery creates missing JobRun | Job RUNNING, no JobRun (corrupt) | recovery_on_startup() | FAILED JobRun created |

#### 2.7.2 No Orphan JobRuns

**Statement**: A JobRun MUST NOT exist without a parent Job.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-002-A | JobRun creation requires valid job_id | Attempt create with invalid job_id | create_jobrun() | Foreign key error |
| PERS-002-B | Cleanup removes orphans (defensive) | Manually insert orphan | cleanup_orphans() | Orphan removed |

#### 2.7.3 No Duplicate Execution

**Statement**: A Job MUST NOT be executed more than once.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-003-A | Concurrent dispatch claims atomically | Same job, two concurrent dispatch attempts | parallel dispatch() | Only one succeeds |
| PERS-003-B | RUNNING job cannot return to QUEUED | Job RUNNING | set_status(QUEUED) | Rejected or ignored |
| PERS-003-C | Retry creates NEW job | Job1 FAILED | create_retry() | Job2 created, Job1 unchanged |

#### 2.7.4 Queue Order Determinism

**Statement**: Given the same SQLite state, queue order MUST be identical.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-004-A | Order reproducible | Fixed set of QUEUED jobs | Query N times | Identical order each time |
| PERS-004-B | Order survives restart | Jobs in queue | Restart scheduler | Same order as before |

#### 2.7.5 Reservation Exclusivity

**Statement**: At most ONE Direct API reservation may be ACTIVE at any time.

| Test ID | Description | Setup | Action | Assertion |
|---------|-------------|-------|--------|-----------|
| PERS-005-A | First reservation succeeds | No active reservation | reserve_next_slot() | ACTIVE reservation created |
| PERS-005-B | Second reservation waits/rejects | ACTIVE reservation exists | reserve_next_slot() | Waits or returns error |
| PERS-005-C | Reservation released allows next | Release reservation | reserve_next_slot() | Succeeds |

---

## 3. State Transition Tests

### 3.1 Job State Transitions

```
Valid transitions:
  QUEUED → RUNNING (dispatch)
  QUEUED → CANCELLED (cancel request)
  RUNNING → (terminal via JobRun completion)
```

| Test ID | Description | From | To | Valid? |
|---------|-------------|------|-----|--------|
| ST-JOB-01 | Dispatch transitions to RUNNING | QUEUED | RUNNING | Yes |
| ST-JOB-02 | Cancel transitions to CANCELLED | QUEUED | CANCELLED | Yes |
| ST-JOB-03 | Cannot transition CANCELLED → QUEUED | CANCELLED | QUEUED | No (rejected) |
| ST-JOB-04 | Cannot transition RUNNING → QUEUED | RUNNING | QUEUED | No (rejected) |
| ST-JOB-05 | RUNNING job with terminal JobRun | RUNNING | (check JobRun) | Job.finished_at set |

### 3.2 JobRun State Transitions

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
| ST-EXT-01 | API returns only external Job statuses | GET /api/jobs/{id} | Status in {QUEUED, RUNNING, CANCELLED} |
| ST-EXT-02 | API returns only external JobRun statuses | GET /api/job-runs/{id} | Status in {COMPLETED, FAILED, SKIPPED} |
| ST-EXT-03 | Webhook uses same status values | Capture webhook payload | Status matches API |

---

## 4. Execution Path Scenario Tests

### 4.1 Normal Queue Execution

**Scenario**: Job created → queued → dispatched → executed → completed

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-NORM-01 | 1. Create job<br>2. Wait for dispatch<br>3. Execute successfully | Job: QUEUED → RUNNING<br>JobRun: COMPLETED<br>Webhook fired |
| EP-NORM-02 | 1. Create 3 jobs<br>2. Execute all | Execution order matches queue order |
| EP-NORM-03 | 1. Create job<br>2. Cancel before dispatch | Job: CANCELLED<br>No JobRun created |

### 4.2 Direct API Next-Slot Reservation (DEC-004)

**Scenario**: Direct API reserves slot, waits for running job, executes, queue resumes

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-DIRECT-01 | 1. Job1 RUNNING<br>2. Direct API called<br>3. Job1 completes<br>4. Direct executes<br>5. Job2 dispatched | Direct executes between Job1 and Job2 |
| EP-DIRECT-02 | 1. Queue empty<br>2. Direct API called | Direct executes immediately |
| EP-DIRECT-03 | 1. Direct API<br>2. Another Direct API | Second waits for first to complete |
| EP-DIRECT-04 | 1. Direct reservation<br>2. Job1 completes<br>3. Verify queue paused | Job2 not dispatched until reservation released |
| EP-DIRECT-05 | 1. Reservation released | Queue dispatch resumes immediately |

**Invariant Check** (per DEC-004):
```
Execution order: [Current RUNNING] → [Direct] → [Remaining Queue]
No preemption: Running job always completes first
```

### 4.3 Retry Semantics (DEC-007)

**Scenario**: Job fails, automatic retry up to 3, then manual required

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-RETRY-01 | 1. Job1 fails | Retry Job2 created automatically |
| EP-RETRY-02 | 1. Job1 fails<br>2. Job2 fails<br>3. Job3 fails | Retry Job4 created |
| EP-RETRY-03 | 1. Job1-4 all fail (3 retries exhausted) | No Job5 created automatically |
| EP-RETRY-04 | 1. Max retries reached<br>2. Manual retry API | New Job created successfully |
| EP-RETRY-05 | 1. Job fails<br>2. Retry job created | retry_of field links to original |
| EP-RETRY-06 | 1. Multiple failures | Backoff delay increases exponentially |

**Retry Chain Verification**:
```
Job1 (original) → Job2 (retry_of: Job1) → Job3 (retry_of: Job2) → Job4 (retry_of: Job3)
Count traversal: 3 retries after original
```

### 4.4 Schedule-Triggered Job Creation

**Scenario**: Schedule cron fires, job created

| Test ID | Steps | Assertions |
|---------|-------|------------|
| EP-SCHED-01 | 1. Create enabled schedule<br>2. Advance time to cron<br>3. Trigger fires | Job created with schedule_id reference |
| EP-SCHED-02 | 1. Disabled schedule<br>2. Advance time | No job created |
| EP-SCHED-03 | 1. Schedule with param_overrides | Job.params includes overrides |
| EP-SCHED-04 | 1. Trigger fires<br>2. Check last_triggered_at | Timestamp updated |

---

## 5. Crash/Restart Recovery Tests

### 5.1 Crash During RUNNING Job (from RECOVERY_SCENARIOS.md Scenario 1)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-RUN-01 | Job1 RUNNING, JobRun1 non-terminal | Kill process | recovery_on_startup() | JobRun1.status = FAILED |
| REC-RUN-02 | Job1 RUNNING, no JobRun | Kill process | recovery_on_startup() | FAILED JobRun created |
| REC-RUN-03 | Job1 RUNNING, JobRun1 COMPLETED | Kill process | recovery_on_startup() | Job1.finished_at set only |
| REC-RUN-04 | Job1 RUNNING recovered | After recovery | Check retry | Retry job created if eligible |
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
| REC-RETRY-01 | JobRun1 FAILED, no retry job | Kill before retry | recovery_on_startup() | Retry job created |
| REC-RETRY-02 | JobRun1 FAILED, retry job exists | After retry created | recovery_on_startup() | No duplicate retry |
| REC-RETRY-03 | Max retries reached, no retry | Already at max | recovery_on_startup() | No retry created |

### 5.4 Crash During JobRun Creation (from RECOVERY_SCENARIOS.md Scenario 4)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-TXN-01 | Uncommitted transaction | Kill mid-transaction | SQLite rollback | Job remains QUEUED |
| REC-TXN-02 | After rollback | Restart | Normal dispatch | Job dispatched again |

### 5.5 Multiple RUNNING Jobs Recovery (from RECOVERY_SCENARIOS.md Scenario 5)

| Test ID | Setup State | Simulated Crash | Recovery Action | Assertions |
|---------|-------------|-----------------|-----------------|------------|
| REC-MULTI-01 | Job1, Job2 both RUNNING | Kill process | recovery_on_startup() | Both marked FAILED |
| REC-MULTI-02 | Both recovered | After recovery | Both get retry jobs (if eligible) |
| REC-MULTI-03 | Queue had Job3, Job4, Job5 | After recovery | Queue order preserved |

### 5.6 Rapid Restart Idempotency (from RECOVERY_SCENARIOS.md Scenario 6)

| Test ID | Setup State | Actions | Assertions |
|---------|-------------|---------|------------|
| REC-IDEM-01 | Job1 RUNNING | Crash → recover → crash → recover | Same final state as single recovery |
| REC-IDEM-02 | Multiple FAILED jobs needing retry | Run recovery N times | Same number of retry jobs |
| REC-IDEM-03 | Reservation ACTIVE | Run recovery N times | Only one EXPIRED transition |

---

## 6. Webhook Contract Verification

### 6.1 Schema Parity with API

**Rule**: Webhook payload schema MUST match API response schema for statuses.

| Test ID | Description | Assertion |
|---------|-------------|-----------|
| WH-SCHEMA-01 | Job status in webhook matches API | Webhook status ∈ {QUEUED, RUNNING, CANCELLED} |
| WH-SCHEMA-02 | JobRun status in webhook matches API | Webhook status ∈ {COMPLETED, FAILED, SKIPPED} |
| WH-SCHEMA-03 | Webhook payload structure | Matches API_CONTRACT.md Section 8 |
| WH-SCHEMA-04 | All required fields present | run_id, job_id, status, timestamps |

### 6.2 Event Types

| Test ID | Event | Trigger | Payload Contains |
|---------|-------|---------|------------------|
| WH-EVENT-01 | job.run.completed | JobRun status = COMPLETED | status: COMPLETED |
| WH-EVENT-02 | job.run.failed | JobRun status = FAILED | status: FAILED, error |
| WH-EVENT-03 | job.run.skipped | JobRun status = SKIPPED | status: SKIPPED |

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
| WH-REC-01 | Crash-recovered job fires webhook | FAILED status webhook sent |
| WH-REC-02 | Retry job fires webhook on completion | New job's webhook sent |

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

| Category | Reason |
|----------|--------|
| Schedule trigger tests (EP-SCHED-*) | Requires APScheduler integration |
| Full webhook delivery tests (WH-DELIV-*) | Requires external endpoint |
| INV-006 (JobGroup) tests | Depends on OQ-002 resolution |

### 7.4 No Regressions Criteria

**When OQ-001 or OQ-002 decisions land**:

| Criteria | Enforcement |
|----------|-------------|
| Existing invariant tests | Must still pass |
| Existing scenario tests | Must still pass |
| New tests may be added | But not replace existing |
| Single-worker tests | Remain valid (subset of multi-worker) |

**Test Extension Pattern**:
```
OQ-001 resolved (e.g., per-type limit):
  - Add new tests: INV-003-C, INV-003-D for multi-worker
  - Keep INV-003-A, INV-003-B (still valid for single-worker case)

OQ-002 resolved (e.g., configurable):
  - Add new tests for on_failure options
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
  - Pre-populated jobs for ordering tests
  - Pre-populated RUNNING jobs for recovery tests
  - Pre-created reservations for exclusivity tests
```

### 8.2 Assertion Helpers

**Recommended Assertion Helpers**:
```
assert_job_status(job_id, expected_status)
assert_jobrun_status(run_id, expected_status)
assert_queue_order(expected_job_ids_in_order)
assert_reservation_state(expected_status)
assert_retry_chain_length(job_id, expected_length)
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
| Lost jobs | PERS-004-*, queue order tests |
| Stale reservations | REC-RES-* |
| Webhook inconsistency | WH-SCHEMA-* |

### 9.2 Known Gaps

| Gap | Reason | Future Action |
|-----|--------|---------------|
| Full APScheduler integration | Depends on Phase 4 | Add EP-SCHED-* when implemented |
| Multi-worker scenarios | OQ-001 unresolved | Extend INV-003-* when decided |
| JobGroup failure behavior | OQ-002 unresolved | Extend INV-006-* when decided |
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

