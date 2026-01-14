# n8n API Integration Guide

**Version:** 1.0
**Last Updated:** 2026-01-15

---

## Overview

이 가이드는 n8n을 사용하여 Horror Story Generator API와 통합하는 방법을 설명합니다.

---

## Prerequisites

1. **Horror Story Generator API 실행 중**
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

2. **n8n 설치 및 실행**
   ```bash
   npm install -g n8n
   n8n start
   ```

---

## Available Workflows

### 1. Polling-based Story Generation
**파일:** `03_polling_story_generation.json`

API를 통해 스토리 생성을 트리거하고 완료까지 폴링합니다.

**흐름:**
```
Manual Trigger → Trigger Story Job → Poll Status (loop) → Final Result
```

**사용 사례:**
- 단일 스토리 생성
- 완료 확인이 필요한 경우

---

### 2. Research-to-Story Pipeline
**파일:** `04_research_story_pipeline.json`

연구 카드를 먼저 생성한 후 스토리를 생성합니다.

**흐름:**
```
Config → Trigger Research → Poll Research → Trigger Story → Poll Story → Result
```

**사용 사례:**
- 새로운 주제 연구 후 스토리 생성
- 연구-스토리 파이프라인 자동화

**설정 변경:**
`Config: Pipeline Settings` 노드에서 수정:
```javascript
return {
  json: {
    research_topic: 'Your topic here',
    research_tags: ['tag1', 'tag2'],
    research_model: 'gemini',  // or 'deep-research'
    story_max_count: 1,
    story_enable_dedup: true
  }
};
```

---

### 3. Scheduled Batch Generation
**파일:** `05_batch_generation.json`

정기 스케줄로 다수 작업을 배치 실행합니다.

**흐름:**
```
Schedule (6h) → Trigger Batch → Poll Batch Status → Summary → Notify
```

**사용 사례:**
- 정기 콘텐츠 생성
- 다수 연구 + 스토리 동시 실행

**스케줄 변경:**
`Schedule: Every 6 Hours` 노드에서 간격 조정

**배치 작업 수정:**
`Trigger Batch Jobs` 노드의 JSON Body 수정:
```json
{
  "jobs": [
    {"type": "research", "topic": "Topic 1", "model": "gemini"},
    {"type": "research", "topic": "Topic 2", "model": "gemini"},
    {"type": "story", "max_stories": 3, "enable_dedup": true}
  ]
}
```

---

## API Endpoints Reference

### Job Triggers

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/story/trigger` | POST | 스토리 생성 작업 트리거 |
| `/jobs/research/trigger` | POST | 연구 생성 작업 트리거 |
| `/jobs/batch/trigger` | POST | 다수 작업 배치 트리거 |

### Status Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/{job_id}` | GET | 단일 작업 상태 조회 |
| `/jobs/batch/{batch_id}` | GET | 배치 상태 조회 |
| `/jobs` | GET | 전체 작업 목록 |

### Job Status Values

| Status | Description |
|--------|-------------|
| `queued` | 대기 중 |
| `running` | 실행 중 |
| `succeeded` | 성공 |
| `failed` | 실패 |
| `skipped` | 건너뜀 (중복 등) |

---

## Importing Workflows

1. n8n 웹 UI 접속 (기본: http://localhost:5678)
2. **Workflows** → **Import from File**
3. JSON 파일 선택
4. **Import** 클릭

---

## Customization Tips

### API URL 변경
각 HTTP Request 노드의 URL을 환경에 맞게 수정:
```
http://localhost:8000  →  http://your-server:8000
```

### 타임아웃 조정
- Research jobs: 10-30초 폴링 간격 권장
- Story jobs: 5-10초 폴링 간격 권장
- Deep Research: 30-60초 폴링 간격 권장

### 알림 추가
`Batch Summary` 후 Discord/Slack 웹훅 노드 추가 가능:
```javascript
// Discord Webhook Example
{
  "content": "Batch complete: {{ $json.success_rate }} success rate"
}
```

---

## Troubleshooting

### Connection Refused
- API 서버 실행 확인: `curl http://localhost:8000/health`
- 포트 확인: `lsof -i :8000`

### Timeout Errors
- 폴링 간격 증가
- 최대 폴링 횟수 조정 (기본 60회)

### Job Fails Immediately
- API 로그 확인: `tail -f logs/*.log`
- 환경 변수 확인: `.env` 파일 점검

---

## Related Documents

- [API Reference](../../core/API.md)
- [Environment Setup](n8n_environment_setup.md)
- [Workflow Import Guide](n8n_workflow_import_guide.md)
