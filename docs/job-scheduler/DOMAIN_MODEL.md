# Job Scheduler Domain Model

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 1.5.0 (managed by release-please)
> **Last Updated:** 2026-01-18

---

## Overview

This document defines the canonical domain model for the Job Scheduler system. These entities form the conceptual foundation for all scheduler-related functionality. Implementation details are intentionally omitted; this document serves as the authoritative reference for what each entity represents and why it exists.

---

## Entity Definitions

### 1. JobTemplate

#### Purpose

A JobTemplate represents a **reusable specification** for work that can be executed. It captures the "what" and "how" of a task without committing to "when" or "how many times."

#### Responsibilities

- Define the type of work (research, story generation, etc.)
- Store default parameters for execution
- Provide a stable reference for creating Jobs
- Enable reuse across multiple executions

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `template_id` | Unique identifier |
| `name` | Human-readable label |
| `job_type` | Type of work (e.g., `research`, `story`) |
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
- **ARCHIVED**: Soft-deleted, not available for new Jobs

#### What JobTemplate is NOT

- JobTemplate is NOT an execution record
- JobTemplate does NOT track run history
- JobTemplate does NOT store runtime state
- JobTemplate does NOT enforce scheduling

---

### 2. Schedule

#### Purpose

A Schedule defines **when** work should be executed. It binds a JobTemplate to a temporal pattern, enabling automated, recurring execution.

#### Responsibilities

- Define execution timing (cron expression or interval)
- Reference the JobTemplate to execute
- Track next execution time
- Enable/disable automated execution

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `schedule_id` | Unique identifier |
| `name` | Human-readable label |
| `template_id` | Reference to JobTemplate |
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
- **ENABLED**: Schedule actively creates Jobs at defined times
- **DISABLED**: Schedule paused, no new Jobs created
- **DELETED**: Schedule removed

#### What Schedule is NOT

- Schedule is NOT a Job
- Schedule does NOT execute work directly
- Schedule does NOT store execution results
- Schedule does NOT manage queue position

---

### 3. Job

#### Purpose

A Job represents a **single unit of work** that has been queued for execution. It is an ephemeral entity that exists from the moment work is requested until execution completes.

#### Responsibilities

- Represent a specific execution request
- Hold execution parameters (potentially overriding template defaults)
- Track queue position and priority
- Transition through execution states

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `job_id` | Unique identifier |
| `template_id` | Reference to source JobTemplate (nullable for ad-hoc jobs) |
| `schedule_id` | Reference to triggering Schedule (nullable) |
| `group_id` | Reference to JobGroup (nullable) |
| `job_type` | Type of work |
| `params` | Resolved execution parameters |
| `priority` | Execution priority |
| `position` | Queue position (for ordered execution) |
| `status` | Current state |
| `created_at` | Creation timestamp |
| `queued_at` | When added to queue |

#### Lifecycle

**External (API/Webhook visible):**
```
QUEUED → RUNNING → CANCELLED
```

| Status | Meaning |
|--------|---------|
| **QUEUED** | Job in queue, awaiting execution |
| **RUNNING** | Job actively executing |
| **CANCELLED** | Job cancelled before completion |

**Internal only (not exposed via API):**
- `PENDING`: Job created but not yet queued (e.g., awaiting group)
- `DISPATCHED`: Job assigned to worker (brief transition state)

> Note: Execution outcome (success/failure) is recorded in JobRun, not Job.

#### What Job is NOT

- Job is NOT a historical record (that is JobRun)
- Job does NOT persist after completion indefinitely
- Job does NOT define what work to do (that is JobTemplate)
- Job does NOT define when to execute (that is Schedule)

---

### 4. JobRun

#### Purpose

A JobRun represents a **historical record** of a single execution attempt. It is the immutable audit trail of what happened when a Job was executed.

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
| `job_id` | Reference to the Job |
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

#### What JobRun is NOT

- JobRun is NOT mutable after creation
- JobRun does NOT control execution
- JobRun does NOT affect queue state
- JobRun does NOT store configuration (only snapshots)

---

### 5. JobGroup

#### Purpose

A JobGroup represents a **logical collection** of Jobs that share execution constraints. It enables batch operations and coordinated execution.

#### Responsibilities

- Group related Jobs together
- Define execution mode (parallel or sequential within group)
- Track aggregate completion status
- Enable batch operations (cancel all, reorder all)

#### Conceptual Fields

| Field | Description |
|-------|-------------|
| `group_id` | Unique identifier |
| `name` | Human-readable label (optional) |
| `mode` | Execution mode (`parallel` or `sequential`) |
| `job_ids` | Ordered list of Job references |
| `status` | Aggregate status |
| `created_at` | Creation timestamp |
| `started_at` | When first job started |
| `finished_at` | When last job finished |

#### Lifecycle

```
CREATED → QUEUED → RUNNING → [terminal state]

Terminal states:
- COMPLETED (all jobs finished)
- PARTIAL (some jobs failed)
- CANCELLED
```

- **CREATED**: Group defined, jobs being added
- **QUEUED**: Group in queue, awaiting execution
- **RUNNING**: At least one job in group is executing
- **COMPLETED**: All jobs finished (success or skip)
- **PARTIAL**: Some jobs succeeded, some failed
- **CANCELLED**: Group cancelled

#### What JobGroup is NOT

- JobGroup is NOT a JobTemplate (it does not define work)
- JobGroup is NOT a Schedule (it does not define timing)
- JobGroup does NOT execute work (Jobs do)
- JobGroup does NOT persist execution history (JobRuns do)

---

## Key Distinctions

### JobTemplate vs Job

| Aspect | JobTemplate | Job |
|--------|-------------|-----|
| Lifespan | Long-lived | Ephemeral |
| Purpose | Define work | Request execution |
| Mutability | Mutable | Immutable after queued |
| Cardinality | One template → Many jobs | One job → One execution |

### Job vs JobRun

| Aspect | Job | JobRun |
|--------|-----|--------|
| Temporal scope | Future/present | Past |
| Purpose | Queue management | Audit trail |
| Mutability | State changes | Immutable |
| Retention | Temporary | Permanent |

### Schedule vs JobGroup

| Aspect | Schedule | JobGroup |
|--------|----------|----------|
| Trigger | Time-based | Explicit |
| Scope | Single template | Multiple jobs |
| Recurrence | Repeating | One-time |

---

## Design Principles

1. **Separation of Concerns**
   - Configuration (JobTemplate) is separate from execution (Job/JobRun)
   - Timing (Schedule) is separate from grouping (JobGroup)

2. **Single Responsibility**
   - Each entity has one clear purpose
   - No entity handles both configuration and execution

3. **Immutability Where Appropriate**
   - JobRun is immutable (audit integrity)
   - Job is immutable after dispatch (execution consistency)

4. **Explicit Over Implicit**
   - All relationships are explicit references
   - No hidden state or magic behavior

---

## Glossary

| Term | Definition |
|------|------------|
| **Execution** | The act of running work defined by a Job |
| **Dispatch** | Assigning a Job to a Worker for execution |
| **Queue** | Ordered collection of Jobs awaiting execution |
| **Worker** | Component that performs actual execution |
| **Artifact** | File produced by execution (e.g., story JSON) |
| **Priority** | Relative importance affecting execution order |
