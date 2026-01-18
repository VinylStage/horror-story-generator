# Job Scheduler Implementation Plan

> **Status:** DRAFT
> **Version:** 0.1.0
> **Phase:** 2 (Implementation Planning)
> **Last Updated:** 2026-01-18

---

## Purpose

This document bridges **design** to **implementation** by defining:
- Component responsibilities and boundaries
- Execution paths for all job types
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

**Responsibility**: Maintains the ordered queue of QUEUED jobs.

**Inputs**:
- New Job (from ScheduleTrigger, Manual API, or RetryController)
- Cancel request (job_id)
- Reorder request (job_id, new_position)

**Outputs**:
- Next job to dispatch (based on priority, position, created_at)
- Queue state queries (list, count, position)

**What It MUST NOT Do**:
- Execute jobs (Executor's responsibility)
- Create JobRuns (Executor's responsibility)
- Manage retry logic (RetryController's responsibility)
- Interact with external APIs or webhooks

**Key Behaviors**:
```
Insertion:
  Job added → assign position → persist to SQLite → status = QUEUED

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

**Responsibility**: Pulls jobs from queue and hands them to Executor.

**Inputs**:
- Signal: "worker available"
- Signal: "next-slot reserved" (from Direct API)
- Queue state from QueueManager

**Outputs**:
- Job dispatched to Executor
- Dispatch event (for logging/monitoring)

**What It MUST NOT Do**:
- Modify job parameters (immutable after dispatch per INV-001)
- Execute the job itself
- Handle retries
- Manage concurrency limits (see OQ-001 - unresolved)

**Key Behaviors**:
```
Normal dispatch loop:
  1. Check if next-slot is reserved
     → YES: wait for reservation to complete
     → NO: continue
  2. Query QueueManager.get_next()
  3. If job exists:
     a. Transition job: QUEUED → RUNNING (internal DISPATCHED is transient)
     b. Hand to Executor
  4. Wait for Executor completion signal
  5. Loop

Next-slot reservation handling:
  1. Direct API calls reserve_next_slot()
  2. Dispatcher pauses queue dispatch
  3. Current job (if any) completes normally
  4. Direct execution runs
  5. Reservation released
  6. Queue dispatch resumes
```

---

### 1.3 Executor

**Responsibility**: Runs the actual job work and produces JobRun.

**Inputs**:
- Job (with params, job_type)
- Execution context (model spec, resource handles)

**Outputs**:
- JobRun (with status, artifacts, error, timing)
- Completion signal to Dispatcher

**What It MUST NOT Do**:
- Modify the Job entity (except status transition)
- Decide retry policy (RetryController's responsibility)
- Send webhooks directly (WebhookService's responsibility)
- Manage queue state

**Key Behaviors**:
```
Execution flow:
  1. Create JobRun (started_at = now)
  2. Load job_type handler (story/research)
  3. Execute work
  4. On success:
     - JobRun.status = COMPLETED
     - JobRun.artifacts = [produced files]
  5. On failure:
     - JobRun.status = FAILED
     - JobRun.error = error message
  6. On skip (e.g., dedup):
     - JobRun.status = SKIPPED
  7. Persist JobRun (INV-002: immutable after creation)
  8. Signal completion to Dispatcher
  9. Notify RetryController (if FAILED)
  10. Trigger WebhookService
```

---

### 1.4 RetryController

**Responsibility**: Decides whether to create retry jobs and manages retry chain.

**Inputs**:
- Failed JobRun
- Job's retry_policy (from JobTemplate)
- Retry chain (via `retry_of` references)

**Outputs**:
- New Job (if auto-retry)
- "No more retries" signal (if max reached)

**What It MUST NOT Do**:
- Execute jobs
- Modify existing Jobs or JobRuns
- Override template's retry_policy

**Key Behaviors (DEC-007)**:
```
On FAILED JobRun:
  1. Count retry attempts in chain (traverse retry_of)
  2. If attempts < max_attempts (default: 3):
     a. Calculate backoff delay
     b. Create new Job with:
        - Same template_id, params
        - retry_of = original_job_id
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

**Responsibility**: Abstracts SQLite storage for all job-related entities.

**Inputs**:
- CRUD operations for Job, JobRun, JobTemplate, Schedule, JobGroup

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
  1. Load all QUEUED jobs → restore queue
  2. Find RUNNING jobs from previous session → mark as FAILED
  3. Validate queue order integrity

Schema enforcement:
  - Job.params immutable after RUNNING (app-level, not DB constraint)
  - JobRun mostly immutable (limited mutable fields per INV-002)
```

---

### 1.6 ScheduleTrigger

**Responsibility**: Converts Schedule cron triggers into Jobs.

**Inputs**:
- Enabled Schedules (from PersistenceAdapter)
- Current time
- Timezone configuration

**Outputs**:
- New Jobs (enqueued via QueueManager)

**What It MUST NOT Do**:
- Execute jobs
- Modify Schedule during trigger
- Handle missed triggers beyond catchup policy

**Key Behaviors (DEC-003, DEC-010)**:
```
Integration with APScheduler:
  1. On startup, register all enabled Schedules with APScheduler
  2. APScheduler fires trigger at cron time
  3. Trigger handler:
     a. Load Schedule and associated JobTemplate
     b. Create Job with merged params
     c. Enqueue via QueueManager
  4. Update Schedule.last_triggered_at

Timezone handling:
  - Each Schedule.timezone passed to APScheduler
  - Default: UTC
  - DST handled by APScheduler/pytz
```

---

### 1.7 WebhookService

**Responsibility**: Sends webhook notifications on job events.

**Inputs**:
- Job completion events
- Webhook configuration (URL, events to send)

**Outputs**:
- HTTP requests to configured endpoints
- Delivery status tracking

**What It MUST NOT Do**:
- Block job execution
- Guarantee exactly-once delivery

**Key Behaviors (DEC-009)**:
```
Delivery:
  1. On JobRun terminal status (COMPLETED, FAILED, SKIPPED)
  2. Build payload (matches API response schema)
  3. POST to webhook_url
  4. On failure:
     a. Retry up to 3 times
     b. Exponential backoff (e.g., 5s, 15s, 45s)
  5. After 3 failures: mark as failed, stop retrying

Fire-and-forget pattern:
  - Non-blocking (async)
  - Does not affect job execution flow
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
- Create Jobs
- Preempt running jobs
- Modify queue state directly

**Key Behaviors (DEC-004)**:
```
Execution flow:
  1. Call Dispatcher.reserve_next_slot()
  2. Wait for current job to complete (if any)
  3. Execute direct request
  4. Return response to caller
  5. Call Dispatcher.release_next_slot()
  6. Dispatcher resumes queue

No preemption guarantee:
  - Running job always completes
  - Direct request waits (with timeout)
  - Timeout behavior: TBD (fail fast vs extend wait)
```

---

## 2. Execution Paths

### 2.1 Path A: Scheduled Job

```
Schedule.cron fires
    ↓
ScheduleTrigger.handle_trigger()
    ↓
Load JobTemplate, merge params
    ↓
QueueManager.enqueue(new Job)
    ↓
[Job status: QUEUED]
    ↓
Dispatcher sees available worker
    ↓
Dispatcher.dispatch(job)
    ↓
[Job status: RUNNING]
    ↓
Executor.execute(job)
    ↓
[JobRun created]
    ↓
On completion: JobRun.status = COMPLETED/FAILED/SKIPPED
    ↓
WebhookService.notify()
    ↓
If FAILED: RetryController.evaluate()
```

---

### 2.2 Path B: Manual Job

```
POST /api/jobs {template_id, priority}
    ↓
Validate template exists
    ↓
Create Job with params snapshot
    ↓
QueueManager.enqueue(job)
    ↓
[Job status: QUEUED]
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
Wait for current RUNNING job (if any)
    ↓
Current job completes normally
    ↓
Execute direct request (NOT a Job)
    ↓
Return response to caller
    ↓
Dispatcher.release_next_slot()
    ↓
[Queue dispatch resumed]
    ↓
Next QUEUED job dispatched
```

---

### 2.4 Path D: Retry → New Job Creation

```
JobRun.status = FAILED
    ↓
Executor notifies RetryController
    ↓
RetryController.evaluate(job, jobrun)
    ↓
Count attempts in chain (retry_of traversal)
    ↓
attempts < 3?
    ├── YES: Create new Job
    │         - retry_of = original_job_id
    │         - scheduled_for = now + backoff
    │         - QueueManager.enqueue()
    │
    └── NO: Mark permanently failed
             - No auto-retry
             - Manual retry via POST /api/job-runs/{run_id}/retry
```

---

## 3. State Transitions

### 3.1 Job Lifecycle

```
                    ┌─────────────┐
                    │   QUEUED    │ ← Created by Schedule/Manual/Retry
                    └──────┬──────┘
                           │ dispatch
                    ┌──────▼──────┐
                    │   RUNNING   │ ← Executor working
                    └──────┬──────┘
                           │ complete (JobRun determines outcome)
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
- `PENDING`: Job awaiting group (if using JobGroup)
- `DISPATCHED`: Brief transition between claim and execution start

---

### 3.2 JobRun Lifecycle

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
| Job | status | QUEUED/RUNNING/CANCELLED | Same |
| JobRun | status | COMPLETED/FAILED/SKIPPED | Same |
| JobRun | error | Error message (if FAILED) | Same |
| JobRun | artifacts | List of file paths | Same |

Webhook events:
- `job.run.completed` → JobRun.status = COMPLETED
- `job.run.failed` → JobRun.status = FAILED
- `job.run.skipped` → JobRun.status = SKIPPED

---

## 4. Failure Handling

### 4.1 Retry Flow (DEC-007)

**Automatic Retry (max 3 attempts)**:
```
Attempt 1: Job1 → JobRun1 (FAILED)
                ↓
           RetryController creates Job2 (retry_of: Job1)
                ↓
Attempt 2: Job2 → JobRun2 (FAILED)
                ↓
           RetryController creates Job3 (retry_of: Job2)
                ↓
Attempt 3: Job3 → JobRun3 (FAILED)
                ↓
           RetryController: max attempts reached, no auto-retry
                ↓
           Job3 marked as permanently failed
```

**Backoff Strategy**:
- Base delay: configurable (e.g., 10 seconds)
- Formula: `delay = base * (2 ^ attempt_number)`
- Example: 10s → 20s → 40s

---

### 4.2 Manual Retry Semantics

```
POST /api/job-runs/{run_id}/retry
    ↓
Validate: run_id exists, status = FAILED
    ↓
Create new Job with:
  - template_id from original
  - params snapshot from original
  - retry_of = original_job_id
  - priority: same or specified
    ↓
Enqueue to QueueManager
    ↓
Return new job_id
```

Manual retry is always allowed, regardless of automatic retry count.

---

### 4.3 Crash/Restart Recovery (DEC-008)

**On Scheduler Startup**:
```
1. Load all Jobs from SQLite
2. For each Job:
   - QUEUED: Restore to queue (preserve order)
   - RUNNING: Mark as FAILED (orphaned)
     - Create JobRun with status=FAILED, error="Scheduler crash recovery"
     - Trigger RetryController evaluation
3. Resume normal dispatch loop
```

**Orphaned Job Handling**:
- RUNNING jobs from previous session cannot be verified
- Conservative approach: mark as FAILED, let retry handle
- Webhook fires for recovery-failed jobs

---

## 5. Explicit Non-Goals

The following are **explicitly out of scope** for this implementation:

### 5.1 Distributed Workers

- All workers run on the same machine
- No network coordination protocol
- No distributed locking
- Reference: CON-001 (Single Machine Deployment)

### 5.2 Preemption

- Running jobs are NEVER interrupted
- Direct APIs wait, not preempt
- Cancel requests on RUNNING jobs wait for completion
- Reference: DEC-004 (Next-Slot Reservation)

### 5.3 UI Coupling

- No UI-specific endpoints
- No dashboard data aggregation
- No websocket push for status updates
- Reference: API_CONTRACT.md Section 9 (Non-Goals)

### 5.4 Complex Scheduling Patterns

- No job dependencies (DAG execution)
- No conditional execution (if-then-else)
- No cross-job data passing
- Simple cron + manual + retry only

### 5.5 Exactly-Once Semantics

- Webhooks are at-least-once, not exactly-once
- Duplicate deliveries possible
- Client-side idempotency required
- Reference: DEC-009

---

## 6. Open Questions (NOT RESOLVED)

The following questions remain open. Implementation must accommodate multiple possible resolutions.

### OQ-001: Concurrency Limit Strategy

**Question**: How should we limit concurrent job execution?

**Implementation Options**:

| Option | Description | Trade-offs |
|--------|-------------|------------|
| **Global limit** | Max N jobs running total | Simple; doesn't distinguish resource needs |
| **Per-type limit** | Max N story, M research | Flexible; requires type registry |
| **Resource-based** | Based on tagged resources | Most flexible; complex configuration |

**Implementation Guidance**:
- Design Dispatcher with pluggable concurrency policy
- Default: single worker (CON-002 constraint for Ollama)
- Interface should support future policy changes

**Placeholder Interface**:
```
ConcurrencyPolicy:
  can_dispatch(job) → bool
  on_job_started(job)
  on_job_completed(job)
```

---

### OQ-002: JobGroup Sequential Failure Behavior

**Question**: In a sequential JobGroup, what happens when one job fails?

**Implementation Options**:

| Option | Description | Trade-offs |
|--------|-------------|------------|
| **Stop immediately** | Cancel remaining jobs | Safest; may waste prep work |
| **Continue all** | Execute all regardless | Runs everything; may cascade failures |
| **Configurable** | `on_failure: stop \| continue \| skip` | Flexible; more complex API |

**Implementation Guidance**:
- Design JobGroup executor with injectable failure handler
- Store policy in JobGroup entity (if configurable option chosen)
- Default behavior: stop (safest)

**Placeholder Interface**:
```
GroupFailurePolicy:
  on_member_failed(group, failed_job) → Action

Action: STOP | CONTINUE | SKIP_REMAINING
```

---

## 7. Component Dependencies

```
                    ┌────────────────┐
                    │ ScheduleTrigger│
                    └───────┬────────┘
                            │ creates Jobs
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

