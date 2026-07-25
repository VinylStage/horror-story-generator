# Task Scheduler API Contract

> **Status:** IMPLEMENTED (Phase 3 API Integration Complete)
> **Document Version:** 2.0.0
> **Application Version:** 2.0.3 <!-- x-release-please-version -->
> **Last Updated:** 2026-01-18
> **Implementation Branch:** feat/88-scheduler-api-integration

---

## 1. Purpose

This document defines the **external API contract** for the Task Scheduler system.
It is intentionally **UI-agnostic** and serves as the authoritative reference for backend behavior, API semantics, and integration guarantees.

This contract aligns **API responses, internal state, and webhook payloads** to a single, consistent model.

### 1.1 Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Scheduler Control (`/scheduler/*`) | ✅ Implemented | start, stop, status |
| Tasks CRUD (`/tasks`) | ✅ Implemented | POST, GET, PATCH, DELETE |
| Task Runs (`/tasks/{id}/runs`) | ✅ Implemented | 1:1 Task-to-Run relationship |
| Legacy Trigger Endpoints | ❌ Removed | Removed in v2.0.0 (PR #139) |
| TaskTemplate APIs | 🔮 Planned | Phase 4+ |
| Schedule (Cron) APIs | 🔮 Planned | Phase 4+ |

---

## 2. Canonical Status Model (Unified)

### 2.1 Task Status (Queue-level)

Used for:
- Queue inspection
- Task control (cancel)
- Scheduler orchestration

| Status | Meaning |
|------|--------|
| QUEUED | Waiting in queue |
| RUNNING | Currently executing |
| COMPLETED | Execution finished successfully |
| FAILED | Execution failed |
| CANCELLED | Cancelled before completion |

> These statuses are exposed via API and webhooks.

---

### 2.2 TaskRun Status (Execution Result)

Used for:
- Execution history
- Webhook notifications
- Result inspection

| Status | Meaning |
|------|--------|
| COMPLETED | Execution finished successfully |
| FAILED | Execution failed |
| SKIPPED | Execution intentionally skipped |

> **No other result statuses are externally visible.**

---

## 3. Implemented APIs (Phase 3)

### 3.1 Scheduler Control APIs

Scheduler is an **independent system control plane**, NOT a sub-resource of Task.
This design enables future extensibility (`/scheduler/config`, `/scheduler/metrics`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scheduler/start` | Start scheduler (idempotent) |
| POST | `/scheduler/stop` | Stop scheduler (graceful) |
| GET | `/scheduler/status` | Get scheduler status + cumulative stats |

**Scheduler Status Response:**
```json
{
  "scheduler_running": true,
  "current_task_id": "task-123",
  "queue_length": 5,
  "cumulative_stats": {
    "total_executed": 42,
    "succeeded": 38,
    "failed": 3,
    "cancelled": 1,
    "skipped": 0
  },
  "has_active_reservation": false
}
```

### 3.2 Tasks CRUD APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Create task (enqueue to scheduler) |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{task_id}` | Get task details |
| PATCH | `/tasks/{task_id}` | Update task priority (QUEUED only) |
| DELETE | `/tasks/{task_id}` | Cancel task (QUEUED only) |
| GET | `/tasks/{task_id}/runs` | Get task execution history |

**Create Task Request:**
```json
{
  "type": "story",
  "params": {
    "max_stories": 1,
    "enable_dedup": true
  },
  "priority": 10
}
```

**Task Response:**
```json
{
  "task_id": "task-550e8400...",
  "task_type": "story",
  "status": "QUEUED",
  "params": {...},
  "priority": 10,
  "position": 3,
  "created_at": "2026-01-18T10:00:00",
  "queued_at": "2026-01-18T10:00:00",
  "started_at": null,
  "finished_at": null
}
```

---

## 4. TaskTemplate APIs (Planned)

### Create Template
```
POST /api/task-templates
```

```json
{
  "name": "daily-horror-story",
  "task_type": "story",
  "params": {
    "genre": "horror",
    "length": 1200,
    "model": "claude"
  },
  "retry_policy": {
    "max_attempts": 3
  }
}
```

---

### Get Templates
```
GET /api/task-templates
GET /api/task-templates/{template_id}
```

---

### Update Template
```
PATCH /api/task-templates/{template_id}
```

- Changes apply **only to future Tasks**
- Existing TaskRuns are unaffected

---

## 4. Schedule APIs

### Create Schedule
```
POST /api/schedules
```

```json
{
  "template_id": "tmpl_123",
  "cron": "0 0 * * *",
  "timezone": "UTC",
  "enabled": true
}
```

---

### Enable / Disable Schedule
```
PATCH /api/schedules/{schedule_id}
```

```json
{
  "enabled": false
}
```

---

## 5. Task APIs (Queue Operations)

### Create Task (Manual Execution)
```
POST /api/tasks
```

```json
{
  "template_id": "tmpl_123",
  "priority": 5
}
```

---

### List Queue
```
GET /api/tasks?status=QUEUED
```

---

### Cancel Task
```
POST /api/tasks/{task_id}/cancel
```

---

## 6. Direct APIs (Immediate Execution)

### Endpoints (Unchanged)
```
POST /story/generate
POST /research/run
```

### Execution Contract

Direct APIs **DO NOT create Tasks**.

Behavior:
1. If a Task is RUNNING, it is **never preempted**
2. Direct execution is **reserved for the next execution slot**
3. Execution order becomes:

```
[Current RUNNING Task]
→ [Direct Execution]
→ [Remaining Queue]
```

This guarantees:
- Immediate responsiveness
- No forced interruption
- Deterministic ordering

---

## 7. TaskRun APIs (Execution History)

### List Runs
```
GET /api/task-runs
```

### Get Run Detail
```
GET /api/task-runs/{run_id}
```

---

### Retry Failed Run (Manual)
```
POST /api/task-runs/{run_id}/retry
```

Rules:
- Creates a **new Task**
- Automatic retries are limited to **3 attempts**
- Further retries require manual invocation

---

## 8. Webhook Contract

### Delivery Semantics
- **At-least-once**
- Max 3 retries
- Discord webhook URLs auto-detected for embed format
- Scheduler task completions enrich payloads with output file metadata

### Scheduler Webhook Payload

On task completion, the scheduler sends a webhook with base fields plus
task-type-specific rich metadata extracted from the generated output files.

**Base fields** (always present):
| Field | Description |
|-------|-------------|
| `task_id` | Task UUID |
| `task_type` | `"story"` or `"research"` |
| `run_id` | TaskRun UUID |
| `status` | TaskRunStatus value |
| `exit_code` | Process exit code |
| `error` | Error message (null on success) |

**Story task** (`task_type: "story"`) — additional fields on success:
| Field | Description |
|-------|-------------|
| `story_id` | Story identifier (timestamp-based) |
| `title` | Generated story title |
| `file_path` | Path to story markdown file |
| `word_count` | Character count |
| `thumbnail_url` | Thumbnail URL (if generated) |
| `thumbnail_provider` | Thumbnail provider name |

**Research task** (`task_type: "research"`) — additional fields on success:
| Field | Description |
|-------|-------------|
| `card_id` | Research card identifier |
| `output_path` | Path to research card JSON |
| `message` | Descriptive completion message |

### Discord Embed Format (Scheduler-specific)

Scheduler task webhooks use a **dedicated Discord embed format** (`build_task_discord_embed_payload`)
distinct from direct API endpoint webhooks (`build_discord_embed_payload`):

- **Title**: `📋 Task Completed: Story` / `📋 Task Failed: Research`
- **Context fields**: Task ID, Type, Status (always present)
- **Rich fields**: Task-type-specific metadata (title, word_count, card_id, etc.)
- **Endpoint**: `/tasks/{task_id}` (not `/story/generate` or `/research/run`)
- **Footer**: Dynamic version from `src.__version__`

---

## 9. Non-Goals

- No UI assumptions
- No distributed workers
- No forced task preemption
- No implicit retries beyond policy

---

## 10. Compatibility

- Legacy `/jobs/*` trigger endpoints have been removed in v2.0.0 (PR #139)
- `POST /tasks` is the sole interface for asynchronous task creation

---

## Related Documents

- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) - 도메인 모델 정의
- [API_IMPACT.md](./API_IMPACT.md) - API 영향 분석
- [DESIGN_GUARDS.md](./DESIGN_GUARDS.md) - 설계 가드레일 및 결정사항
- [TASK_SCHEDULER_DESIGN.md](../technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계 개요
