# Task Scheduler Implementation Plan

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 2.0.2 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Purpose

This document bridges **design** to **implementation** by defining:
- Component responsibilities and boundaries
- Execution paths for all task types
- State transition rules
- Failure handling semantics

This is a planning document. No code is included.

---

## Authoritative References

| Document | Role |
|----------|------|
| API_CONTRACT.md | Canonical API behavior (cannot be overridden) |
| DESIGN_GUARDS.md | Locked decisions (DEC-004 ~ DEC-010) |
| DOMAIN_MODEL.md | Entity definitions |

---

## 1. Component Breakdown

### 1.1 QueueManager

**Responsibility**: Maintains the ordered queue of QUEUED tasks.

**Inputs**:
- New Task (from ScheduleTrigger, Manual API, or RetryController)
- Cancel request (task_id)
- Reorder request (task_id, new_position)

**Outputs**:
- Next task to dispatch (based on priority, position, created_at)
- Queue state queries (list, count, position)

**What It MUST NOT Do**:
- Execute tasks (Executor's responsibility)
- Create TaskRuns (Executor's responsibility)
- Manage retry logic (RetryController's responsibility)
- Interact with external APIs or webhooks

**Key Behaviors**:
```
Insertion:
  Task added → assign position → persist to SQLite → status = QUEUED

Ordering (INV-004):
  priority DESC, position ASC, created_at ASC

Cancellation:
  status = QUEUED → status = CANCELLED
  status = RUNNING → delegate to Executor

Direct API Reservation (DEC-004):
  reserve_next_slot() → blocks queue dispatch until released
```

---

### 1.2 Dispatcher

**Responsibility**: Pulls tasks from queue and hands them to Executor.

**Inputs**:
- Signal: "worker available"
- Signal: "next-slot reserved" (from Direct API)
- Queue state from QueueManager

**Outputs**:
- Task dispatched to Executor
- Dispatch event (for logging/monitoring)

**What It MUST NOT Do**:
- Modify task parameters (immutable after dispatch per INV-001)
- Execute the task itself
- Handle retries
- Manage concurrency limits (see OQ-001 - unresolved)

**Key Behaviors**:
```
Normal dispatch loop:
  1. Check if next-slot is reserved
     → YES: wait for reservation to complete
     → NO: continue
  2. Query QueueManager.get_next()
  3. If task exists:
     a. Transition task: QUEUED → RUNNING (internal DISPATCHED is transient)
     b. Hand to Executor
  4. Wait for Executor completion signal
  5. Loop

Next-slot reservation handling:
  1. Direct API calls reserve_next_slot()
  2. Dispatcher pauses queue dispatch
  3. Current task (if any) completes normally
  4. Direct execution runs
  5. Reservation released
  6. Queue dispatch resumes
```

---

### 1.3 Executor

**Responsibility**: Runs the actual task work and produces TaskRun.

**Inputs**:
- Task (with params, task_type)
- Execution context (model spec, resource handles)

**Outputs**:
- TaskRun (with status, artifacts, error, timing)
- Completion signal to Dispatcher

**What It MUST NOT Do**:
- Modify the Task entity (except status transition)
- Decide retry policy (RetryController's responsibility)
- Send webhooks directly (WebhookService's responsibility)
- Manage queue state

**Key Behaviors**:
```
Execution flow:
  1. Create TaskRun (started_at = now)
  2. Load task_type handler (story/research)
  3. Execute work
  4. On success:
     - TaskRun.status = COMPLETED
     - TaskRun.artifacts = [produced files]
  5. On failure:
     - TaskRun.status = FAILED
     - TaskRun.error = error message
  6. On skip (e.g., dedup):
     - TaskRun.status = SKIPPED
  7. Persist TaskRun (INV-002: immutable after creation)
  8. Signal completion to Dispatcher
  9. Notify RetryController (if FAILED)
  10. Trigger WebhookService
```

---

### 1.4 RetryController

**Responsibility**: Decides whether to create retry tasks and manages retry chain.

**Inputs**:
- Failed TaskRun
- Task's retry_policy (from TaskTemplate)
- Retry chain (via `retry_of` references)

**Outputs**:
- New Task (if auto-retry)
- "No more retries" signal (if max reached)

**What It MUST NOT Do**:
- Execute tasks
- Modify existing Tasks or TaskRuns
- Override template's retry_policy

**Key Behaviors (DEC-007)**:
```
On FAILED TaskRun:
  1. Count retry attempts in chain (traverse retry_of)
  2. If attempts < max_attempts (default: 3):
     a. Calculate backoff delay
     b. Create new Task with:
        - Same template_id, params
        - retry_of = original_task_id
        - scheduled_for = now + backoff
     c. Enqueue to QueueManager
  3. If attempts >= max_attempts:
     a. Mark as permanently failed
     b. No auto-retry
     c. Manual retry still allowed via API

Backoff calculation:
  delay = base_delay * (2 ^ attempt_number)
  Example: 10s, 20s, 40s
```

---

### 1.5 PersistenceAdapter

**Responsibility**: Abstracts SQLite storage for all task-related entities.

**Inputs**:
- CRUD operations for Task, TaskRun, TaskTemplate, Schedule, TaskGroup

**Outputs**:
- Persisted entities
- Query results

**What It MUST NOT Do**:
- Contain business logic
- Validate beyond schema constraints
- Manage transactions across multiple operations (caller's responsibility)

**Key Behaviors (DEC-002, DEC-008)**:
```
Storage:
  - SQLite with WAL mode
  - Connection pooling for async access
  - All state persisted immediately

Startup recovery:
  1. Load all QUEUED tasks → restore queue
  2. Find RUNNING tasks from previous session → mark as FAILED
  3. Validate queue order integrity

Schema enforcement:
  - Task.params immutable after RUNNING (app-level, not DB constraint)
  - TaskRun mostly immutable (limited mutable fields per INV-002)
```

---

### 1.6 ScheduleTrigger

**Responsibility**: Converts Schedule cron triggers into Tasks.

**Inputs**:
- Enabled Schedules (from PersistenceAdapter)
- Current time
- Timezone configuration

**Outputs**:
- New Tasks (enqueued via QueueManager)

**What It MUST NOT Do**:
- Execute tasks
- Modify Schedule during trigger
- Handle missed triggers beyond catchup policy

**Key Behaviors (DEC-003, DEC-010)**:
```
Integration with APScheduler:
  1. On startup, register all enabled Schedules with APScheduler
  2. APScheduler fires trigger at cron time
  3. Trigger handler:
     a. Load Schedule and associated TaskTemplate
     b. Create Task with merged params
     c. Enqueue via QueueManager
  4. Update Schedule.last_triggered_at

Timezone handling:
  - Each Schedule.timezone passed to APScheduler
  - Default: UTC
  - DST handled by APScheduler/pytz
```

---

### 1.7 WebhookService

**Responsibility**: Sends webhook notifications on task events.

**Inputs**:
- Task completion events
- Webhook configuration (URL, events to send)

**Outputs**:
- HTTP requests to configured endpoints
- Delivery status tracking

**What It MUST NOT Do**:
- Block task execution
- Guarantee exactly-once delivery

**Key Behaviors (DEC-009)**:
```
Delivery:
  1. On TaskRun terminal status (COMPLETED, FAILED, SKIPPED)
  2. Build payload (matches API response schema)
  3. POST to webhook_url
  4. On failure:
     a. Retry up to 3 times
     b. Exponential backoff (e.g., 5s, 15s, 45s)
  5. After 3 failures: mark as failed, stop retrying

Fire-and-forget pattern:
  - Non-blocking (async)
  - Does not affect task execution flow
```

---

### 1.8 DirectExecutionHandler

**Responsibility**: Handles Direct API requests with next-slot reservation.

**Inputs**:
- Direct API request (`/story/generate`, `/research/run`)

**Outputs**:
- Execution result (synchronous response)
- Reservation release signal

**What It MUST NOT Do**:
- Create Tasks
- Preempt running tasks
- Modify queue state directly

**Key Behaviors (DEC-004)**:
```
Execution flow:
  1. Call Dispatcher.reserve_next_slot()
  2. Wait for current task to complete (if any)
  3. Execute direct request
  4. Return response to caller
  5. Call Dispatcher.release_next_slot()
  6. Dispatcher resumes queue

No preemption guarantee:
  - Running task always completes
  - Direct request waits (with timeout)
  - Timeout behavior: TBD (fail fast vs extend wait)
```

---

## 2. Execution Paths

### 2.1 Path A: Scheduled Task

```
Schedule.cron fires
    ↓
ScheduleTrigger.handle_trigger()
    ↓
Load TaskTemplate, merge params
    ↓
QueueManager.enqueue(new Task)
    ↓
[Task status: QUEUED]
    ↓
Dispatcher sees available worker
    ↓
Dispatcher.dispatch(task)
    ↓
[Task status: RUNNING]
    ↓
Executor.execute(task)
    ↓
[TaskRun created]
    ↓
On completion: TaskRun.status = COMPLETED/FAILED/SKIPPED
    ↓
WebhookService.notify()
    ↓
If FAILED: RetryController.evaluate()
```

---

### 2.2 Path B: Manual Task

```
POST /api/tasks {template_id, priority}
    ↓
Validate template exists
    ↓
Create Task with params snapshot
    ↓
QueueManager.enqueue(task)
    ↓
[Task status: QUEUED]
    ↓
(Same as Path A from Dispatcher onward)
```

---

### 2.3 Path C: Direct API (Next-Slot Reservation)

```
POST /story/generate (or /research/run)
    ↓
DirectExecutionHandler receives request
    ↓
Dispatcher.reserve_next_slot()
    ↓
[Queue dispatch paused]
    ↓
Wait for current RUNNING task (if any)
    ↓
Current task completes normally
    ↓
Execute direct request (NOT a Task)
    ↓
Return response to caller
    ↓
Dispatcher.release_next_slot()
    ↓
[Queue dispatch resumed]
    ↓
Next QUEUED task dispatched
```

---

### 2.4 Path D: Retry → New Task Creation

```
TaskRun.status = FAILED
    ↓
Executor notifies RetryController
    ↓
RetryController.evaluate(task, taskrun)
    ↓
Count attempts in chain (retry_of traversal)
    ↓
attempts < 3?
    ├── YES: Create new Task
    │         - retry_of = original_task_id
    │         - scheduled_for = now + backoff
    │         - QueueManager.enqueue()
    │
    └── NO: Mark permanently failed
             - No auto-retry
             - Manual retry via POST /api/task-runs/{run_id}/retry
```

---

## 3. State Transitions

### 3.1 Task Lifecycle

```
                    ┌─────────────┐
                    │   QUEUED    │ ← Created by Schedule/Manual/Retry
                    └──────┬──────┘
                           │ dispatch
                    ┌──────▼──────┐
                    │   RUNNING   │ ← Executor working
                    └──────┬──────┘
                           │ complete (TaskRun determines outcome)
                    ┌──────▼──────┐
                    │  (terminal) │
                    └─────────────┘

Cancellation:
  QUEUED ──cancel──► CANCELLED
  RUNNING ──cancel──► (wait for completion, then no retry)
```

**External (API/Webhook) Statuses**:
| Status | Meaning |
|--------|---------|
| QUEUED | Waiting in queue |
| RUNNING | Currently executing |
| CANCELLED | Cancelled before completion |

**Internal-Only States** (not exposed via API):
- `PENDING`: Task awaiting group (if using TaskGroup)
- `DISPATCHED`: Brief transition between claim and execution start

---

### 3.2 TaskRun Lifecycle

```
                    ┌─────────────┐
                    │  (created)  │ ← Executor starts work
                    └──────┬──────┘
                           │ execution finishes
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ COMPLETED│ │  FAILED  │ │ SKIPPED  │
        └──────────┘ └──────────┘ └──────────┘
```

**External (API/Webhook) Statuses**:
| Status | Meaning |
|--------|---------|
| COMPLETED | Execution succeeded |
| FAILED | Execution encountered error |
| SKIPPED | Execution intentionally skipped (e.g., dedup) |

---

### 3.3 Mapping to API and Webhook

| Entity | Field | API Response | Webhook Payload |
|--------|-------|--------------|-----------------|
| Task | status | QUEUED/RUNNING/CANCELLED | Same |
| TaskRun | status | COMPLETED/FAILED/SKIPPED | Same |
| TaskRun | error | Error message (if FAILED) | Same |
| TaskRun | artifacts | List of file paths | Same |

Webhook events:
- `task.run.completed` → TaskRun.status = COMPLETED
- `task.run.failed` → TaskRun.status = FAILED
- `task.run.skipped` → TaskRun.status = SKIPPED

---

## 4. Failure Handling

### 4.1 Retry Flow (DEC-007)

**Automatic Retry (max 3 attempts)**:
```
Attempt 1: Task1 → TaskRun1 (FAILED)
                ↓
           RetryController creates Task2 (retry_of: Task1)
                ↓
Attempt 2: Task2 → TaskRun2 (FAILED)
                ↓
           RetryController creates Task3 (retry_of: Task2)
                ↓
Attempt 3: Task3 → TaskRun3 (FAILED)
                ↓
           RetryController: max attempts reached, no auto-retry
                ↓
           Task3 marked as permanently failed
```

**Backoff Strategy**:
- Base delay: configurable (e.g., 10 seconds)
- Formula: `delay = base * (2 ^ attempt_number)`
- Example: 10s → 20s → 40s

---

### 4.2 Manual Retry Semantics

```
POST /api/task-runs/{run_id}/retry
    ↓
Validate: run_id exists, status = FAILED
    ↓
Create new Task with:
  - template_id from original
  - params snapshot from original
  - retry_of = original_task_id
  - priority: same or specified
    ↓
Enqueue to QueueManager
    ↓
Return new task_id
```

Manual retry is always allowed, regardless of automatic retry count.

---

### 4.3 Crash/Restart Recovery (DEC-008)

**On Scheduler Startup**:
```
1. Load all Tasks from SQLite
2. For each Task:
   - QUEUED: Restore to queue (preserve order)
   - RUNNING: Mark as FAILED (orphaned)
     - Create TaskRun with status=FAILED, error="Scheduler crash recovery"
     - Trigger RetryController evaluation
3. Resume normal dispatch loop
```

**Orphaned Task Handling**:
- RUNNING tasks from previous session cannot be verified
- Conservative approach: mark as FAILED, let retry handle
- Webhook fires for recovery-failed tasks

---

## 5. Explicit Non-Goals

The following are **explicitly out of scope** for this implementation:

### 5.1 Distributed Workers

- All workers run on the same machine
- No network coordination protocol
- No distributed locking
- Reference: CON-001 (Single Machine Deployment)

### 5.2 Preemption

- Running tasks are NEVER interrupted
- Direct APIs wait, not preempt
- Cancel requests on RUNNING tasks wait for completion
- Reference: DEC-004 (Next-Slot Reservation)

### 5.3 UI Coupling

- No UI-specific endpoints
- No dashboard data aggregation
- No websocket push for status updates
- Reference: API_CONTRACT.md Section 9 (Non-Goals)

### 5.4 Complex Scheduling Patterns

- No task dependencies (DAG execution)
- No conditional execution (if-then-else)
- No cross-task data passing
- Simple cron + manual + retry only

### 5.5 Exactly-Once Semantics

- Webhooks are at-least-once, not exactly-once
- Duplicate deliveries possible
- Client-side idempotency required
- Reference: DEC-009

---

## 6. Resolved Questions

The following questions have been resolved and implemented.

### OQ-001 → DEC-011: Concurrency Limit Strategy

**Resolution**: Global single concurrency - maximum 1 task running at any time.

**Decision Reference**: See DESIGN_GUARDS.md DEC-011

**Implementation**:
- Dispatcher checks for any RUNNING task before dispatch
- If any task is RUNNING, new dispatch waits
- No type-based or resource-based partitioning in Phase 4

**Migration Path**:
- Phase 5+: Add per-type or resource-based limits when remote API parallelization needed
- Existing single-worker tests remain valid (single-worker is subset)

---

### OQ-002 → DEC-012: TaskGroup Sequential Failure Behavior

**Resolution**: Stop-on-failure - if any task in a sequential group fails, cancel remaining tasks.

**Decision Reference**: See DESIGN_GUARDS.md DEC-012

**Implementation**:
- Sequential group executes tasks in order
- If Task N fails (after retry exhaustion), cancel Task N+1, N+2, ...
- Cancelled tasks get status `CANCELLED` with reason "predecessor failed"
- Group status becomes `PARTIAL`

**Retry Interaction**:
- Failed task is retried per DEC-007 before group decides to stop
- Remaining tasks cancelled only after retry chain exhaustion

**Migration Path**:
- Phase 5+: Add `on_failure: stop | continue | skip` field when user requests flexibility
- Default value `stop` ensures backward compatibility

---

## 7. Component Dependencies

```
                    ┌────────────────┐
                    │ ScheduleTrigger│
                    └───────┬────────┘
                            │ creates Tasks
                            ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Manual API     │──►│  QueueManager   │◄──│ RetryController │
└─────────────────┘   └───────┬─────────┘   └────────▲────────┘
                              │                      │
                              ▼                      │
                    ┌─────────────────┐              │
                    │   Dispatcher    │◄─────────────┤
                    └───────┬─────────┘              │
                            │                        │
           ┌────────────────┼────────────────┐       │
           ▼                ▼                ▼       │
┌──────────────────┐ ┌──────────────┐ ┌──────────────┴───┐
│DirectExecHandler │ │   Executor   │─│  WebhookService  │
└──────────────────┘ └──────────────┘ └──────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │PersistenceAdapter│
                    └─────────────────┘
```

---

## 8. Implementation Order (Suggested)

| Phase | Components | Dependencies |
|-------|------------|--------------|
| 1 | PersistenceAdapter | None |
| 2 | QueueManager | PersistenceAdapter |
| 3 | Executor | PersistenceAdapter |
| 4 | Dispatcher | QueueManager, Executor |
| 5 | RetryController | QueueManager, Dispatcher |
| 6 | ScheduleTrigger | QueueManager, APScheduler |
| 7 | DirectExecutionHandler | Dispatcher, Executor |
| 8 | WebhookService | Existing webhook infra |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-18 | - | Initial implementation plan |

---

## Related Documents

- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [EXECUTION_FLOW.md](./EXECUTION_FLOW.md) - 실행 흐름 다이어그램
- [PERSISTENCE_SCHEMA.md](./PERSISTENCE_SCHEMA.md) - 영속성 스키마
- [API_CONTRACT.md](./API_CONTRACT.md) - API 계약
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

