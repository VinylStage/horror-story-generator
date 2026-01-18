# Job Scheduler API Contract

> Status: DRAFT  
> Version: 0.1.0  
> Last Updated: 2026-01-18  

---

## 1. Purpose

This document defines the **external API contract** for the Job Scheduler system.
It is intentionally **UI-agnostic** and serves as the authoritative reference for backend behavior, API semantics, and integration guarantees.

This contract aligns **API responses, internal state, and webhook payloads** to a single, consistent model.

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

## 3. JobTemplate APIs

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
