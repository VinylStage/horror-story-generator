# Job Scheduler API Contract

> **Status:** IMPLEMENTED (Phase 3 API Integration Complete)
> **Document Version:** 2.0.0
> **Application Version:** 1.5.0 (managed by release-please)
> **Last Updated:** 2026-01-18
> **Implementation Branch:** feat/88-scheduler-api-integration

---

## 1. Purpose

This document defines the **external API contract** for the Job Scheduler system.
It is intentionally **UI-agnostic** and serves as the authoritative reference for backend behavior, API semantics, and integration guarantees.

This contract aligns **API responses, internal state, and webhook payloads** to a single, consistent model.

### 1.1 Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Scheduler Control (`/scheduler/*`) | ✅ Implemented | start, stop, status |
| Jobs CRUD (`/jobs`) | ✅ Implemented | POST, GET, PATCH, DELETE |
| Job Runs (`/jobs/{id}/runs`) | ✅ Implemented | 1:1 Job-to-Run relationship |
| Legacy Trigger Endpoints | ✅ Deprecated | Maintained for compatibility |
| JobTemplate APIs | 🔮 Planned | Phase 4+ |
| Schedule (Cron) APIs | 🔮 Planned | Phase 4+ |

---

## 2. Canonical Status Model (Unified)

### 2.1 Job Status (Queue-level)

Used for:
- Queue inspection
- Job control (cancel)
- Scheduler orchestration

| Status | Meaning |
|------|--------|
| QUEUED | Waiting in queue |
| RUNNING | Currently executing |
| CANCELLED | Cancelled before completion |

> These statuses are exposed via API and webhooks.

---

### 2.2 JobRun Status (Execution Result)

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

Scheduler is an **independent system control plane**, NOT a sub-resource of Job.
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
  "current_job_id": "job-123",
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

### 3.2 Jobs CRUD APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs` | Create job (enqueue to scheduler) |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get job details |
| PATCH | `/jobs/{job_id}` | Update job priority (QUEUED only) |
| DELETE | `/jobs/{job_id}` | Cancel job (QUEUED only) |
| GET | `/jobs/{job_id}/runs` | Get job execution history |

**Create Job Request:**
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

**Job Response:**
```json
{
  "job_id": "job-550e8400...",
  "job_type": "story",
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

## 4. JobTemplate APIs (Planned)

### Create Template
```
POST /api/job-templates
```

```json
{
  "name": "daily-horror-story",
  "job_type": "story",
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
GET /api/job-templates
GET /api/job-templates/{template_id}
```

---

### Update Template
```
PATCH /api/job-templates/{template_id}
```

- Changes apply **only to future Jobs**
- Existing JobRuns are unaffected

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

## 5. Job APIs (Queue Operations)

### Create Job (Manual Execution)
```
POST /api/jobs
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
GET /api/jobs?status=QUEUED
```

---

### Cancel Job
```
POST /api/jobs/{job_id}/cancel
```

---

## 6. Direct APIs (Immediate Execution)

### Endpoints (Unchanged)
```
POST /story/generate
POST /research/run
```

### Execution Contract

Direct APIs **DO NOT create Jobs**.

Behavior:
1. If a Job is RUNNING, it is **never preempted**
2. Direct execution is **reserved for the next execution slot**
3. Execution order becomes:

```
[Current RUNNING Job]
→ [Direct Execution]
→ [Remaining Queue]
```

This guarantees:
- Immediate responsiveness
- No forced interruption
- Deterministic ordering

---

## 7. JobRun APIs (Execution History)

### List Runs
```
GET /api/job-runs
```

### Get Run Detail
```
GET /api/job-runs/{run_id}
```

---

### Retry Failed Run (Manual)
```
POST /api/job-runs/{run_id}/retry
```

Rules:
- Creates a **new Job**
- Automatic retries are limited to **3 attempts**
- Further retries require manual invocation

---

## 8. Webhook Contract

### Delivery Semantics
- **At-least-once**
- Max 3 retries
- Identical schema to API responses

### Example Payload
```json
{
  "event": "job.run.completed",
  "run_id": "run_456",
  "job_id": "job_123",
  "status": "COMPLETED",
  "started_at": "...",
  "finished_at": "...",
  "artifacts": {}
}
```

---

## 9. Non-Goals

- No UI assumptions
- No distributed workers
- No forced job preemption
- No implicit retries beyond policy

---

## 10. Compatibility

- Legacy APIs remain functional during migration
- This contract applies to **new scheduler-based execution only**

---
