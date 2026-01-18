# Job Scheduler API Impact Analysis

> **Status:** FINAL (Phase 5 Complete)
> **Document Version:** 1.0.0
> **Application Version:** 1.5.0 (managed by release-please)
> **Last Updated:** 2026-01-18

---

## Overview

This document analyzes how the proposed Job Scheduler system impacts existing API endpoints. It covers endpoint mapping to domain entities, breaking changes, migration strategies, and coexistence patterns.

---

## Current API Structure

### Existing Endpoints Summary

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
| `/jobs` | `/story/trigger` | POST | Async, immediate execution |
| `/jobs` | `/research/trigger` | POST | Async, immediate execution |
| `/jobs` | `/batch/trigger` | POST | Async, parallel execution |
| `/jobs` | `/batch/{batch_id}` | GET | Batch status |
| `/jobs` | `/{job_id}` | GET | Job status |
| `/jobs` | (list) | GET | List all jobs |
| `/jobs` | `/{job_id}/cancel` | POST | Cancel job |
| `/jobs` | `/monitor` | POST | Monitor all jobs |
| `/jobs` | `/{job_id}/monitor` | POST | Monitor single job |
| `/jobs` | `/{job_id}/dedup_check` | POST | Check dedup for job |

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
- Direct APIs do NOT create Jobs in the scheduler
- They reserve the next execution slot (no preemption of running jobs)
- Execution order: [current job finishes] → [direct request] → [queue resumes]

---

### Category 2: Job Trigger APIs (Current Async)

These endpoints create jobs that execute **immediately but asynchronously**.

```
POST /jobs/story/trigger     → Async story job
POST /jobs/research/trigger  → Async research job
POST /jobs/batch/trigger     → Async batch jobs
```

**Current Behavior**:
- Job created immediately
- Subprocess spawned immediately
- No queue, no waiting, no ordering

**Proposed Behavior**:
- Job created and added to queue
- Execution controlled by scheduler
- Supports priority, ordering, grouping

---

### Category 3: Job Management APIs

These endpoints query and control jobs.

```
GET  /jobs/{job_id}          → Job status
GET  /jobs                   → List jobs
POST /jobs/{job_id}/cancel   → Cancel job
POST /jobs/monitor           → Monitor all
POST /jobs/{job_id}/monitor  → Monitor single
```

**Impact**: These map directly to scheduler entities and will be enhanced.

---

## Entity Mapping

### Current → Proposed Mapping

| Current Concept | Current Implementation | Proposed Entity |
|-----------------|------------------------|-----------------|
| Job type "story" | `job_type` field | JobTemplate (named) |
| Job type "research" | `job_type` field | JobTemplate (named) |
| Job params | `params` dict | JobTemplate.default_params + Job.params |
| Batch | `Batch` dataclass | JobGroup |
| Job status | File-based JSON | Job + JobRun |
| Job ID | UUID string | Job.job_id |
| Batch ID | UUID string | JobGroup.group_id |
| None | None | Schedule (NEW) |

### Detailed Mapping

#### JobTemplate Mapping

Current: No explicit templates; job type is a string.

```python
# Current
create_job(job_type="story_generation", params={...})

# Proposed
# Pre-registered templates
template = get_template("daily-story")
create_job(template_id=template.id, params={...})
```

**Migration Path**:
1. Create default JobTemplates for "story_generation" and "research"
2. Support both `job_type` and `template_id` during transition
3. Deprecate `job_type` string in favor of `template_id`

#### Job Mapping

Current: Single Job entity with mixed responsibilities.

```python
# Current Job dataclass (legacy)
class Job:
    job_id: str
    type: str            # "story_generation" | "research"
    status: str          # "created" | "queued" | "running" | "succeeded" | "failed"
    # ... other fields
```

> Note: Legacy statuses `succeeded` and `failed` are replaced by JobRun statuses in the new model.

Proposed: Split into Job (queue) and JobRun (history).

```python
# Proposed Job (queue-level, external statuses only)
class Job:
    job_id: str
    template_id: Optional[str]
    schedule_id: Optional[str]
    group_id: Optional[str]
    params: dict
    priority: int
    position: int
    status: str  # QUEUED | RUNNING | CANCELLED

# Proposed JobRun (execution result)
class JobRun:
    run_id: str
    job_id: str
    status: str  # COMPLETED | FAILED | SKIPPED
    started_at: datetime
    finished_at: Optional[datetime]
    pid: Optional[int]
    exit_code: Optional[int]
    error: Optional[str]
    artifacts: List[str]
    log_path: Optional[str]
```

#### Batch → JobGroup Mapping

Current:
```python
class Batch:
    batch_id: str
    job_ids: List[str]
    status: str
    webhook_url: Optional[str]
    created_at: str
```

Proposed:
```python
class JobGroup:
    group_id: str
    name: Optional[str]
    mode: str  # "parallel" | "sequential"
    job_ids: List[str]
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
POST   /queue/{job_id}/priority    Set job priority
POST   /queue/{job_id}/move        Move job position
GET    /queue/stats                Queue statistics
```

### JobRun Queries

```
GET    /runs                       List job runs (history)
GET    /runs/{run_id}              Get run details
GET    /jobs/{job_id}/runs         Get runs for job (1:1, but useful for retry chains)
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
| JobRun as separate entity | Low | Job status still accessible |

### Medium Risk (Behavioral)

These changes alter existing behavior but maintain API compatibility.

| Change | Risk | Mitigation |
|--------|------|------------|
| Jobs enter queue instead of immediate execution | Medium | Add `priority: "immediate"` flag for legacy behavior |
| Batch becomes JobGroup | Medium | Keep `/jobs/batch/*` as aliases |
| Job status reflects queue position | Medium | Add `queue_position` field, keep `status` semantics |

### High Risk (Breaking)

These changes break existing clients.

| Change | Risk | Mitigation |
|--------|------|------------|
| None identified | - | - |

---

## Coexistence Strategy

### Phase 1: Parallel Operation

Run old and new systems in parallel.

```
┌─────────────────────────────────────────────────────┐
│                    API Gateway                       │
├─────────────────────────────────────────────────────┤
│  Legacy Path              │  New Path               │
│  /jobs/story/trigger      │  /scheduler/jobs        │
│  /jobs/research/trigger   │  /scheduler/templates   │
│  /jobs/batch/trigger      │  /scheduler/schedules   │
│         │                 │         │               │
│         ▼                 │         ▼               │
│  ┌─────────────┐          │  ┌─────────────┐        │
│  │ Old System  │          │  │ Scheduler   │        │
│  │ (Immediate) │          │  │ (Queued)    │        │
│  └─────────────┘          │  └─────────────┘        │
└─────────────────────────────────────────────────────┘
```

**Implementation**:
1. Mount scheduler endpoints under `/scheduler/` prefix
2. Keep existing `/jobs/*` endpoints unchanged
3. Clients opt-in to new system

### Phase 2: Migration Period

Add compatibility layer.

```python
# In legacy /jobs/story/trigger endpoint
@router.post("/story/trigger")
async def trigger_story_generation(request: StoryTriggerRequest):
    if config.USE_SCHEDULER:
        # Route to scheduler with immediate priority
        return await scheduler.create_job(
            template_id="story_generation",
            params=request.model_dump(),
            priority=Priority.IMMEDIATE,
        )
    else:
        # Legacy behavior
        return legacy_trigger_story(request)
```

### Phase 3: Deprecation

1. Log deprecation warnings on legacy endpoints
2. Provide migration guide
3. Set sunset date
4. Remove legacy endpoints

---

## Request/Response Changes

### Job Trigger Request Evolution

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

### Job Status Response Evolution

**Current**:
```json
{
  "job_id": "abc123",
  "type": "story_generation",
  "status": "running",
  "pid": 12345,
  "created_at": "2026-01-18T10:00:00Z"
}
```

**Proposed**:
```json
{
  "job_id": "abc123",
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
/api/v1/jobs/*      → Legacy system
/api/v2/jobs/*      → New scheduler
```

### Option B: Header-Based

```
X-API-Version: 1    → Legacy system
X-API-Version: 2    → New scheduler
```

### Option C: Query Parameter

```
/jobs/*?version=1   → Legacy system
/jobs/*?version=2   → New scheduler
```

**Recommendation**: Path prefix (Option A) for clarity and tooling compatibility.

---

## Direct API Integration

### How Direct APIs Interact with Scheduler

Direct APIs (`/story/generate`, `/research/run`) follow these rules:

1. **DO NOT** create scheduler Jobs
2. **DO NOT** preempt a currently running Job
3. **Reserve the next execution slot** (executed immediately after current Job)
4. **Queue resumes normally** after direct execution completes

```
┌──────────────────┐                    ┌───────────────┐
│ POST /story/gen  │───────────────────►│   Reserve     │
│   (Direct API)   │   Next-Slot        │  Next Slot    │
└──────────────────┘   Reservation      └───────┬───────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │  Wait for current job │
                                    │  then execute         │
                                    └───────────────────────┘
```

### Next-Slot Reservation Pattern

When a direct API is called while a job is running:

```
Before Direct API:
┌─────────────────────────────────────┐
│ Queue: [Job1(RUNNING), Job2, Job3]  │
└─────────────────────────────────────┘

Direct API Called:
┌─────────────────────────────────────┐
│ 1. Job1 continues (NO preemption)   │
│ 2. Direct request reserves next slot│
│ 3. Job1 finishes                    │
│ 4. Direct request executes          │
│ 5. Queue resumes with Job2          │
└─────────────────────────────────────┘

After Direct API:
┌─────────────────────────────────────┐
│ Queue: [Job2(RUNNING), Job3]        │
└─────────────────────────────────────┘
```

This guarantees:
- **Immediate responsiveness** (reserves slot instantly)
- **No forced interruption** (running job completes normally)
- **Deterministic ordering** (direct → remaining queue)

---

## Summary: Endpoint Mapping Table

| Current Endpoint | Scheduler Entity | Change Type |
|------------------|------------------|-------------|
| `POST /story/generate` | None (Direct) | Unchanged |
| `POST /research/run` | None (Direct) | Unchanged |
| `POST /jobs/story/trigger` | Job + JobTemplate | Enhanced |
| `POST /jobs/research/trigger` | Job + JobTemplate | Enhanced |
| `POST /jobs/batch/trigger` | JobGroup + Jobs | Enhanced |
| `GET /jobs/{job_id}` | Job + JobRun | Enhanced |
| `GET /jobs` | Job (list) | Enhanced |
| `POST /jobs/{job_id}/cancel` | Job.status | Unchanged |
| `POST /jobs/monitor` | JobRun | Enhanced |
| NEW: Schedule endpoints | Schedule | Added |
| NEW: Template endpoints | JobTemplate | Added |
| NEW: Queue endpoints | Job (queue view) | Added |
| NEW: Run endpoints | JobRun | Added |

---

## Glossary

| Term | Definition |
|------|------------|
| **Direct API** | Synchronous endpoint that executes work immediately |
| **Job API** | Asynchronous endpoint that creates schedulable work |
| **Legacy System** | Current immediate-execution job system |
| **Coexistence** | Period where both systems operate in parallel |
| **Next-Slot Reservation** | Direct API reserving next execution slot without preempting current job |

