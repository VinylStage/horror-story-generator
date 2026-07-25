# Task Scheduler Domain Model

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 2.0.3 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18

---

## Overview

This document defines the canonical domain model for the Task Scheduler system. These entities form the conceptual foundation for all scheduler-related functionality. Implementation details are intentionally omitted; this document serves as the authoritative reference for what each entity represents and why it exists.

---

## Entity Definitions

### 1. TaskTemplate

#### Purpose

A TaskTemplate represents a **reusable specification** for work that can be executed. It captures the "what" and "how" of a task without committing to "when" or "how many times."

#### Responsibilities

- Define the type of work (research, story generation, etc.)
- Store default parameters for execution
- Provide a stable reference for creating Tasks
- Enable reuse across multiple executions

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `template_id` | Unique identifier |
| `name` | Human-readable label |
| `task_type` | Type of work (e.g., `research`, `story`) |
| `default_params` | Default execution parameters |
| `description` | Optional documentation |
| `created_at` | Creation timestamp |
| `updated_at` | Last modification timestamp |

#### Lifecycle

```
CREATED → ACTIVE → [ARCHIVED]
```

- **CREATED**: Template exists and can be used
- **ACTIVE**: Normal operational state
- **ARCHIVED**: Soft-deleted, not available for new Tasks

#### What TaskTemplate is NOT

- TaskTemplate is NOT an execution record
- TaskTemplate does NOT track run history
- TaskTemplate does NOT store runtime state
- TaskTemplate does NOT enforce scheduling

---

### 2. Schedule

#### Purpose

A Schedule defines **when** work should be executed. It binds a TaskTemplate to a temporal pattern, enabling automated, recurring execution.

#### Responsibilities

- Define execution timing (cron expression or interval)
- Reference the TaskTemplate to execute
- Track next execution time
- Enable/disable automated execution

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `schedule_id` | Unique identifier |
| `name` | Human-readable label |
| `template_id` | Reference to TaskTemplate |
| `cron_expression` | Temporal pattern (e.g., `0 9 * * *`) |
| `timezone` | Timezone for cron interpretation |
| `enabled` | Whether schedule is active |
| `param_overrides` | Optional parameter overrides |
| `last_triggered_at` | Last trigger timestamp |
| `next_trigger_at` | Computed next trigger time |
| `created_at` | Creation timestamp |

#### Lifecycle

```
CREATED → ENABLED ⇄ DISABLED → [DELETED]
```

- **CREATED**: Schedule defined but not yet enabled
- **ENABLED**: Schedule actively creates Tasks at defined times
- **DISABLED**: Schedule paused, no new Tasks created
- **DELETED**: Schedule removed

#### What Schedule is NOT

- Schedule is NOT a Task
- Schedule does NOT execute work directly
- Schedule does NOT store execution results
- Schedule does NOT manage queue position

---

### 3. Task

#### Purpose

A Task represents a **single unit of work** that has been queued for execution. It is an ephemeral entity that exists from the moment work is requested until execution completes.

#### Responsibilities

- Represent a specific execution request
- Hold execution parameters (potentially overriding template defaults)
- Track queue position and priority
- Transition through execution states

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `task_id` | Unique identifier |
| `template_id` | Reference to source TaskTemplate (nullable for ad-hoc tasks) |
| `schedule_id` | Reference to triggering Schedule (nullable) |
| `group_id` | Reference to TaskGroup (nullable) |
| `task_type` | Type of work |
| `params` | Resolved execution parameters |
| `priority` | Execution priority |
| `position` | Queue position (for ordered execution) |
| `status` | Current state |
| `created_at` | Creation timestamp |
| `queued_at` | When added to queue |

#### Lifecycle

```
QUEUED → RUNNING → COMPLETED | FAILED
QUEUED → CANCELLED
```

| Status | Meaning |
|--------|---------|
| **QUEUED** | Task in queue, awaiting execution |
| **RUNNING** | Task actively executing |
| **COMPLETED** | Task execution finished successfully |
| **FAILED** | Task execution encountered an error |
| **CANCELLED** | Task cancelled before completion |

#### What Task is NOT

- Task is NOT a historical record (that is TaskRun)
- Task does NOT persist after completion indefinitely
- Task does NOT define what work to do (that is TaskTemplate)
- Task does NOT define when to execute (that is Schedule)

---

### 4. TaskRun

#### Purpose

A TaskRun represents a **historical record** of a single execution attempt. It is the immutable audit trail of what happened when a Task was executed.

#### Responsibilities

- Record execution start and end times
- Store execution outcome (success, failure, skip)
- Preserve error information
- Reference produced artifacts
- Enable execution history queries

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `run_id` | Unique identifier |
| `task_id` | Reference to the Task |
| `template_id` | Snapshot of template used |
| `params_snapshot` | Snapshot of parameters used |
| `status` | Execution result |
| `started_at` | Execution start timestamp |
| `finished_at` | Execution end timestamp |
| `duration_ms` | Execution duration |
| `worker_id` | Identifier of executing worker |
| `exit_code` | Process exit code (if applicable) |
| `error` | Error message (if failed) |
| `artifacts` | List of produced file paths |
| `log_path` | Path to execution log |

#### Lifecycle

**External (API/Webhook visible):**
```
COMPLETED | FAILED | SKIPPED
```

| Status | Meaning |
|--------|---------|
| **COMPLETED** | Execution finished successfully |
| **FAILED** | Execution encountered an error |
| **SKIPPED** | Execution was skipped (e.g., duplicate detection) |

**Internal only:**
- `STARTED`: Execution began (brief transition, recorded as timestamp)

#### What TaskRun is NOT

- TaskRun is NOT mutable after creation
- TaskRun does NOT control execution
- TaskRun does NOT affect queue state
- TaskRun does NOT store configuration (only snapshots)

---

### 5. TaskGroup

#### Purpose

A TaskGroup represents a **logical collection** of Tasks that share execution constraints. It enables batch operations and coordinated execution.

#### Responsibilities

- Group related Tasks together
- Define execution mode (parallel or sequential within group)
- Track aggregate completion status
- Enable batch operations (cancel all, reorder all)

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `group_id` | Unique identifier |
| `name` | Human-readable label (optional) |
| `mode` | Execution mode (`parallel` or `sequential`) |
| `task_ids` | Ordered list of Task references |
| `status` | Aggregate status |
| `created_at` | Creation timestamp |
| `started_at` | When first task started |
| `finished_at` | When last task finished |

#### Lifecycle

```
CREATED → QUEUED → RUNNING → [terminal state]

Terminal states:
- COMPLETED (all tasks finished)
- PARTIAL (some tasks failed)
- CANCELLED
```

- **CREATED**: Group defined, tasks being added
- **QUEUED**: Group in queue, awaiting execution
- **RUNNING**: At least one task in group is executing
- **COMPLETED**: All tasks finished (success or skip)
- **PARTIAL**: Some tasks succeeded, some failed
- **CANCELLED**: Group cancelled

#### What TaskGroup is NOT

- TaskGroup is NOT a TaskTemplate (it does not define work)
- TaskGroup is NOT a Schedule (it does not define timing)
- TaskGroup does NOT execute work (Tasks do)
- TaskGroup does NOT persist execution history (TaskRuns do)

---

## Key Distinctions

### TaskTemplate vs Task

| Aspect | TaskTemplate | Task |
|--------|-------------|------|
| Lifespan | Long-lived | Ephemeral |
| Purpose | Define work | Request execution |
| Mutability | Mutable | Immutable after queued |
| Cardinality | One template → Many tasks | One task → One execution |

### Task vs TaskRun

| Aspect | Task | TaskRun |
|--------|------|--------|
| Temporal scope | Future/present | Past |
| Purpose | Queue management | Audit trail |
| Mutability | State changes | Immutable |
| Retention | Temporary | Permanent |

### Schedule vs TaskGroup

| Aspect | Schedule | TaskGroup |
|--------|----------|----------|
| Trigger | Time-based | Explicit |
| Scope | Single template | Multiple tasks |
| Recurrence | Repeating | One-time |

---

## Design Principles

1. **Separation of Concerns**
   - Configuration (TaskTemplate) is separate from execution (Task/TaskRun)
   - Timing (Schedule) is separate from grouping (TaskGroup)

2. **Single Responsibility**
   - Each entity has one clear purpose
   - No entity handles both configuration and execution

3. **Immutability Where Appropriate**
   - TaskRun is immutable (audit integrity)
   - Task is immutable after dispatch (execution consistency)

4. **Explicit Over Implicit**
   - All relationships are explicit references
   - No hidden state or magic behavior

---

## Glossary

| Term | Definition |
|------|------------|
| **Execution** | The act of running work defined by a Task |
| **Dispatch** | Assigning a Task to a Worker for execution |
| **Queue** | Ordered collection of Tasks awaiting execution |
| **Worker** | Component that performs actual execution |
| **Artifact** | File produced by execution (e.g., story JSON) |
| **Priority** | Relative importance affecting execution order |

---

## Related Documents

- [ENTITY_RELATIONSHIPS.md](./ENTITY_RELATIONSHIPS.md) - 엔티티 관계 정의
- [PERSISTENCE_SCHEMA.md](./PERSISTENCE_SCHEMA.md) - 영속성 스키마
- [API_CONTRACT.md](./API_CONTRACT.md) - API 계약
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요
