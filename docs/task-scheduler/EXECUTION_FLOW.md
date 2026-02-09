# Task Scheduler Execution Flow

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 2.0.1 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Purpose

This document provides visual representations of the Task Scheduler execution flows.
Each diagram is accompanied by a text explanation.

---

## 1. Normal Queue Execution

### Diagram

```mermaid
sequenceDiagram
    participant S as ScheduleTrigger
    participant Q as QueueManager
    participant D as Dispatcher
    participant E as Executor
    participant P as PersistenceAdapter
    participant W as WebhookService
    participant R as RetryController

    Note over S: Cron fires or Manual API called
    S->>Q: enqueue(new Task)
    Q->>P: persist Task (QUEUED)
    P-->>Q: OK
    Q-->>S: task_id

    loop Dispatch Loop
        D->>Q: get_next_task()
        Q-->>D: Task (or null)
        alt Task available
            D->>P: update Task (RUNNING)
            D->>E: execute(task)
            E->>P: create TaskRun
            E->>E: run work
            alt Success
                E->>P: update TaskRun (COMPLETED)
            else Failure
                E->>P: update TaskRun (FAILED)
                E->>R: notify_failure(task, run)
            else Skip
                E->>P: update TaskRun (SKIPPED)
            end
            E-->>D: completion signal
            D->>W: notify(task, run)
        end
    end
```

### Explanation

1. **Task Creation**: Either ScheduleTrigger (cron fires) or Manual API creates a new Task.

2. **Enqueue**: QueueManager receives the Task, assigns position, and persists to SQLite with status `QUEUED`.

3. **Dispatch Loop**: Dispatcher continuously polls QueueManager for the next available Task.

4. **Dispatch**: When a Task is available:
   - Task status transitions to `RUNNING`
   - Task is passed to Executor

5. **Execution**: Executor:
   - Creates a new TaskRun record
   - Runs the actual work (story generation, research, etc.)
   - Updates TaskRun with terminal status

6. **Post-Execution**:
   - On `FAILED`: RetryController is notified for potential retry
   - WebhookService sends notification
   - Dispatcher continues loop

---

## 2. Direct API Next-Slot Reservation

### Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant H as DirectExecHandler
    participant D as Dispatcher
    participant E as Executor
    participant Q as QueueManager

    Note over D: Task1 is RUNNING
    C->>H: POST /story/generate
    H->>D: reserve_next_slot()
    D-->>H: reservation_id

    Note over D: Queue dispatch PAUSED
    Note over E: Task1 still running...

    E-->>D: Task1 complete
    D->>H: slot_ready signal

    H->>E: execute_direct(request)
    E->>E: run story generation
    E-->>H: result

    H->>D: release_next_slot()
    Note over D: Queue dispatch RESUMED
    H-->>C: response

    D->>Q: get_next_task()
    Note over D: Task2 dispatched normally
```

### Explanation

1. **Request Arrives**: Client calls Direct API (e.g., `POST /story/generate`).

2. **Reserve Slot**: DirectExecutionHandler requests next-slot reservation from Dispatcher.

3. **Queue Paused**: Dispatcher pauses queue dispatch. No new tasks will be dispatched.

4. **Wait for Current Task**: If a task is currently running (Task1), it continues to completion. **No preemption occurs.**

5. **Execute Direct Request**: Once the slot is available:
   - DirectExecutionHandler executes the request
   - This is NOT a Task - no Task entity is created
   - Result returned directly to client

6. **Release Slot**: After completion, reservation is released.

7. **Resume Queue**: Dispatcher resumes normal queue dispatch. Next QUEUED task (Task2) is dispatched.

### Key Invariant (DEC-004)

```
Execution Order: [Current RUNNING Task] → [Direct Request] → [Remaining Queue]
```

- Direct requests NEVER preempt running tasks
- Queue is paused, not cleared
- Deterministic ordering guaranteed

---

## 3. Retry Loop

### Diagram

```mermaid
sequenceDiagram
    participant E as Executor
    participant R as RetryController
    participant Q as QueueManager
    participant P as PersistenceAdapter

    E->>R: notify_failure(task1, run1)
    R->>P: count_retry_chain(task1)
    P-->>R: attempts = 0

    Note over R: attempts < 3, create retry
    R->>R: calculate_backoff(attempt=1)
    R->>Q: enqueue(new Task2, retry_of=task1)
    Q->>P: persist Task2 (QUEUED)

    Note over E: Later: Task2 executes and fails
    E->>R: notify_failure(task2, run2)
    R->>P: count_retry_chain(task2)
    P-->>R: attempts = 1

    Note over R: attempts < 3, create retry
    R->>R: calculate_backoff(attempt=2)
    R->>Q: enqueue(new Task3, retry_of=task2)

    Note over E: Later: Task3 executes and fails
    E->>R: notify_failure(task3, run3)
    R->>P: count_retry_chain(task3)
    P-->>R: attempts = 2

    Note over R: attempts < 3, create retry
    R->>Q: enqueue(new Task4, retry_of=task3)

    Note over E: Later: Task4 executes and fails
    E->>R: notify_failure(task4, run4)
    R->>P: count_retry_chain(task4)
    P-->>R: attempts = 3

    Note over R: attempts >= 3, NO auto-retry
    R->>P: mark_permanently_failed(task4)
```

### Explanation

1. **Failure Notification**: When Executor completes a TaskRun with status `FAILED`, it notifies RetryController.

2. **Chain Counting**: RetryController traverses the `retry_of` chain to count total attempts.

3. **Retry Decision** (DEC-007):
   - If attempts < 3: Create new Task with `retry_of` reference
   - If attempts >= 3: Mark as permanently failed, no auto-retry

4. **Backoff Calculation**:
   - Formula: `delay = base_delay * (2 ^ attempt_number)`
   - Example with 10s base: 10s → 20s → 40s

5. **Chain Structure**:
   ```
   Task1 (original)
     └── Task2 (retry_of: Task1)
           └── Task3 (retry_of: Task2)
                 └── Task4 (retry_of: Task3) ← max reached
   ```

6. **Manual Retry**: Always available via `POST /api/task-runs/{run_id}/retry`, regardless of auto-retry count.

---

## 4. Crash Recovery Flow

### Diagram

```mermaid
sequenceDiagram
    participant SC as Scheduler
    participant P as PersistenceAdapter
    participant Q as QueueManager
    participant R as RetryController
    participant W as WebhookService

    Note over SC: Scheduler starts after crash
    SC->>P: load_all_tasks()
    P-->>SC: [Task1(RUNNING), Task2(QUEUED), Task3(QUEUED)]

    loop For each RUNNING task
        SC->>P: create TaskRun(FAILED, error="Crash recovery")
        SC->>P: update Task status
        SC->>R: notify_failure(task, run)
        SC->>W: notify(task, run)
    end

    loop For each QUEUED task
        SC->>Q: restore_to_queue(task)
    end

    Note over Q: Queue restored: [Task2, Task3]
    Note over SC: Normal dispatch loop begins
```

### Explanation

1. **Startup**: Scheduler process starts after unexpected termination.

2. **Load State**: All tasks loaded from SQLite.

3. **Handle RUNNING Tasks** (orphaned from crash):
   - Cannot verify actual execution state
   - Conservative approach: mark as FAILED
   - Create TaskRun with `error = "Scheduler crash recovery"`
   - Trigger RetryController (may create retry task)
   - Fire webhook notification

4. **Restore QUEUED Tasks**:
   - Add back to queue in original order
   - Position and priority preserved

5. **Resume Normal Operation**: Dispatch loop begins.

### Key Invariant (DEC-008)

- QUEUED tasks are NEVER lost due to restart
- RUNNING tasks are FAILED (safe assumption: incomplete)
- Retry logic handles recovery automatically

---

## 5. State Machine Summary

### Task States

```mermaid
stateDiagram-v2
    [*] --> QUEUED: Created
    QUEUED --> RUNNING: Dispatched
    QUEUED --> CANCELLED: Cancel request
    RUNNING --> [*]: Complete (outcome in TaskRun)
    CANCELLED --> [*]
```

### TaskRun States

```mermaid
stateDiagram-v2
    [*] --> COMPLETED: Success
    [*] --> FAILED: Error
    [*] --> SKIPPED: Skip condition met
```

### Combined View

```
Task Lifecycle:          TaskRun Lifecycle:
┌─────────────┐         ┌─────────────┐
│   QUEUED    │         │   Created   │
└──────┬──────┘         └──────┬──────┘
       │ dispatch              │ execution ends
       ▼                       ▼
┌─────────────┐    ┌──────────────────────────┐
│   RUNNING   │───►│ COMPLETED │ FAILED │ SKIPPED │
└──────┬──────┘    └──────────────────────────┘
       │ cancel
       ▼
┌─────────────┐
│  CANCELLED  │
└─────────────┘
```

---

## 6. Concurrency Visualization (OQ-001)

Since OQ-001 is unresolved, this section shows how different strategies would affect the flow.

### Option A: Global Limit (N=1)

```
Time →
Worker1: [Task1]────────[Task2]────────[Task3]────────
```

### Option B: Per-Type Limit (Story=1, Research=1)

```
Time →
Worker1 (Story):    [S1]────[S2]────[S3]────
Worker2 (Research): [R1]────[R2]────
```

### Option C: Resource-Based (Ollama=1, Remote=2)

```
Time →
Ollama:  [J1(ollama)]────[J3(ollama)]────
Remote1: [J2(remote)]────[J5(remote)]────
Remote2: [J4(remote)]────
```

**Implementation Note**: Dispatcher must support pluggable ConcurrencyPolicy interface to accommodate any chosen option.

---

## 7. TaskGroup Execution (OQ-002 Impact)

Since OQ-002 is unresolved, this section shows how different failure behaviors would affect sequential groups.

### Setup

```
TaskGroup (mode: sequential)
├── Task1
├── Task2
└── Task3
```

### Option A: Stop Immediately

```
Task1: COMPLETED
Task2: FAILED    ← failure occurs
Task3: CANCELLED ← never executed
```

### Option B: Continue All

```
Task1: COMPLETED
Task2: FAILED    ← failure occurs
Task3: COMPLETED ← still executed
```

### Option C: Configurable

```yaml
on_failure: stop     # → Option A behavior
on_failure: continue # → Option B behavior
on_failure: skip     # → Skip remaining without CANCELLED status
```

**Implementation Note**: TaskGroup executor must support injectable GroupFailurePolicy.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-18 | - | Initial execution flow diagrams |

---

## Related Documents

- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [RECOVERY_SCENARIOS.md](./RECOVERY_SCENARIOS.md) - 복구 시나리오
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - 구현 계획
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

