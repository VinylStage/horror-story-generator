# Task Scheduler API Impact Analysis

> **Status:** FINAL (v2.0.0 — Legacy Removed)
> **Document Version:** 2.0.0
> **Application Version:** 2.0.1 <!-- x-release-please-version -->
> **Last Updated:** 2026-02-08

---

> **v2.0.0 Note:** Legacy `/tasks/*` endpoints have been fully removed. The `POST /tasks` API is the sole interface for asynchronous task creation. Direct APIs (`/story/generate`, `/research/run`) remain unchanged.

## Overview

This document analyzes how the Task Scheduler system impacts API endpoints. It covers endpoint mapping to domain entities and the current API structure after legacy endpoint removal.

---

## Current API Structure

### Endpoints Summary

| Router | Endpoint | Method | Behavior |
|--------|----------|--------|----------|
| `/story` | `/generate` | POST | Synchronous, blocking |
| `/story` | `/list` | GET | List stories |
| `/story` | `/{story_id}` | GET | Get story details |
| `/research` | `/run` | POST | Synchronous, blocking |
| `/research` | `/validate` | POST | Synchronous |
| `/research` | `/list` | GET | List research cards |
| `/research` | `/dedup` | POST | Synchronous |
| `/research` | `/matching-templates` | POST | Synchronous |
| `/tasks` | (create) | POST | Async, queued execution |
| `/tasks` | (list) | GET | List all tasks |
| `/tasks` | `/{task_id}` | GET | Task status |
| `/tasks` | `/{task_id}` | PATCH | Update task priority |
| `/tasks` | `/{task_id}` | DELETE | Cancel task |
| `/tasks` | `/{task_id}/runs` | GET | Task execution history |
| `/tasks` | `/group` | POST | Create task group |
| `/scheduler` | `/start` | POST | Start scheduler |
| `/scheduler` | `/stop` | POST | Stop scheduler |
| `/scheduler` | `/status` | GET | Scheduler status |

---

## Endpoint Classification

### Category 1: Direct APIs (Synchronous)

These endpoints execute work **immediately and block** until completion.

```
POST /story/generate      → Blocking story generation
POST /research/run        → Blocking research generation
```

**Impact**: These remain unchanged. They use the "next-slot reservation" pattern.

**Scheduler Interpretation**:
- Direct APIs do NOT create Tasks in the scheduler
- They reserve the next execution slot (no preemption of running tasks)
- Execution order: [current task finishes] → [direct request] → [queue resumes]

---

### Category 2: Task Scheduler APIs (Async)

The `POST /tasks` endpoint creates tasks that are queued and executed asynchronously by the scheduler.

```
POST /tasks                  → Create task(s) (array input)
GET  /tasks                  → List all tasks
GET  /tasks/{task_id}        → Task status
PATCH /tasks/{task_id}       → Update task priority
DELETE /tasks/{task_id}      → Cancel task
GET  /tasks/{task_id}/runs   → Task execution history
POST /tasks/group            → Create task group
```

**Behavior**:
- Task created and added to queue
- Execution controlled by scheduler
- Supports priority, ordering, grouping
- Always takes array input (single or batch)

> **Note:** Legacy `/tasks/*` endpoints (trigger, batch, monitor, dedup_check) have been removed in v2.0.0.

---

## Entity Mapping

### Current → Proposed Mapping

| Current Concept | Current Implementation | Proposed Entity |
|-----------------|------------------------|-----------------|
| Task type "story" | `task_type` field | TaskTemplate (named) |
| Task type "research" | `task_type` field | TaskTemplate (named) |
| Task params | `params` dict | TaskTemplate.default_params + Task.params |
| Batch | `Batch` dataclass | TaskGroup |
| Task status | File-based JSON | Task + TaskRun |
| Task ID | UUID string | Task.task_id |
| Batch ID | UUID string | TaskGroup.group_id |
| None | None | Schedule (NEW) |

### Detailed Mapping

#### TaskTemplate Mapping

Current: No explicit templates; task type is a string.

```python
# Current
create_task(task_type="story_generation", params={...})

# Proposed
# Pre-registered templates
template = get_template("daily-story")
create_task(template_id=template.id, params={...})
```

**Migration Path**:
1. Create default TaskTemplates for "story_generation" and "research"
2. Support both `task_type` and `template_id` during transition
3. Deprecate `task_type` string in favor of `template_id`

#### Task Mapping

Current: Single Task entity with mixed responsibilities.

```python
# Current Task dataclass (legacy)
class Task:
    task_id: str
    type: str            # "story_generation" | "research"
    status: str          # "created" | "queued" | "running" | "succeeded" | "failed"
    # ... other fields
```

> Note: Legacy statuses `succeeded` and `failed` are replaced by TaskRun statuses in the new model.

Proposed: Split into Task (queue) and TaskRun (history).

```python
# Proposed Task (queue-level, external statuses only)
class Task:
    task_id: str
    template_id: Optional[str]
    schedule_id: Optional[str]
    group_id: Optional[str]
    params: dict
    priority: int
    position: int
    status: str  # QUEUED | RUNNING | CANCELLED

# Proposed TaskRun (execution result)
class TaskRun:
    run_id: str
    task_id: str
    status: str  # COMPLETED | FAILED | SKIPPED
    started_at: datetime
    finished_at: Optional[datetime]
    pid: Optional[int]
    exit_code: Optional[int]
    error: Optional[str]
    artifacts: List[str]
    log_path: Optional[str]
```

#### Batch → TaskGroup Mapping

Current:
```python
class Batch:
    batch_id: str
    task_ids: List[str]
    status: str
    webhook_url: Optional[str]
    created_at: str
```

Proposed:
```python
class TaskGroup:
    group_id: str
    name: Optional[str]
    mode: str  # "parallel" | "sequential"
    task_ids: List[str]
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
```

**Key Differences**:
- `mode` field for parallel vs sequential execution
- `name` for human-readable identification
- Timing fields for tracking

---

## New Endpoints Required

### Schedule Management

```
POST   /schedules                  Create schedule
GET    /schedules                  List schedules
GET    /schedules/{schedule_id}    Get schedule
PATCH  /schedules/{schedule_id}    Update schedule
DELETE /schedules/{schedule_id}    Delete schedule
POST   /schedules/{schedule_id}/enable   Enable schedule
POST   /schedules/{schedule_id}/disable  Disable schedule
POST   /schedules/{schedule_id}/trigger  Force trigger
```

### Template Management

```
POST   /templates                  Create template
GET    /templates                  List templates
GET    /templates/{template_id}    Get template
PATCH  /templates/{template_id}    Update template
DELETE /templates/{template_id}    Archive template
```

### Queue Management

```
GET    /queue                      View current queue
POST   /queue/reorder              Reorder queue items
POST   /queue/{task_id}/priority    Set task priority
POST   /queue/{task_id}/move        Move task position
GET    /queue/stats                Queue statistics
```

### TaskRun Queries

```
GET    /runs                       List task runs (history)
GET    /runs/{run_id}              Get run details
GET    /tasks/{task_id}/runs         Get runs for task (1:1, but useful for retry chains)
```

---

## Breaking Changes Analysis

### Low Risk (Additive)

These changes add new functionality without breaking existing clients.

| Change | Risk | Mitigation |
|--------|------|------------|
| New Schedule endpoints | None | Purely additive |
| New Template endpoints | None | Purely additive |
| New Queue endpoints | None | Purely additive |
| TaskRun as separate entity | Low | Task status still accessible |

### Medium Risk (Behavioral)

These changes alter existing behavior but maintain API compatibility.

| Change | Risk | Mitigation |
|--------|------|------------|
| Tasks enter queue instead of immediate execution | Medium | Add `priority: "immediate"` flag for legacy behavior |
| Batch becomes TaskGroup | Medium | Array input via `POST /tasks` |
| Task status reflects queue position | Medium | Add `queue_position` field, keep `status` semantics |

### High Risk (Breaking)

These changes break existing clients.

| Change | Risk | Mitigation |
|--------|------|------------|
| None identified | - | - |

---

## Migration Complete (v2.0.0)

Legacy `/tasks/*` endpoints have been fully removed. The migration is complete:

```
┌─────────────────────────────────────────────────────┐
│                    API Server                        │
├─────────────────────────────────────────────────────┤
│  Direct APIs               │  Task Scheduler        │
│  POST /story/generate      │  POST /tasks           │
│  POST /research/run        │  GET  /tasks           │
│         │                  │  GET  /tasks/{id}      │
│         ▼                  │  POST /tasks/group     │
│  ┌─────────────┐           │         │              │
│  │ Synchronous │           │         ▼              │
│  │ (Blocking)  │           │  ┌─────────────┐       │
│  └─────────────┘           │  │ Scheduler   │       │
│                            │  │ (Queued)    │       │
│                            │  └─────────────┘       │
└─────────────────────────────────────────────────────┘
```

**Removed endpoints** (previously `/tasks/*`):
- `POST /tasks/story/trigger` → Use `POST /tasks` with `type: "story"`
- `POST /tasks/research/trigger` → Use `POST /tasks` with `type: "research"`
- `POST /tasks/batch/trigger` → Use `POST /tasks` with array input
- `GET /tasks/{task_id}` → Use `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/cancel` → Use `DELETE /tasks/{task_id}`
- `POST /tasks/monitor` → Removed (scheduler handles status tracking)
- `POST /tasks/{task_id}/monitor` → Removed (use `GET /tasks/{task_id}`)
- `POST /tasks/{task_id}/dedup_check` → Removed

---

## Request/Response Changes

### Task Trigger Request Evolution

**Current**:
```json
{
  "max_stories": 1,
  "enable_dedup": true,
  "model": "gemini/gemini-2.0-flash-exp"
}
```

**Proposed**:
```json
{
  "template_id": "story_generation",
  "params": {
    "max_stories": 1,
    "enable_dedup": true,
    "model": "gemini/gemini-2.0-flash-exp"
  },
  "priority": "normal",
  "group_id": null,
  "position": null
}
```

**Backward Compatible Request** (Phase 2):
```json
{
  "max_stories": 1,
  "enable_dedup": true,
  "model": "gemini/gemini-2.0-flash-exp",
  "_scheduler": {
    "priority": "normal",
    "template_id": "story_generation"
  }
}
```

### Task Status Response Evolution

**Current**:
```json
{
  "task_id": "abc123",
  "type": "story_generation",
  "status": "running",
  "pid": 12345,
  "created_at": "2026-01-18T10:00:00Z"
}
```

**Proposed**:
```json
{
  "task_id": "abc123",
  "template_id": "story_generation",
  "template_name": "Story Generation",
  "status": "running",
  "queue_position": null,
  "priority": "normal",
  "created_at": "2026-01-18T10:00:00Z",
  "run": {
    "run_id": "run456",
    "status": "started",
    "started_at": "2026-01-18T10:00:05Z",
    "pid": 12345
  }
}
```

---

## API Versioning Strategy

### Option A: Path Prefix (Recommended)

```
/api/v1/tasks/*     → Legacy system
/api/v2/tasks/*     → New scheduler
```

### Option B: Header-Based

```
X-API-Version: 1    → Legacy system
X-API-Version: 2    → New scheduler
```

### Option C: Query Parameter

```
/tasks/*?version=1  → Legacy system
/tasks/*?version=2  → New scheduler
```

**Recommendation**: Path prefix (Option A) for clarity and tooling compatibility.

---

## Direct API Integration

### How Direct APIs Interact with Scheduler

Direct APIs (`/story/generate`, `/research/run`) follow these rules:

1. **DO NOT** create scheduler Tasks
2. **DO NOT** preempt a currently running Task
3. **Reserve the next execution slot** (executed immediately after current Task)
4. **Queue resumes normally** after direct execution completes

```
┌──────────────────┐                    ┌───────────────┐
│ POST /story/gen  │───────────────────►│   Reserve     │
│   (Direct API)   │   Next-Slot        │  Next Slot    │
└──────────────────┘   Reservation      └───────┬───────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │  Wait for current task│
                                    │  then execute         │
                                    └───────────────────────┘
```

### Next-Slot Reservation Pattern

When a direct API is called while a task is running:

```
Before Direct API:
┌─────────────────────────────────────┐
│ Queue: [Task1(RUNNING), Task2, Task3]  │
└─────────────────────────────────────┘

Direct API Called:
┌─────────────────────────────────────┐
│ 1. Task1 continues (NO preemption)  │
│ 2. Direct request reserves next slot│
│ 3. Task1 finishes                   │
│ 4. Direct request executes          │
│ 5. Queue resumes with Task2         │
└─────────────────────────────────────┘

After Direct API:
┌─────────────────────────────────────┐
│ Queue: [Task2(RUNNING), Task3]        │
└─────────────────────────────────────┘
```

This guarantees:
- **Immediate responsiveness** (reserves slot instantly)
- **No forced interruption** (running task completes normally)
- **Deterministic ordering** (direct → remaining queue)

---

## Summary: Endpoint Mapping Table

| Endpoint | Scheduler Entity | Status |
|----------|------------------|--------|
| `POST /story/generate` | None (Direct) | Unchanged |
| `POST /research/run` | None (Direct) | Unchanged |
| `POST /tasks` | Task | Active (replaces legacy `/tasks/*`) |
| `GET /tasks` | Task (list) | Active |
| `GET /tasks/{task_id}` | Task + TaskRun | Active |
| `PATCH /tasks/{task_id}` | Task | Active |
| `DELETE /tasks/{task_id}` | Task.status | Active |
| `GET /tasks/{task_id}/runs` | TaskRun | Active |
| `POST /tasks/group` | TaskGroup + Tasks | Active |
| `POST /scheduler/start` | Scheduler | Active |
| `POST /scheduler/stop` | Scheduler | Active |
| `GET /scheduler/status` | Scheduler | Active |

---

## Glossary

| Term | Definition |
|------|------------|
| **Direct API** | Synchronous endpoint that executes work immediately (`/story/generate`, `/research/run`) |
| **Task API** | Asynchronous endpoint that creates schedulable work (`POST /tasks`) |
| **Next-Slot Reservation** | Direct API reserving next execution slot without preempting current task |

---

## Related Documents

- [API_CONTRACT.md](./API_CONTRACT.md) - API 계약 및 구현 상태
- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요

