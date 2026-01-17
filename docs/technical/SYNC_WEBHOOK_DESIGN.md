# Sync Endpoint Webhook Design

**Version:** v1.4.4
**Status:** Implemented
**Related Issues:** #26, #76

---

## Overview

Sync 엔드포인트(`/research/run`, `/story/generate`)에서 작업 완료 시 외부 시스템에 알림을 보내는 웹훅 기능.

### Design Goals

1. **Fire-and-Forget**: API 응답을 빠르게 반환하고, 웹훅은 비동기로 발송
2. **Discord 호환**: Discord 웹훅 URL 자동 감지 및 embed 포맷 변환
3. **Retry Logic**: 실패 시 지수 백오프로 재시도
4. **Non-blocking**: 웹훅 실패가 API 응답에 영향 없음

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Endpoint                              │
│                  (/research/run, /story/generate)                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    fire_and_forget_webhook()                     │
│  1. URL 검사 (empty check)                                       │
│  2. Discord URL 감지                                             │
│  3. 페이로드 생성 (Discord/Standard)                              │
│  4. Background Thread 생성 및 시작                                │
│  5. 즉시 True 반환 (non-blocking)                                 │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               Background Thread (daemon=True)                    │
│                  _send_webhook_in_thread()                       │
│  - Max 3회 재시도                                                 │
│  - 지수 백오프 (1s, 2s, 4s... max 10s)                            │
│  - 30초 타임아웃                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
           ┌──────────────┐       ┌──────────────┐
           │   Discord    │       │   Standard   │
           │   Webhook    │       │   Webhook    │
           └──────────────┘       └──────────────┘
```

---

## Implementation Details

### 1. Discord URL Detection

```python
def is_discord_webhook_url(url: str) -> bool:
    discord_patterns = [
        "https://discord.com/api/webhooks/",
        "https://www.discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
        "https://www.discordapp.com/api/webhooks/",
    ]
    return any(url.startswith(pattern) for pattern in discord_patterns)
```

**Design Decision:**
- `startswith()` 사용으로 부분 문자열 매칭 방지 (e.g., `notdiscord.com`)
- `discordapp.com` 레거시 도메인도 지원

### 2. Payload Formats

#### Standard Webhook Payload

일반 웹훅 수신자를 위한 JSON 포맷:

```json
{
  "event": "completed",
  "endpoint": "/research/run",
  "status": "success",
  "result": {
    "card_id": "RC-20260118-120000",
    "output_path": "/path/to/card.json"
  },
  "timestamp": "2026-01-18T12:00:00.000000"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | `completed` 또는 `error` |
| `endpoint` | string | 호출된 API 엔드포인트 |
| `status` | string | `success` 또는 `error` |
| `result` | object | 작업 결과 데이터 |
| `timestamp` | string | ISO 8601 포맷 |

#### Discord Embed Payload

Discord 웹훅을 위한 embed 포맷:

```json
{
  "embeds": [{
    "title": "✅ Research Completed",
    "color": 5763719,
    "fields": [
      {"name": "Card ID", "value": "RC-123", "inline": true},
      {"name": "Output", "value": "`/path/to/file`", "inline": false},
      {"name": "Endpoint", "value": "`/research/run`", "inline": true}
    ],
    "timestamp": "2026-01-18T12:00:00.000000",
    "footer": {"text": "Horror Story Generator v1.4"}
  }]
}
```

### 3. Discord Embed Design

#### Color Scheme

| Status | Color | Hex | Discord Color Int |
|--------|-------|-----|-------------------|
| Success | Green | `#57F287` | `5763719` |
| Error | Red | `#ED4245` | `15548997` |

#### Title Format

| Endpoint | Success Title | Error Title |
|----------|---------------|-------------|
| `/research/*` | ✅ Research Completed | ❌ Research Failed |
| `/story/*` | ✅ Story Generation Completed | ❌ Story Generation Failed |
| Other | ✅ Operation Completed | ❌ Operation Failed |

#### Fields Mapping

| Result Field | Discord Field Name | Inline |
|--------------|-------------------|--------|
| `card_id` | Card ID | Yes |
| `story_id` | Story ID | Yes |
| `title` | Title | Yes |
| `output_path` | Output | No |
| `file_path` | File | No |
| `word_count` | Word Count | Yes |
| `error` | Error | No |
| (always) | Endpoint | Yes |

### 4. Thread Configuration

```python
thread = threading.Thread(
    target=_send_webhook_in_thread,
    args=(url, payload),
    daemon=True,  # 프로세스 종료 시 스레드도 함께 종료
)
```

**Why Daemon Thread:**
- 메인 프로세스가 종료되면 웹훅 스레드도 함께 종료
- 프로세스가 웹훅 완료를 기다리지 않음
- Fire-and-forget 패턴에 적합

### 5. Retry Logic

```python
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_BASE_DELAY = 1.0  # seconds
WEBHOOK_RETRY_MAX_DELAY = 10.0  # seconds

for attempt in range(max_retries):
    # ... attempt to send ...

    if attempt < max_retries - 1:
        delay = min(
            WEBHOOK_RETRY_BASE_DELAY * (2 ** attempt),
            WEBHOOK_RETRY_MAX_DELAY
        )
        time.sleep(delay)
```

| Attempt | Delay |
|---------|-------|
| 1 | 0s (immediate) |
| 2 | 1s |
| 3 | 2s |

### 6. HTTP Headers

#### Standard Webhook Headers

```
Content-Type: application/json
User-Agent: HorrorStoryGenerator/1.4
X-Webhook-Event: completed
X-Webhook-Endpoint: /research/run
```

#### Discord Webhook Headers

```
Content-Type: application/json
User-Agent: HorrorStoryGenerator/1.4
```

**Note:** Discord는 커스텀 헤더를 무시하므로 `X-Webhook-*` 헤더 생략.

---

## Usage Examples

### API Request with Webhook

```bash
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Korean apartment horror",
    "webhook_url": "https://discord.com/api/webhooks/xxx/yyy"
  }'
```

### Response

```json
{
  "success": true,
  "story_id": "20260118_120000",
  "title": "The Floor Above",
  "webhook_triggered": true
}
```

### Discord Message Preview

**Success:**
```
┌─────────────────────────────────────┐
│ ✅ Story Generation Completed       │
├─────────────────────────────────────┤
│ Story ID    │ Title                 │
│ 20260118... │ 역행                  │
├─────────────────────────────────────┤
│ File                                │
│ `/path/to/horror_story_xxx.md`     │
├─────────────────────────────────────┤
│ Word Count  │ Endpoint              │
│ 5122        │ `/story/generate`     │
├─────────────────────────────────────┤
│ Horror Story Generator v1.4         │
│ Today at 12:00 PM                   │
└─────────────────────────────────────┘
```

**Error:**
```
┌─────────────────────────────────────┐
│ ❌ Research Failed                  │
├─────────────────────────────────────┤
│ Error                               │
│ Research execution timed out        │
├─────────────────────────────────────┤
│ Endpoint                            │
│ `/research/run`                     │
├─────────────────────────────────────┤
│ Horror Story Generator v1.4         │
│ Today at 12:00 PM                   │
└─────────────────────────────────────┘
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty/None URL | `fire_and_forget_webhook()` returns `False`, no thread started |
| Network error | Retry up to 3 times with backoff |
| HTTP 4xx/5xx | Retry up to 3 times with backoff |
| Timeout (30s) | Retry up to 3 times with backoff |
| All retries fail | Log error, no exception raised |

---

## Testing

### Unit Tests (37 tests)

```bash
python -m pytest tests/test_sync_webhook.py -v
```

**Test Classes:**
- `TestBuildSyncWebhookPayload` - Standard payload 생성
- `TestFireAndForgetWebhook` - 스레드 시작 및 daemon 설정
- `TestSendWebhookInThread` - HTTP 전송 및 재시도
- `TestSchemaWebhookFields` - Schema webhook 필드
- `TestDiscordWebhookDetection` - Discord URL 감지
- `TestBuildDiscordEmbedPayload` - Discord embed 생성
- `TestDiscordWebhookIntegration` - Discord 통합

### Manual Testing

```python
from src.infra.webhook import fire_and_forget_webhook
import time

fire_and_forget_webhook(
    url="https://discord.com/api/webhooks/xxx/yyy",
    endpoint="/research/run",
    status="success",
    result={"card_id": "RC-TEST-123"},
)
time.sleep(5)  # Wait for background thread
```

---

## Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| `WEBHOOK_TIMEOUT_SECONDS` | 30 | HTTP 요청 타임아웃 |
| `WEBHOOK_MAX_RETRIES` | 3 | 최대 재시도 횟수 |
| `WEBHOOK_RETRY_BASE_DELAY` | 1.0 | 재시도 기본 딜레이 (초) |
| `WEBHOOK_RETRY_MAX_DELAY` | 10.0 | 재시도 최대 딜레이 (초) |
| `DISCORD_COLOR_SUCCESS` | 0x57F287 | Discord 성공 색상 |
| `DISCORD_COLOR_ERROR` | 0xED4245 | Discord 에러 색상 |

---

## Related Files

- `src/infra/webhook.py` - 웹훅 구현
- `src/api/routers/research.py` - Research 엔드포인트
- `src/api/routers/story.py` - Story 엔드포인트
- `src/api/schemas/research.py` - Research 스키마
- `src/api/schemas/story.py` - Story 스키마
- `tests/test_sync_webhook.py` - 테스트
- `docs/core/API.md` - API 문서
