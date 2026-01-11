# Phase B+ Implementation Guide

## Overview

Phase B+는 연구 카드 중복 제거, 스토리 시드 생성, 리소스 관리 기능을 추가합니다.

**핵심 원칙:**
- 연구는 스토리 생성을 **절대 차단하지 않음**
- 모든 작업은 **LOCAL-FIRST** (Ollama, FAISS, SQLite)
- 실패 시 **graceful degradation**

---

## Requirements

### Python Version

**권장 버전:** Python 3.11.x 또는 3.12.x

```bash
# pyenv 설치 (macOS)
brew install pyenv

# Python 3.11 설치
pyenv install 3.11.11

# 프로젝트 디렉토리에서 로컬 버전 설정
cd horror-story-generator
pyenv local 3.11.11

# 버전 확인
python --version  # Python 3.11.11
```

### 의존성 설치

```bash
# Poetry 설치 (권장)
curl -sSL https://install.python-poetry.org | python3 -

# 의존성 설치
poetry install

# 개발 의존성 포함 설치
poetry install --with dev
```

### 주요 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `faiss-cpu` | >=1.7.0 | 벡터 유사도 검색 |
| `httpx` | >=0.27.0 | 비동기 HTTP 클라이언트 |
| `fastapi` | ^0.115.0 | REST API 프레임워크 |
| `anthropic` | >=0.40.0 | Claude API 클라이언트 |

---

## Architecture

```
horror-story-generator/
├── data/
│   ├── research/
│   │   ├── cards/           # RC-*.json (연구 카드)
│   │   ├── vectors/
│   │   │   ├── research.faiss   # FAISS 인덱스
│   │   │   └── metadata.json    # vector_id <-> card_id 매핑
│   │   ├── logs/
│   │   └── registry.sqlite      # 연구 레지스트리
│   ├── seeds/
│   │   ├── SS-*.json            # 스토리 시드
│   │   └── seed_registry.sqlite # 시드 레지스트리
│   └── story_registry.db        # 기존 스토리 레지스트리
│
├── research_dedup/          # 중복 제거 모듈
│   ├── __init__.py
│   ├── embedder.py          # Ollama 임베딩 생성
│   ├── index.py             # FAISS 인덱스 관리
│   └── dedup.py             # 중복 검사 로직
│
├── research_registry.py     # 연구 카드 SQLite 레지스트리
├── story_seed.py            # 스토리 시드 생성
├── seed_registry.py         # 시드 SQLite 레지스트리
├── seed_integration.py      # 시드 → 프롬프트 통합
├── data_paths.py            # 중앙집중식 경로 관리
│
└── research_api/
    └── services/
        └── ollama_resource.py  # Ollama 리소스 관리
```

---

## 1. Research Deduplication (FAISS)

### 개요
FAISS를 사용한 시맨틱 유사도 기반 중복 검사.

### 신호 레벨
| Signal | 유사도 | 의미 |
|--------|--------|------|
| LOW | < 0.70 | 고유한 콘텐츠 |
| MEDIUM | 0.70 - 0.85 | 일부 중복, 주의 필요 |
| HIGH | >= 0.85 | 높은 유사도 |

**중요:** HIGH 신호도 **차단하지 않음** - 정보 제공만.

### CLI 사용법

```bash
# 카드 중복 검사
poetry run python -m research_executor dedup data/research/2026/01/RC-20260111-001.json

# FAISS 인덱스 상태 확인
poetry run python -m research_executor index

# 인덱스 재구축
poetry run python -m research_executor index --rebuild

# 단일 카드 인덱싱
poetry run python -m research_executor index -c path/to/card.json
```

### Python API

```python
from research_dedup import check_duplicate, add_card_to_index, DedupResult

# 중복 검사
result: DedupResult = check_duplicate(card_data)
print(f"Score: {result.similarity_score}")
print(f"Signal: {result.signal.value}")  # LOW/MEDIUM/HIGH
print(f"Nearest: {result.nearest_card_id}")

# 인덱스에 카드 추가
add_card_to_index(card_data, card_id="RC-2026-01-11-001")
```

---

## 2. Research Registry (SQLite)

### 스키마

```sql
CREATE TABLE research_cards (
    card_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP,
    file_path TEXT,
    embedding_indexed INTEGER DEFAULT 0,
    dedup_score REAL DEFAULT 0.0,
    dedup_signal TEXT DEFAULT 'LOW',
    status TEXT DEFAULT 'pending'
);
```

### Python API

```python
from research_registry import get_registry

registry = get_registry()

# 카드 등록
registry.register("RC-2026-01-11-001", "한국 아파트 공포", "/path/to/card.json")

# 중복 정보 업데이트
registry.update_dedup_info("RC-2026-01-11-001", 0.75, "MEDIUM")

# 통계 조회
stats = registry.get_stats()
# {'total': 10, 'completed': 8, 'indexed': 5, 'high_similarity': 1}
```

---

## 3. Story Seed Generation

### 개요
연구 카드를 스토리 생성에 최적화된 시드로 증류.

### 시드 형식

```json
{
  "seed_id": "SS-2026-01-11-001",
  "source_card_id": "RC-2026-01-11-001",
  "key_themes": ["isolation", "paranoia", "transformation"],
  "atmosphere_tags": ["oppressive", "uncanny", "claustrophobic"],
  "suggested_hooks": ["A researcher discovers...", "The algorithm begins..."],
  "cultural_elements": ["corporate surveillance", "gig economy"],
  "created_at": "2026-01-11T12:00:00"
}
```

### CLI 사용법

```bash
# 연구 카드에서 시드 생성
poetry run python -m research_executor seed-gen data/research/2026/01/RC-20260111-001.json

# 시드 목록 조회
poetry run python -m research_executor seed-list
```

### Python API

```python
from story_seed import generate_and_save_seed, load_seed, get_random_seed

# 시드 생성
seed = generate_and_save_seed(card_data, card_id="RC-2026-01-11-001")

# 시드 로드
seed = load_seed(Path("data/seeds/SS-2026-01-11-001.json"))

# 랜덤 시드 선택
seed = get_random_seed()
```

---

## 4. Seed Registry (SQLite)

### 스키마

```sql
CREATE TABLE story_seeds (
    seed_id TEXT PRIMARY KEY,
    source_card_id TEXT NOT NULL,
    created_at TIMESTAMP,
    file_path TEXT,
    times_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    is_available INTEGER DEFAULT 1
);
```

### Python API

```python
from seed_registry import get_seed_registry

registry = get_seed_registry()

# 최소 사용 시드 선택 (다양성 확보)
record = registry.get_least_used()

# 사용 횟수 증가
registry.mark_used("SS-2026-01-11-001")

# 통계
stats = registry.get_stats()
# {'total': 5, 'available': 5, 'total_uses': 12, 'never_used': 2}
```

---

## 5. Seed Integration (Non-blocking)

### 개요
시드를 시스템 프롬프트에 주입하여 스토리 생성 가이드.

### 선택 전략
| Strategy | 설명 |
|----------|------|
| `least_used` | 최소 사용 시드 선택 (기본) |
| `random` | 무작위 선택 |
| `newest` | 최신 시드 선택 |

### Python API

```python
from seed_integration import select_seed_for_generation, get_seed_context_for_prompt
from prompt_builder import build_system_prompt

# 시드 선택
selection = select_seed_for_generation(strategy="least_used")

if selection.has_seed:
    # 프롬프트 컨텍스트 생성
    seed_context = get_seed_context_for_prompt(selection)

    # 시스템 프롬프트에 시드 주입
    system_prompt = build_system_prompt(
        skeleton=template_skeleton,
        seed_context=seed_context
    )
```

---

## 6. Ollama Resource Management

### 개요
FastAPI 서버와 Ollama 모델 수명주기 관리.

### 기능
- **서버 종료 시 자동 정리**: 모든 활성 모델 언로드
- **유휴 타임아웃**: 지정 시간 후 자동 언로드 (기본 5분)
- **사용량 추적**: 모델별 마지막 사용 시간 기록

### 환경 변수

```bash
# 유휴 타임아웃 (초, 0=비활성화)
export OLLAMA_IDLE_TIMEOUT_SECONDS=300

# Ollama 기본 URL
export OLLAMA_BASE_URL=http://localhost:11434
```

### API 엔드포인트

```bash
# 리소스 상태 조회
curl http://localhost:8000/resource/status
```

응답 예시:
```json
{
  "running": true,
  "idle_timeout_seconds": 300,
  "active_models": {
    "qwen3:30b": "2026-01-11T12:00:00"
  },
  "model_count": 1
}
```

---

## 7. Data Paths

### 개요
모든 데이터 경로를 중앙 집중 관리.

### Python API

```python
from data_paths import (
    get_project_root,
    get_research_cards_dir,
    get_faiss_index_path,
    get_seeds_root,
    find_all_research_cards,
    ensure_data_directories
)

# 경로 조회
cards_dir = get_research_cards_dir()  # data/research/cards/
faiss_path = get_faiss_index_path()   # data/research/vectors/research.faiss

# 모든 연구 카드 찾기 (레거시 위치 포함)
all_cards = find_all_research_cards(include_legacy=True)

# 디렉토리 초기화 (자동 실행됨)
ensure_data_directories()
```

---

## CLI Commands Summary

```bash
# 연구 실행
poetry run python -m research_executor run "한국 아파트 공포"

# 카드 목록
poetry run python -m research_executor list

# 카드 검증
poetry run python -m research_executor validate path/to/card.json

# 중복 검사 (Phase B+)
poetry run python -m research_executor dedup path/to/card.json

# 인덱스 관리 (Phase B+)
poetry run python -m research_executor index
poetry run python -m research_executor index --rebuild

# 시드 생성 (Phase B+)
poetry run python -m research_executor seed-gen path/to/card.json

# 시드 목록 (Phase B+)
poetry run python -m research_executor seed-list
```

---

## Async Optimization

### 비동기 임베딩 API

`httpx`를 사용한 비동기 HTTP 클라이언트로 성능 최적화:

```python
from research_dedup import get_embedding_async, OllamaEmbedder

# 단일 비동기 임베딩
embedding = await get_embedding_async("한국 아파트 공포")

# 배치 비동기 임베딩 (동시 요청 제어)
embedder = OllamaEmbedder()
texts = ["text1", "text2", "text3", "text4", "text5"]
embeddings = await embedder.get_embeddings_batch_async(texts, max_concurrent=3)

# 비동기 Ollama 가용성 확인
is_ready = await embedder.is_available_async()
```

### 성능 특징

| 기능 | 동기 | 비동기 |
|------|------|--------|
| 단일 임베딩 | `get_embedding()` | `get_embedding_async()` |
| 배치 임베딩 | 순차 처리 | `asyncio.gather()` 병렬 처리 |
| HTTP 클라이언트 | `urllib` | `httpx` (권장) |
| 동시 요청 제어 | N/A | `asyncio.Semaphore` |

### httpx 없이 동작

`httpx`가 설치되지 않은 경우 자동 폴백:
- `run_in_executor`를 통해 동기 코드를 스레드풀에서 실행
- 기능은 동일하나 성능 이점 감소

---

## Testing

### 전체 테스트 실행

```bash
# 모든 테스트 실행 (coverage 포함)
poetry run pytest tests/ --cov --cov-report=term-missing

# Phase B+ 테스트만 실행
poetry run pytest tests/test_data_paths.py tests/test_research_dedup.py \
    tests/test_research_registry.py tests/test_story_seed.py \
    tests/test_seed_registry.py tests/test_seed_integration.py \
    tests/test_prompt_builder.py tests/test_ollama_resource.py \
    tests/test_api_endpoints.py tests/test_embedder_mock.py \
    tests/test_story_seed_mock.py -v
```

### 테스트 파일 구성

| 테스트 파일 | 테스트 대상 | 유형 |
|------------|------------|------|
| `test_data_paths.py` | 경로 관리 | Unit |
| `test_research_dedup.py` | FAISS 인덱스 | Unit |
| `test_research_registry.py` | 연구 레지스트리 | Unit |
| `test_story_seed.py` | 스토리 시드 기본 | Unit |
| `test_seed_registry.py` | 시드 레지스트리 | Unit |
| `test_seed_integration.py` | 시드 통합 | Unit |
| `test_prompt_builder.py` | 프롬프트 빌더 | Unit |
| `test_ollama_resource.py` | Ollama 리소스 | Unit/Async |
| `test_api_endpoints.py` | FastAPI 엔드포인트 | Integration (Mock) |
| `test_embedder_mock.py` | 임베딩 생성 | Unit (Mock) |
| `test_story_seed_mock.py` | 시드 생성 | Unit (Mock) |

### 모듈 임포트 확인

```bash
# 개별 모듈 임포트 테스트
poetry run python -c "from research_dedup import check_duplicate; print('OK')"
poetry run python -c "from story_seed import StorySeed; print('OK')"
poetry run python -c "from seed_integration import select_seed_for_generation; print('OK')"

# FAISS 가용성 확인
poetry run python -c "from research_dedup.index import is_faiss_available; print(is_faiss_available())"

# 리소스 매니저 테스트
poetry run python -c "from research_api.services.ollama_resource import OllamaResourceManager; print('OK')"
```

### Coverage 목표

- **전체:** 70% 이상
- **핵심 모듈:** 80% 이상 (`data_paths`, `prompt_builder`, `seed_integration`)
- **API 라우터:** 100% (mock 테스트)

---

## Configuration

### 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_IDLE_TIMEOUT_SECONDS` | `300` | 유휴 모델 자동 언로드 시간 (0=비활성화) |

### 임계값 (코드 내)

| 파일 | 변수 | 기본값 | 설명 |
|------|------|--------|------|
| `research_dedup/dedup.py` | `THRESHOLD_MEDIUM` | 0.70 | MEDIUM 신호 임계값 |
| `research_dedup/dedup.py` | `THRESHOLD_HIGH` | 0.85 | HIGH 신호 임계값 |
| `research_dedup/embedder.py` | `DEFAULT_EMBED_MODEL` | `qwen3:30b` | 임베딩 모델 |

---

## Troubleshooting

### FAISS not available
```bash
# faiss-cpu 설치 확인
poetry run pip show faiss-cpu

# 재설치
poetry install
```

### Ollama connection failed
```bash
# Ollama 서비스 확인
ollama list

# 서비스 시작
ollama serve
```

### Empty embeddings
- Ollama 모델이 로드되었는지 확인
- `qwen3:30b` 모델이 임베딩을 지원하는지 확인
