# API Reference

**Status:** Active
**Version:** v1.5.0 <!-- x-release-please-version -->
**Base URL:** `http://localhost:8000`
**Swagger UI:** `http://localhost:8000/docs`
**ReDoc:** `http://localhost:8000/redoc`

---

## Overview

The Horror Story Generator API provides:
- **Scheduler Control** - Scheduler-based job queue management (Phase 3)
- **Jobs CRUD** - Scheduler-based job creation, listing, and management
- **Story Generation** - Direct (blocking) and job-based (non-blocking) story creation
- **Research Generation** - Ollama/Gemini-based research card creation
- **Deduplication** - Semantic and canonical similarity checking
- **Job Management** - Background job execution and monitoring (Legacy)

### Design Principle

> **Scheduler = Job Execution Engine** (Phase 3)

The Scheduler controls job execution timing and order. Jobs are enqueued via API and processed by the dispatch loop when running.

> **CLI = Source of Truth** (Legacy)

Legacy trigger endpoints launch CLI commands via subprocess. All business logic resides in the CLI tools (`main.py`, `src.research.executor`).

---

## Quick Start

```bash
# Start server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health

# Generate story directly (blocking)
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Korean apartment horror"}'

# Generate research with Gemini Deep Research
curl -X POST http://localhost:8000/jobs/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic": "Korean apartment horror", "model": "deep-research", "timeout": 300}'

# Check job status
curl http://localhost:8000/jobs/{job_id}
```

---

## Authentication (Optional)

API 인증은 기본적으로 **비활성화**되어 있습니다. 외부 노출이 필요한 경우 활성화할 수 있습니다.

### 환경 변수

| Variable | Default | Description |
|----------|---------|-------------|
| `API_AUTH_ENABLED` | `false` | `true`로 설정 시 인증 활성화 |
| `API_KEY` | - | 인증에 사용할 API 키 |

### 설정 방법

```bash
# .env 파일
API_AUTH_ENABLED=true
API_KEY=your-secure-api-key-here
```

### 사용 방법

인증이 활성화된 경우, 모든 요청에 `X-API-Key` 헤더를 포함해야 합니다:

```bash
# 인증된 요청
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{"topic": "Korean apartment horror"}'
```

### 인증 제외 엔드포인트

다음 엔드포인트는 인증 여부와 관계없이 항상 접근 가능합니다:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | 헬스 체크 |
| `GET /resource/status` | Ollama 리소스 상태 |

### 에러 응답

인증 실패 시 `401 Unauthorized` 응답:

```json
{"detail": "Missing API key. Provide X-API-Key header."}
```

```json
{"detail": "Invalid API key"}
```

---

## Scheduler API (Phase 3)

스케줄러 기반 실행 모델 API입니다. Job은 큐에 등록되고, Scheduler가 실행 시점을 제어합니다.

### Architecture Overview

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   POST /jobs    │──────▶│    Job Queue    │──────▶│   Dispatcher    │
│  (Create Job)   │       │   (SQLite DB)   │       │  (Background)   │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                              │
                          ┌─────────────────┐                 │
                          │  CLI Executor   │◀────────────────┘
                          │  (Subprocess)   │
                          └─────────────────┘
```

### 핵심 개념

| 개념 | 설명 |
|------|------|
| **Job** | 수행할 작업의 정의 (QUEUED → RUNNING → CANCELLED) |
| **JobRun** | Job의 단일 실행 시도 (COMPLETED/FAILED/SKIPPED) |
| **Scheduler** | Job을 JobRun으로 변환하는 백그라운드 실행 엔진 |

### Scheduler Control Endpoints

#### POST /scheduler/start

스케줄러 디스패치 루프를 시작합니다.

**특징:**
- Idempotent: 이미 실행 중이면 성공 메시지 반환
- 서버 부팅 시 자동 시작되지 않음 (명시적 호출 필요)
- crash recovery 실행 옵션 지원

**Request Body:**

```json
{
  "run_recovery": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_recovery` | boolean | true | 시작 시 crash recovery 실행 여부 |

**Response:** `200 OK`

```json
{
  "success": true,
  "message": "Scheduler started successfully",
  "recovery_stats": {
    "recovered_jobs": 2,
    "failed_jobs": 0
  }
}
```

---

#### POST /scheduler/stop

스케줄러 디스패치 루프를 gracefully 중지합니다.

**특징:**
- 현재 실행 중인 Job 완료 대기 (preemption 없음)
- Idempotent: 이미 중지되어 있으면 성공 메시지 반환

**Request Body:**

```json
{
  "timeout": 30.0
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout` | float | 30.0 | 현재 Job 완료 대기 최대 시간 (초, 1-300) |

**Response:** `200 OK`

```json
{
  "success": true,
  "message": "Scheduler stopped successfully"
}
```

---

#### GET /scheduler/status

스케줄러 상태 및 누적 통계를 조회합니다.

**Response:** `200 OK`

```json
{
  "scheduler_running": true,
  "current_job_id": "job-550e8400-e29b-41d4-a716-446655440000",
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

| Field | Type | Description |
|-------|------|-------------|
| `scheduler_running` | boolean | 디스패치 루프 실행 여부 |
| `current_job_id` | string | 현재 실행 중인 Job ID (없으면 null) |
| `queue_length` | integer | QUEUED 상태 Job 수 |
| `cumulative_stats` | object | 누적 실행 통계 |
| `has_active_reservation` | boolean | Direct API 예약 활성화 여부 |

### Jobs CRUD Endpoints (Scheduler-based)

#### POST /jobs

새로운 Job을 생성하고 스케줄러 큐에 등록합니다.

**Request Body:**

```json
{
  "type": "story",
  "params": {
    "max_stories": 1,
    "enable_dedup": true,
    "model": "ollama:qwen3:30b"
  },
  "priority": 10
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | **Yes** | - | Job 타입: `"story"` 또는 `"research"` |
| `params` | object | No | {} | Job 파라미터 (타입별 상이) |
| `priority` | integer | No | 0 | 우선순위 (0-100, 높을수록 먼저 실행) |

**Story Job params:**

| Field | Type | Description |
|-------|------|-------------|
| `max_stories` | integer | 생성할 최대 스토리 수 |
| `duration_seconds` | integer | 실행 제한 시간 |
| `enable_dedup` | boolean | 중복 검사 활성화 |
| `model` | string | 모델 선택 |

**Research Job params:**

| Field | Type | Description |
|-------|------|-------------|
| `topic` | string | **필수** - 연구 주제 |
| `tags` | array | 분류 태그 |
| `model` | string | 모델 선택 |
| `timeout` | integer | 타임아웃 (초) |

**Response:** `201 Created`

```json
{
  "job_id": "job-550e8400-e29b-41d4-a716-446655440000",
  "job_type": "story",
  "status": "QUEUED",
  "params": {
    "max_stories": 1,
    "enable_dedup": true
  },
  "priority": 10,
  "position": 3,
  "template_id": null,
  "group_id": null,
  "retry_of": null,
  "created_at": "2026-01-18T10:00:00",
  "queued_at": "2026-01-18T10:00:00",
  "started_at": null,
  "finished_at": null
}
```

---

#### GET /jobs

스케줄러의 모든 Job 목록을 조회합니다.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | 최대 결과 수 (1-200) |

**Response:** `200 OK`

```json
{
  "jobs": [
    {
      "job_id": "job-1",
      "job_type": "story",
      "status": "RUNNING",
      "params": {...},
      "priority": 10,
      "position": 0,
      "created_at": "2026-01-18T10:00:00",
      "queued_at": "2026-01-18T10:00:00",
      "started_at": "2026-01-18T10:01:00",
      "finished_at": null
    }
  ],
  "total": 5,
  "queued_count": 3,
  "running_count": 1
}
```

---

#### GET /jobs/{job_id}

특정 Job의 상세 정보를 조회합니다.

**Response:** `200 OK`

```json
{
  "job_id": "job-550e8400-e29b-41d4-a716-446655440000",
  "job_type": "research",
  "status": "QUEUED",
  "params": {
    "topic": "Korean apartment horror",
    "tags": ["urban", "isolation"]
  },
  "priority": 5,
  "position": 2,
  "template_id": null,
  "group_id": null,
  "retry_of": null,
  "created_at": "2026-01-18T10:00:00",
  "queued_at": "2026-01-18T10:00:00",
  "started_at": null,
  "finished_at": null
}
```

**Error Response:** `404 Not Found`

```json
{"detail": "Job not found: nonexistent-id"}
```

---

#### PATCH /jobs/{job_id}

Job의 우선순위를 업데이트합니다 (QUEUED 상태만 가능).

**Request Body:**

```json
{
  "priority": 50
}
```

| Field | Type | Description |
|-------|------|-------------|
| `priority` | integer | 새로운 우선순위 (0-100) |

**Response:** `200 OK`

```json
{
  "job_id": "job-550e8400...",
  "status": "QUEUED",
  "priority": 50,
  ...
}
```

**Error Response:** `400 Bad Request`

```json
{"detail": "Cannot update job: only QUEUED jobs can be updated"}
```

---

#### DELETE /jobs/{job_id}

Job을 취소/삭제합니다 (QUEUED 상태만 가능).

**Response:** `200 OK`

```json
{
  "job_id": "job-550e8400...",
  "success": true,
  "message": "Job cancelled successfully (status: CANCELLED)"
}
```

**Error Response:** `400 Bad Request`

```json
{"detail": "Cannot cancel job: only QUEUED jobs can be cancelled"}
```

---

#### GET /jobs/{job_id}/runs

Job의 실행 이력 (JobRun)을 조회합니다.

**특징:**
- 각 Job당 최대 1개의 JobRun (1:1 관계)
- 재시도 시 새로운 Job이 생성됨 (retry_of 필드 참조)

**Response:** `200 OK`

```json
{
  "runs": [
    {
      "run_id": "run-123",
      "job_id": "job-550e8400...",
      "status": "COMPLETED",
      "params_snapshot": {...},
      "template_id": null,
      "started_at": "2026-01-18T10:01:00",
      "finished_at": "2026-01-18T10:05:30",
      "exit_code": 0,
      "error": null,
      "artifacts": ["data/novel/horror_story_20260118.md"],
      "log_path": "logs/job-550e8400.log"
    }
  ],
  "total": 1
}
```

### Job Status Values (Scheduler)

| Status | Entity | Description |
|--------|--------|-------------|
| `QUEUED` | Job | 큐에서 대기 중 |
| `RUNNING` | Job | 현재 실행 중 |
| `CANCELLED` | Job | 사용자에 의해 취소됨 |
| `COMPLETED` | JobRun | 실행 성공 |
| `FAILED` | JobRun | 실행 실패 |
| `SKIPPED` | JobRun | 의도적으로 건너뜀 |

---

## Model Selection Reference

### Story Generation Models

| Model | Value | Description |
|-------|-------|-------------|
| Claude Sonnet (default) | `null` 또는 미지정 | 기본 모델. 고품질 한국어 호러 생성 |
| Claude Sonnet 4.5 | `"claude-sonnet-4-5-20250929"` | 최신 Sonnet 모델 명시적 지정 |
| Claude Opus 4.5 | `"claude-opus-4-5-20251101"` | 고성능 Opus 모델 |
| Ollama (Local) | `"ollama:qwen3:30b"` | 로컬 Ollama 모델. 형식: `ollama:{model_name}` |

**예시:**
```json
// Claude 기본 (권장)
{"topic": "아파트 호러", "model": null}

// Ollama 로컬 모델
{"topic": "아파트 호러", "model": "ollama:qwen3:30b"}
```

### Research Generation Models

| Model | Value | Description | Timeout |
|-------|-------|-------------|---------|
| Ollama qwen3:30b (default) | `null` 또는 `"qwen3:30b"` | 기본 로컬 모델 | 60s |
| Ollama (other) | `"qwen:14b"`, `"llama3"` 등 | 다른 Ollama 모델 | 60s |
| Gemini Standard | `"gemini"` | Google Gemini API | 120s |
| Gemini Deep Research | `"deep-research"` | Gemini Deep Research Agent (고품질) | 300-600s |

**환경 변수 요구사항:**
- Gemini 모델 사용시: `GEMINI_ENABLED=true`, `GEMINI_API_KEY` 필요

**예시:**
```json
// Ollama 기본
{"topic": "Korean apartment horror", "model": "qwen3:30b"}

// Gemini Deep Research (권장 - 고품질)
{"topic": "Korean apartment horror", "model": "deep-research", "timeout": 300}

// Gemini 표준
{"topic": "Korean apartment horror", "model": "gemini", "timeout": 120}
```

---

## Endpoints

### System Endpoints

#### GET /health

서버 상태 확인.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "version": "1.5.0"
}
```

---

#### GET /resource/status

Ollama 리소스 매니저 상태 확인.

**Response:** `200 OK`

```json
{
  "active_models": ["qwen3:30b"],
  "idle_timeout_seconds": 300,
  "last_cleanup": "2026-01-13T12:00:00"
}
```

---

### Story Endpoints (v1.2.0+)

Direct story generation and registry access. These endpoints execute synchronously.

#### POST /story/generate

Generate a story directly (blocking).

**v1.4.3:** Supports `webhook_url` for fire-and-forget completion notification.

**Request Body:**

```json
{
  "topic": "Korean apartment horror",
  "auto_research": true,
  "model": "ollama:qwen3:30b",
  "research_model": null,
  "save_output": true,
  "webhook_url": "https://your-server.com/callback"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `topic` | string | No | null | Story topic. If provided, searches for matching research card |
| `auto_research` | boolean | No | true | Auto-generate research if no matching card found |
| `model` | string | No | null | Story model. Format: `ollama:qwen3:30b` or Claude model name |
| `research_model` | string | No | null | Research model for auto-research |
| `save_output` | boolean | No | true | Save story to file |
| `webhook_url` | string | No | null | Webhook URL for completion notification (v1.4.3) |

**Response:** `200 OK`

```json
{
  "success": true,
  "story_id": "20260113_120000",
  "story": "# The Floor Above\n\n...",
  "title": "The Floor Above",
  "file_path": "./data/novel/horror_story_20260113_120000.md",
  "word_count": 3500,
  "metadata": {
    "model": "claude-sonnet-4-5-20250929",
    "provider": "anthropic",
    "topic": "Korean apartment horror",
    "research_used": ["RC-20260113-084040"],
    "research_injection_mode": "topic_based"
  },
  "webhook_triggered": true
}
```

---

#### GET /story/list

List stories from the registry.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results (default: 50, max: 500) |
| `offset` | integer | Pagination offset (default: 0) |
| `accepted_only` | boolean | Only return accepted stories |

**Response:** `200 OK`

```json
{
  "stories": [
    {
      "story_id": "20260113_120000",
      "title": "The Floor Above",
      "template_id": "T-DOM-001",
      "template_name": "Domestic Intrusion",
      "created_at": "2026-01-13T12:00:00",
      "accepted": true,
      "decision_reason": "accepted",
      "story_signature": "abc123...",
      "research_used": ["RC-20260113-084040"]
    }
  ],
  "total": 1,
  "message": "Found 1 stories"
}
```

---

#### GET /story/{story_id}

Get detailed information about a specific story.

**Response:** `200 OK`

```json
{
  "story_id": "20260113_120000",
  "title": "The Floor Above",
  "template_id": "T-DOM-001",
  "template_name": "Domestic Intrusion",
  "semantic_summary": "A horror story about...",
  "created_at": "2026-01-13T12:00:00",
  "accepted": true,
  "decision_reason": "accepted",
  "story_signature": "abc123...",
  "canonical_core": {
    "setting_archetype": "domestic_space",
    "primary_fear": "loss_of_autonomy",
    "antagonist_archetype": "collective",
    "threat_mechanism": "erosion"
  },
  "research_used": ["RC-20260113-084040"]
}
```

---

### Job Trigger Endpoints (Legacy - Deprecated)

> **⚠️ Deprecated:** Phase 3부터 `POST /jobs` 사용을 권장합니다.
> Legacy trigger 엔드포인트는 하위 호환성을 위해 유지되지만, 신규 클라이언트는 Scheduler 기반 API를 사용해야 합니다.

#### POST /jobs/story/trigger [DEPRECATED]

Trigger a story generation job.

**Request Body:**

```json
{
  "max_stories": 5,
  "duration_seconds": 300,
  "interval_seconds": 30,
  "enable_dedup": true,
  "db_path": "/path/to/stories.db",
  "load_history": true,
  "model": "ollama:llama3",
  "webhook_url": "https://your-server.com/callback",
  "webhook_events": ["succeeded", "failed", "skipped"]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_stories` | integer | No | 1 | Maximum stories to generate |
| `duration_seconds` | integer | No | null | Time limit in seconds |
| `interval_seconds` | integer | No | 0 | Wait between generations |
| `enable_dedup` | boolean | No | false | Enable deduplication |
| `db_path` | string | No | null | SQLite database path |
| `load_history` | boolean | No | false | Load existing stories |
| `model` | string | No | null | Model selection. Format: `ollama:llama3`, `ollama:qwen`, or Claude model name |
| `webhook_url` | string | No | null | URL for webhook notification on job completion (v1.3.0) |
| `webhook_events` | array | No | ["succeeded", "failed", "skipped"] | Events that trigger webhook (v1.3.0) |

**Response:** `202 Accepted`

```json
{
  "job_id": "abc-123-def",
  "type": "story_generation",
  "status": "running",
  "message": "Story generation job started with PID 12345"
}
```

---

#### POST /jobs/research/trigger [DEPRECATED]

Trigger a research generation job.

**Request Body:**

```json
{
  "topic": "Korean apartment horror",
  "tags": ["urban", "isolation"],
  "model": "qwen3:30b",
  "timeout": 120,
  "webhook_url": "https://your-server.com/callback",
  "webhook_events": ["succeeded", "failed", "skipped"]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `topic` | string | **Yes** | - | Research topic |
| `tags` | array | No | [] | Classification tags |
| `model` | string | No | "qwen3:30b" | Model name. Ollama: `qwen3:30b`. Gemini: `gemini` or `deep-research` (Deep Research Agent, requires GEMINI_ENABLED=true) |
| `timeout` | integer | No | 60 | Generation timeout (deep-research supports up to 600s) |
| `webhook_url` | string | No | null | URL for webhook notification on job completion (v1.3.0) |
| `webhook_events` | array | No | ["succeeded", "failed", "skipped"] | Events that trigger webhook (v1.3.0) |

**Response:** `202 Accepted`

```json
{
  "job_id": "xyz-789-ghi",
  "type": "research",
  "status": "running",
  "message": "Research job started with PID 54321"
}
```

---

### Job Management Endpoints

#### GET /jobs/{job_id}

Get status of a specific job.

**Response:** `200 OK`

```json
{
  "job_id": "abc-123-def",
  "type": "story_generation",
  "status": "succeeded",
  "params": {
    "max_stories": 5,
    "enable_dedup": true
  },
  "pid": 12345,
  "log_path": "logs/story_abc-123-def.log",
  "artifacts": [
    "data/stories/story_20260112_143052.json"
  ],
  "created_at": "2026-01-12T14:30:00",
  "started_at": "2026-01-12T14:30:01",
  "finished_at": "2026-01-12T14:35:00",
  "exit_code": 0,
  "error": null,
  "webhook_url": "https://your-server.com/callback",
  "webhook_events": ["succeeded", "failed", "skipped"],
  "webhook_sent": true,
  "webhook_error": null
}
```

**Error Response:** `404 Not Found`

```json
{
  "detail": "Job not found: nonexistent-id"
}
```

---

#### GET /jobs

List all jobs with optional filtering.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (queued, running, succeeded, failed, cancelled, skipped) |
| `type` | string | Filter by type (story_generation, research) |
| `limit` | integer | Max results (default: 50, max: 200) |

**Response:** `200 OK`

```json
{
  "jobs": [
    {
      "job_id": "abc-123-def",
      "type": "story_generation",
      "status": "running",
      ...
    }
  ],
  "total": 1,
  "message": "Found 1 jobs"
}
```

---

#### POST /jobs/{job_id}/cancel

Cancel a running job by sending SIGTERM.

**Response:** `200 OK`

```json
{
  "job_id": "abc-123-def",
  "success": true,
  "message": "Sent SIGTERM to PID 12345",
  "error": null
}
```

**Error Response:**

```json
{
  "job_id": "abc-123-def",
  "success": false,
  "message": null,
  "error": "Job not running (status: succeeded)"
}
```

---

### Monitoring Endpoints

#### POST /jobs/monitor

Monitor all running jobs and update their status.

Checks if processes are still running, collects artifacts, and updates job status to succeeded/failed.

**Response:** `200 OK`

```json
{
  "monitored_count": 2,
  "results": [
    {
      "job_id": "abc-123-def",
      "status": "succeeded",
      "pid": null,
      "artifacts": ["data/stories/story_1.json"],
      "error": null,
      "message": null
    },
    {
      "job_id": "xyz-789-ghi",
      "status": "running",
      "pid": 54321,
      "artifacts": [],
      "error": null,
      "message": "Process still running"
    }
  ]
}
```

---

#### POST /jobs/{job_id}/monitor

Monitor a single job and update its status.

**Response:** `200 OK`

```json
{
  "job_id": "abc-123-def",
  "status": "succeeded",
  "pid": null,
  "artifacts": ["data/stories/story_1.json"],
  "error": null,
  "message": null
}
```

---

#### POST /jobs/{job_id}/dedup_check

Check deduplication signal for a research job's artifact.

Only available for research jobs with completed artifacts.

**Response:** `200 OK`

```json
{
  "job_id": "xyz-789-ghi",
  "has_artifact": true,
  "artifact_path": "data/research/RC-20260112-143052.json",
  "signal": "LOW",
  "similarity_score": 0.15,
  "message": null
}
```

**No Artifact Response:**

```json
{
  "job_id": "xyz-789-ghi",
  "has_artifact": false,
  "artifact_path": null,
  "signal": null,
  "similarity_score": null,
  "message": "Job has no artifacts yet (still running or failed)"
}
```

---

### Research Endpoints

연구 카드 생성 및 관리. Ollama LLM을 통해 동기적으로 실행됩니다.

#### POST /research/run

연구 카드 생성 (blocking).

**v1.4.3:** Supports `webhook_url` for fire-and-forget completion notification.

**Request Body:**

```json
{
  "topic": "Korean apartment horror",
  "tags": ["urban", "isolation"],
  "model": "deep-research",
  "timeout": 300,
  "webhook_url": "https://your-server.com/callback"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `topic` | string | **Yes** | - | 연구 주제 |
| `tags` | array | No | [] | 분류 태그 |
| `model` | string | No | "qwen3:30b" | 모델 선택 (위 Model Selection Reference 참조) |
| `timeout` | integer | No | 60 | 타임아웃 (초). deep-research는 300-600 권장 |
| `webhook_url` | string | No | null | Webhook URL for completion notification (v1.4.3) |

**Response:** `200 OK`

```json
{
  "card_id": "RC-20260113-120000",
  "status": "completed",
  "message": "Research card generated successfully",
  "output_path": "data/research/RC-20260113-120000.json",
  "webhook_triggered": true
}
```

---

#### POST /research/validate

기존 연구 카드 품질 검증.

**Request Body:**

```json
{
  "card_id": "RC-20260113-120000"
}
```

**Response:** `200 OK`

```json
{
  "card_id": "RC-20260113-120000",
  "is_valid": true,
  "quality_score": "good",
  "message": "Card passes all validation checks"
}
```

| quality_score | Description |
|---------------|-------------|
| `good` | 모든 필수 필드 존재, 품질 양호 |
| `partial` | 일부 필드 누락 또는 품질 미흡 |
| `incomplete` | 주요 필드 누락 |

---

#### GET /research/list

연구 카드 목록 조회.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | 최대 결과 수 (1-100) |
| `offset` | integer | 0 | 페이지네이션 오프셋 |
| `quality` | string | null | 품질 필터 (good, partial, incomplete) |

**Response:** `200 OK`

```json
{
  "cards": [
    {
      "card_id": "RC-20260113-120000",
      "title": "Korean Apartment Horror Research",
      "topic": "Korean apartment horror",
      "quality_score": "good",
      "created_at": "2026-01-13T12:00:00"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0,
  "message": "Found 1 cards"
}
```

---

#### POST /research/dedup

연구 카드 시맨틱 중복 검사 (FAISS 임베딩 기반).

**Request Body:**

```json
{
  "card_id": "RC-20260113-120000"
}
```

**Response:** `200 OK`

```json
{
  "card_id": "RC-20260113-120000",
  "signal": "LOW",
  "similarity_score": 0.45,
  "nearest_card_id": "RC-20260112-090000",
  "similar_cards": [
    {
      "card_id": "RC-20260112-090000",
      "similarity_score": 0.45,
      "title": "Urban Horror Research"
    }
  ],
  "index_size": 52,
  "message": "Card is sufficiently unique"
}
```

---

### Dedup Endpoints

스토리 중복 검사. Canonical dimension 기반 유사도 평가.

#### POST /dedup/evaluate

스토리 중복 신호 평가.

**Request Body:**

```json
{
  "template_id": "T-DOM-001",
  "canonical_core": {
    "setting": "domestic_space",
    "primary_fear": "loss_of_autonomy",
    "antagonist": "collective",
    "mechanism": "erosion",
    "twist": "acceptance"
  },
  "title": "The Floor Above"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template_id` | string | No | 사용 중인 템플릿 ID |
| `canonical_core` | object | No | Canonical dimension 값 |
| `title` | string | No | 스토리 제목 |

**Response:** `200 OK`

```json
{
  "signal": "LOW",
  "similarity_score": 0.15,
  "similar_stories": [
    {
      "story_id": "20260112_143052",
      "template_id": "T-DOM-001",
      "similarity_score": 0.15,
      "matched_dimensions": ["setting"]
    }
  ],
  "message": "Story is sufficiently unique"
}
```

---

## Data Schemas

### Job Status Values

| Status | Description |
|--------|-------------|
| `queued` | Job created, not yet started |
| `running` | Process is executing |
| `succeeded` | Process completed with no errors |
| `failed` | Process exited with errors |
| `cancelled` | User cancelled the job |
| `skipped` | Expected skip (e.g., duplicate detection) - NOT a failure (v1.3.0) |

### Job Types

| Type | Description |
|------|-------------|
| `story_generation` | Story generation via `main.py` |
| `research` | Research generation via `src.research.executor` |

### Dedup Signal Values

**Story Dedup (Canonical Matching):**

| Signal | Score Range | Meaning |
|--------|-------------|---------|
| `LOW` | < 0.3 | Sufficiently unique |
| `MEDIUM` | 0.3 - 0.6 | Some overlap |
| `HIGH` | > 0.6 | Significant similarity |

**Research Dedup (Semantic Embedding via FAISS):**

| Signal | Score Range | Meaning |
|--------|-------------|---------|
| `LOW` | < 0.70 | Unique content |
| `MEDIUM` | 0.70 - 0.85 | Some overlap |
| `HIGH` | ≥ 0.85 | High similarity (potential duplicate) |

Research embeddings use `nomic-embed-text` model via Ollama (768 dimensions).

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 202 | Accepted (job triggered) |
| 404 | Job not found |
| 422 | Validation error (invalid parameters) |
| 500 | Internal server error |

### Error Response Format

```json
{
  "detail": "Error message describing the problem"
}
```

---

## Workflow Integration

### Polling Pattern

Recommended pattern for n8n or similar workflow tools:

```
1. POST /jobs/*/trigger → Get job_id
2. Wait 30 seconds
3. GET /jobs/{job_id} → Check status
4. If status == "running": Go to step 2
5. If status == "succeeded": Process artifacts
6. If status == "failed": Handle error
```

### Webhook Integration (v1.3.0)

Jobs can be configured to send HTTP POST notifications on completion:

**Configuration (in trigger request):**

```json
{
  "webhook_url": "https://your-server.com/callback",
  "webhook_events": ["succeeded", "failed", "skipped"]
}
```

**Webhook Payload:**

```json
{
  "event": "succeeded",
  "job_id": "abc-123-def",
  "type": "story_generation",
  "status": "succeeded",
  "params": {...},
  "created_at": "2026-01-13T12:00:00",
  "started_at": "2026-01-13T12:00:01",
  "finished_at": "2026-01-13T12:05:00",
  "exit_code": 0,
  "error": null,
  "artifacts": ["data/stories/story_1.json"],
  "timestamp": "2026-01-13T12:05:01"
}
```

**Webhook Headers:**

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `User-Agent` | `HorrorStoryGenerator/1.3` |
| `X-Job-ID` | Job identifier |
| `X-Job-Event` | Event type (succeeded, failed, skipped) |

**Retry Logic:**

- Max 3 attempts with exponential backoff
- Base delay: 1 second, max delay: 10 seconds
- Timeout: 30 seconds per request

**Webhook Events:**

| Event | Description |
|-------|-------------|
| `succeeded` | Job completed successfully |
| `failed` | Job failed with error |
| `skipped` | Job skipped (duplicate detection) |

Note: `cancelled` events do not trigger webhooks by default.

### Sync Endpoint Webhooks (v1.4.3)

The sync endpoints (`/research/run`, `/story/generate`) support fire-and-forget webhooks.

**Configuration (in request body):**

```json
{
  "topic": "Korean apartment horror",
  "webhook_url": "https://your-server.com/callback"
}
```

**Fire-and-Forget Behavior:**

- The HTTP response is returned immediately after the operation completes
- The webhook is sent asynchronously in a background thread
- Webhook failures do not affect the API response

**Sync Webhook Payload:**

```json
{
  "event": "completed",
  "endpoint": "/research/run",
  "status": "success",
  "result": {
    "card_id": "RC-20260113-120000",
    "output_path": "data/research/RC-20260113-120000.json"
  },
  "timestamp": "2026-01-13T12:05:01"
}
```

**Error Payload:**

```json
{
  "event": "error",
  "endpoint": "/story/generate",
  "status": "error",
  "result": {
    "error": "Generation failed"
  },
  "timestamp": "2026-01-13T12:05:01"
}
```

**Sync Webhook Headers:**

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `User-Agent` | `HorrorStoryGenerator/1.4` |
| `X-Webhook-Event` | Event type (completed, error) |
| `X-Webhook-Endpoint` | Source endpoint path |

**Retry Logic:** Same as job webhooks (3 attempts, exponential backoff).

---

## CLI Command Mapping

The API triggers these CLI commands:

### Story Generation

```bash
python main.py \
  --max-stories {max_stories} \
  --duration-seconds {duration_seconds} \
  --interval-seconds {interval_seconds} \
  --enable-dedup \
  --db-path {db_path} \
  --load-history \
  --model {model}
```

| Parameter | Description |
|-----------|-------------|
| `--model` | Model selection. Default: Claude Sonnet. Format: `ollama:llama3`, `ollama:qwen`, or Claude model name |

### Research Generation

```bash
python -m src.research.executor run {topic} \
  --tags {tag1} {tag2} \
  --model {model} \
  --timeout {timeout}
```

| Parameter | Description |
|-----------|-------------|
| `--model` | Model selection. Default: Ollama qwen3:30b. Formats: `qwen:14b` (Ollama), `gemini` (standard), `deep-research` (Deep Research Agent). Gemini requires GEMINI_ENABLED=true |

---

## Rate Limiting

Currently, no rate limiting is implemented. For production use, consider:

- Adding API key authentication
- Implementing request rate limits
- Limiting concurrent jobs per type

---

## Assumptions and Limitations

### Assumptions

- Single instance deployment
- Local file system access for logs and artifacts
- Subprocess execution capability

### Limitations

- No authentication (add for production)
- No WebSocket support for real-time updates
- Job history not automatically cleaned up
- No distributed job execution

---

**Note:** All documentation reflects the current `src/` package structure (Post STEP 4-B).
