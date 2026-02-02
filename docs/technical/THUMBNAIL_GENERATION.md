# Thumbnail Generation Guide

**Version:** 1.0
**Application Version:** 1.6.1 <!-- x-release-please-version -->
**Last Updated:** 2026-01-31

---

## Overview

Horror Story Generator는 스토리 생성 시 자동으로 OG(Open Graph) 표준 썸네일 이미지(1200x630px)를 생성할 수 있습니다.
이 기능은 기본적으로 비활성화되어 있으며, 환경변수 설정을 통해 활성화할 수 있습니다.

---

## Quick Start

### 1. 환경변수 설정

```bash
# .env 파일에 추가
ENABLE_THUMBNAIL_GENERATION=true

# 사용할 Provider의 API 키 설정 (하나 이상 필요)
OPENAI_API_KEY=sk-...              # DALL-E 3용
# 또는
STABILITY_AI_API_KEY=sk-...        # Stability AI용
# 또는
REPLICATE_API_TOKEN=r8_...         # FLUX용
# 또는
LOCAL_SD_ENABLED=true              # Local SD용 (ComfyUI)
```

### 2. 스토리 생성

```bash
# CLI로 생성 (기본 provider: openai_dalle3)
python main.py

# API로 생성
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "심야 지하철 괴담"}'
```

---

## Supported Providers

| Provider | 환경변수 | 비용 | 속도 | 품질 |
|----------|---------|------|------|------|
| OpenAI DALL-E 3 | `OPENAI_API_KEY` | $0.04/image | 3-5s | High |
| Stability AI SD 3.5 | `STABILITY_AI_API_KEY` | $0.035/image | 3-5s | High |
| FLUX Schnell (Replicate) | `REPLICATE_API_TOKEN` | $0.003/image | 2-3s | Good |
| Local SD (ComfyUI) | `LOCAL_SD_ENABLED=true` | Free | 3-10s | Varies |

---

## Provider Configuration

### OpenAI DALL-E 3 (Default)

가장 높은 품질의 이미지를 생성합니다.

```bash
OPENAI_API_KEY=sk-your-api-key
IMAGE_PRIMARY_PROVIDER=openai_dalle3
```

**API 키 발급:**
1. [OpenAI Platform](https://platform.openai.com/) 접속
2. API Keys → Create new secret key
3. 발급된 키를 `OPENAI_API_KEY`에 설정

### Stability AI

SDXL 3.5 기반의 고품질 이미지를 생성합니다.

```bash
STABILITY_AI_API_KEY=sk-your-api-key
IMAGE_PRIMARY_PROVIDER=stability_ai
```

**API 키 발급:**
1. [Stability AI Platform](https://platform.stability.ai/) 접속
2. Account → API Keys
3. 발급된 키를 `STABILITY_AI_API_KEY`에 설정

### FLUX (via Replicate)

가장 저렴한 클라우드 옵션입니다.

```bash
REPLICATE_API_TOKEN=r8_your-token
IMAGE_PRIMARY_PROVIDER=flux
```

**API 토큰 발급:**
1. [Replicate](https://replicate.com/) 접속
2. Account → API tokens
3. 발급된 토큰을 `REPLICATE_API_TOKEN`에 설정

### Local SD (ComfyUI)

**무료**로 로컬에서 이미지를 생성합니다. GPU가 필요합니다.

```bash
LOCAL_SD_ENABLED=true
LOCAL_SD_HOST=localhost
LOCAL_SD_PORT=8188
IMAGE_PRIMARY_PROVIDER=local_sd
```

**ComfyUI 설정:**
1. [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 설치
2. SDXL 모델 다운로드 (sd_xl_base_1.0.safetensors)
3. ComfyUI 서버 실행: `python main.py --listen 0.0.0.0 --port 8188`

---

## Local Options (Free)

로컬에서 무료로 이미지를 생성하는 방법입니다.

### Option 1: ComfyUI (Recommended)

GPU가 있는 경우 가장 좋은 선택입니다.

**요구사항:**
- NVIDIA GPU (VRAM 8GB 이상 권장)
- Python 3.10+

**설치:**
```bash
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt

# 모델 다운로드 (SDXL)
# models/checkpoints/ 에 sd_xl_base_1.0.safetensors 배치

# 서버 실행
python main.py --listen 0.0.0.0 --port 8188
```

### Option 2: LocalAI (OpenAI Compatible)

LocalAI는 OpenAI API와 **호환되는** 로컬 서버입니다.
**무료**이며 OpenAI 서버에 요청하지 않습니다.

**요구사항:**
- Docker 또는 직접 설치
- CPU만으로도 동작 (느림), GPU 권장

**설치 (Docker):**
```bash
# GPU 버전
docker run -p 8080:8080 --gpus all localai/localai:latest-aio-gpu-nvidia-cuda-12

# CPU 버전
docker run -p 8080:8080 localai/localai:latest-aio-cpu
```

**설정:**
```bash
# .env
OPENAI_API_KEY=dummy  # LocalAI는 키 검증 안함
OPENAI_BASE_URL=http://localhost:8080/v1
IMAGE_PRIMARY_PROVIDER=openai_dalle3
```

> **참고:** LocalAI는 OpenAI API 형식을 모방하는 **로컬 서버**입니다.
> `OPENAI_API_KEY`는 형식 맞추기용이며 실제 OpenAI에 과금되지 않습니다.

### Option 3: Ollama + FLUX (Experimental)

Ollama는 LLM용이지만 일부 이미지 모델도 지원합니다.

**설치:**
```bash
# Ollama 설치 후
ollama pull flux-schnell  # 또는 사용 가능한 모델
```

> **참고:** Ollama의 이미지 생성 지원은 아직 실험적입니다.
> 안정적인 로컬 이미지 생성은 ComfyUI를 권장합니다.

---

## API Usage

### Generate with Thumbnail

```bash
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "폐병원 탐사 공포",
    "thumbnail_provider": "openai_dalle3"
  }'
```

**Response:**
```json
{
  "success": true,
  "story_id": "story_20260131_123456",
  "title": "폐병원의 마지막 환자",
  "story": "...",
  "thumbnail_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
  "thumbnail_provider": "openai_dalle3"
}
```

### Provider Options

| Parameter | Values |
|-----------|--------|
| `thumbnail_provider` | `openai_dalle3`, `stability_ai`, `flux`, `local_sd` |

---

## Fallback Behavior

Provider 순서:
1. Primary Provider (설정된 경우)
2. Fallback Provider (설정된 경우)
3. 사용 가능한 첫 번째 Provider

```bash
# Primary와 Fallback 설정
IMAGE_PRIMARY_PROVIDER=openai_dalle3
IMAGE_FALLBACK_PROVIDER=stability_ai
```

**Graceful Degradation:**
- API 키가 없으면 해당 Provider 건너뜀
- 모든 Provider 실패 시 스토리는 정상 저장 (`thumbnail: ""`)
- 기능 비활성화 시 빈 문자열 반환

---

## Troubleshooting

### 썸네일이 생성되지 않음

1. `ENABLE_THUMBNAIL_GENERATION=true` 확인
2. 최소 하나의 Provider API 키 설정 확인
3. 로그에서 에러 메시지 확인

### ComfyUI 연결 실패

```bash
# ComfyUI 서버 상태 확인
curl http://localhost:8188/system_stats

# 방화벽 확인
# ComfyUI가 --listen 0.0.0.0으로 실행되었는지 확인
```

### LocalAI 연결 실패

```bash
# LocalAI 서버 상태 확인
curl http://localhost:8080/readyz

# 모델 로드 상태 확인
curl http://localhost:8080/models
```

### FLUX 타임아웃

Replicate의 cold start 시간이 길 수 있습니다.

```bash
# 타임아웃 늘리기
IMAGE_GENERATION_TIMEOUT=60
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_THUMBNAIL_GENERATION` | `false` | 기능 활성화 여부 |
| `OPENAI_API_KEY` | - | OpenAI API 키 (DALL-E 3용) |
| `STABILITY_AI_API_KEY` | - | Stability AI API 키 |
| `REPLICATE_API_TOKEN` | - | Replicate API 토큰 (FLUX용) |
| `LOCAL_SD_ENABLED` | `false` | Local SD 활성화 |
| `LOCAL_SD_HOST` | `localhost` | ComfyUI 호스트 |
| `LOCAL_SD_PORT` | `8188` | ComfyUI 포트 |
| `IMAGE_PRIMARY_PROVIDER` | `openai_dalle3` | 기본 Provider |
| `IMAGE_FALLBACK_PROVIDER` | - | 대체 Provider |
| `IMAGE_GENERATION_TIMEOUT` | `30` | 타임아웃 (초) |
| `IMAGE_MAX_RETRIES` | `1` | 재시도 횟수 |

---

## Related Documents

- [API.md](../core/API.md) - REST API 참조
- [ARCHITECTURE.md](../core/ARCHITECTURE.md) - 시스템 아키텍처
