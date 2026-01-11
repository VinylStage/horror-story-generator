# Trigger-based API Layer

## 개요 (Overview)

Trigger API는 비동기 작업 실행을 위한 API 레이어입니다. CLI를 진실의 근원(source of truth)으로 유지하면서, API는 subprocess를 통해 CLI 명령을 실행합니다.

### 핵심 원칙
- **CLI = Source of Truth**: 모든 핵심 로직은 CLI에 존재
- **Non-blocking**: API는 작업을 트리거하고 즉시 반환
- **파일 기반 저장소**: jobs/ 디렉토리에 JSON 파일로 저장
- **PID 추적**: 프로세스 모니터링을 위한 PID 기록

## 엔드포인트 (Endpoints)

### Job Trigger 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /jobs/story/trigger | 스토리 생성 작업 트리거 |
| POST | /jobs/research/trigger | 리서치 생성 작업 트리거 |

### Job 관리 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /jobs/{job_id} | 단일 작업 상태 조회 |
| GET | /jobs | 전체 작업 목록 조회 (필터링 지원) |
| POST | /jobs/{job_id}/cancel | 실행 중인 작업 취소 (SIGTERM) |
| POST | /jobs/monitor | 모든 실행 중 작업 모니터링 |
| POST | /jobs/{job_id}/monitor | 단일 작업 모니터링 |
| POST | /jobs/{job_id}/dedup_check | 리서치 작업 중복 검사 |

## 시퀀스 다이어그램 (Sequence Diagram)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │   API    │     │ Job Store│     │   CLI    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ POST /trigger  │                │                │
     │───────────────>│                │                │
     │                │ create job     │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │ subprocess     │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │ 202 Accepted   │                │                │
     │<───────────────│                │                │
     │ {job_id, pid}  │                │                │
     │                │                │                │
     ├────── polling loop ────────────────────────────>│
     │                │                │                │
     │ GET /jobs/{id} │                │                │
     │───────────────>│                │                │
     │                │ load job       │                │
     │                │<───────────────│                │
     │                │                │                │
     │ status:running │                │                │
     │<───────────────│                │                │
     │                │                │                │
     │     ...        │                │   (process)    │
     │                │                │       │        │
     │ POST /monitor  │                │       │        │
     │───────────────>│                │       ▼        │
     │                │ check PID      │   (exit)       │
     │                │───────────────────────────────>│
     │                │ collect artifacts              │
     │                │ update status  │                │
     │                │───────────────>│                │
     │                │                │                │
     │ status:done    │                │                │
     │<───────────────│                │                │
     │ {artifacts}    │                │                │
     └────────────────┴────────────────┴────────────────┘
```

## Job 스키마 (Job Schema)

```json
{
  "job_id": "uuid4",
  "type": "story_generation | research",
  "status": "queued | running | succeeded | failed | cancelled",
  "params": { ... },
  "pid": 12345,
  "log_path": "logs/story_uuid.log",
  "artifacts": ["/path/to/output.json"],
  "created_at": "2026-01-11T12:00:00",
  "started_at": "2026-01-11T12:00:01",
  "finished_at": "2026-01-11T12:05:00",
  "exit_code": 0,
  "error": null
}
```

## 사용 예시 (Usage Examples)

### 스토리 생성 트리거

```bash
# 작업 트리거
curl -X POST http://localhost:8000/jobs/story/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "max_stories": 5,
    "enable_dedup": true,
    "interval_seconds": 30
  }'

# 응답
{
  "job_id": "abc-123-def",
  "type": "story_generation",
  "status": "running",
  "message": "Story generation job started with PID 12345"
}
```

### 리서치 생성 트리거

```bash
curl -X POST http://localhost:8000/jobs/research/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Korean apartment horror",
    "tags": ["urban", "isolation"]
  }'
```

### 작업 상태 확인

```bash
# 단일 작업 조회
curl http://localhost:8000/jobs/abc-123-def

# 전체 목록 (필터링)
curl "http://localhost:8000/jobs?status=running&type=research"
```

### 작업 모니터링

```bash
# 모든 실행 중 작업 모니터링 (상태 업데이트)
curl -X POST http://localhost:8000/jobs/monitor

# 단일 작업 모니터링
curl -X POST http://localhost:8000/jobs/abc-123-def/monitor
```

### 작업 취소

```bash
curl -X POST http://localhost:8000/jobs/abc-123-def/cancel
```

### 중복 검사 (리서치 작업)

```bash
curl -X POST http://localhost:8000/jobs/abc-123-def/dedup_check

# 응답
{
  "job_id": "abc-123-def",
  "has_artifact": true,
  "artifact_path": "/path/to/RC-001.json",
  "signal": "LOW",
  "similarity_score": 0.15
}
```

## 에러 처리 (Error Handling)

### 작업 실패 감지

작업 실패는 다음 방법으로 감지됩니다:

1. **프로세스 종료 감지**: `os.kill(pid, 0)` 시그널로 프로세스 생존 확인
2. **로그 파일 분석**: Traceback, Error, Exception 등 에러 패턴 검색
3. **아티팩트 수집**: 작업 시작 이후 생성된 파일 자동 수집

### 에러 상태 코드

| 상태 | 설명 |
|------|------|
| succeeded | 프로세스 종료 + 에러 미발견 |
| failed | 프로세스 종료 + 로그에 에러 감지 |
| cancelled | 사용자에 의해 취소됨 (SIGTERM) |

### 에러 복구

실패한 작업은 다음과 같이 처리됩니다:

- 로그 파일에서 에러 메시지 추출 (마지막 500자)
- exit_code 기록 (가능한 경우)
- artifacts는 실패한 작업에서도 수집됨

## 미래 작업 (Future Work)

### Webhook 통합

```yaml
# 예정된 기능
webhooks:
  on_complete:
    url: "https://your-server.com/hook"
    events: ["succeeded", "failed"]
    payload:
      job_id: "{{job.job_id}}"
      status: "{{job.status}}"
      artifacts: "{{job.artifacts}}"
```

### n8n 통합

n8n 워크플로우와의 통합을 위한 권장 패턴:

1. **Trigger Node**: HTTP Request로 /jobs/*/trigger 호출
2. **Wait Node**: 지정된 간격으로 대기 (30초 권장)
3. **Poll Node**: GET /jobs/{job_id}로 상태 확인
4. **Branch Node**: status에 따른 분기 처리

```
[Trigger] → [Wait 30s] → [Poll Status] → [Check Status]
                              ↓                ↓
                         [running?]      [succeeded/failed]
                              ↓                ↓
                         [Loop Back]     [Process Result]
```

### 배치 작업

향후 지원 예정:
- POST /jobs/batch/trigger - 여러 작업 동시 트리거
- GET /jobs/batch/{batch_id} - 배치 상태 조회

## 파일 구조 (File Structure)

```
horror-story-generator/
├── job_manager.py        # 작업 CRUD 모듈
├── job_monitor.py        # PID 모니터링 모듈
├── jobs/                 # 작업 JSON 저장소
│   └── {job_id}.json
├── logs/                 # 작업 로그 파일
│   ├── story_{job_id}.log
│   └── research_{job_id}.log
└── research_api/
    ├── routers/
    │   └── jobs.py       # API 엔드포인트
    └── schemas/
        └── jobs.py       # Pydantic 스키마
```

## 관련 문서

- [PHASE_B_PLUS.md](PHASE_B_PLUS.md) - Phase B+ 전체 개요
- [system_architecture.md](system_architecture.md) - 시스템 아키텍처
- [n8n_environment_setup.md](n8n_environment_setup.md) - n8n 환경 설정
