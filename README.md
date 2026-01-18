# 호러 소설 생성기

Claude API (Sonnet 4.5)를 활용한 한국어 호러 소설 자동 생성 시스템입니다.

> **Version:** v1.5.0 <!-- x-release-please-version -->
>
> 모든 문서는 현재 `src/` 패키지 구조와 Canonical Enum v1.0을 기준으로 작성되었습니다.
>
> 운영 상태: [docs/OPERATIONAL_STATUS.md](docs/OPERATIONAL_STATUS.md)

---

## 특징

- **템플릿 스켈레톤 시스템**: 15개의 사전 정의된 호러 템플릿으로 다양한 공포 패턴 생성
- **Canonical 중복 검사**: 5차원 fingerprint로 유사 스토리 방지
- **연구 카드 통합**: Ollama/Gemini Deep Research 기반 연구 생성 및 FAISS 시맨틱 중복 검사
- **스토리 레벨 중복 검사**: 시그니처 기반 + 시맨틱 임베딩 하이브리드 중복 방지 (v1.4.0)
- **자동 백업**: 스키마 마이그레이션 전 레지스트리 자동 백업
- **24시간 연속 운영**: Graceful shutdown 및 자동 재시도 지원
- **한국어 최적화**: 한국적 정서와 호러 요소를 반영한 프롬프트 설계

---

## 설치 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

또는 Poetry 사용 시:

```bash
poetry install
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 API 키를 설정합니다:

```env
ANTHROPIC_API_KEY=your_key_here
CLAUDE_MODEL=claude-sonnet-4-5-20250929
OUTPUT_DIR=./generated_stories
MAX_TOKENS=8192
TEMPERATURE=0.8

# 연구 카드 자동 주입 설정 (선택)
AUTO_INJECT_RESEARCH=true        # 연구 카드 자동 선택/주입 활성화
RESEARCH_INJECT_TOP_K=1          # 주입할 연구 카드 수
RESEARCH_INJECT_REQUIRE=false    # 연구 카드 필수 여부
RESEARCH_INJECT_EXCLUDE_DUP_LEVEL=HIGH  # 제외할 중복 레벨 (HIGH/MEDIUM)

# 스토리 레벨 중복 검사 설정 (선택)
ENABLE_STORY_DEDUP=true          # 스토리 시그니처 기반 중복 검사 활성화
STORY_DEDUP_STRICT=false         # true 시 중복 감지되면 생성 중단
ENABLE_STORY_SEMANTIC_DEDUP=true # 시맨틱 임베딩 기반 중복 검사 (v1.4.0)
STORY_SEMANTIC_THRESHOLD=0.85    # 시맨틱 HIGH 신호 기준점
STORY_HYBRID_THRESHOLD=0.85      # 하이브리드 중복 판정 기준점

# Gemini API 설정 (선택 - 연구 생성 전용)
# API: Google AI Studio (not Vertex AI)
# 모드: gemini (표준) 또는 deep-research (Deep Research Agent)
GEMINI_ENABLED=false             # Gemini 활성화 (true로 설정 시 사용 가능)
GEMINI_API_KEY=your_gemini_key   # Gemini API 키
GOOGLE_AI_MODEL=deep-research-pro-preview-12-2025  # 기본 모델

# Ollama 설정 (선택 - 로컬 모델)
OLLAMA_HOST=localhost            # Ollama 호스트
OLLAMA_PORT=11434                # Ollama 포트
```

---

## 사용 방법

### 스토리 생성 (CLI)

```bash
# 스토리 1개 생성 (기본 Claude Sonnet)
python main.py

# 5개 스토리 생성 (중복 검사 활성화)
python main.py --max-stories 5 --enable-dedup --interval-seconds 60

# 24시간 연속 실행
python main.py --duration-seconds 86400 --interval-seconds 1800 --enable-dedup

# 로컬 Ollama 모델로 스토리 생성
python main.py --model ollama:llama3
python main.py --model ollama:qwen
```

**CLI 옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--max-stories N` | 생성할 최대 스토리 수 | 1 |
| `--duration-seconds N` | 실행 지속 시간 (초) | 무제한 |
| `--interval-seconds N` | 생성 간 대기 시간 (초) | 0 |
| `--enable-dedup` | 중복 검사 활성화 | False |
| `--db-path PATH` | SQLite DB 경로 | data/story_registry.db |
| `--model MODEL` | 모델 선택 (`ollama:model`, Claude 모델명) | Claude Sonnet |

### 연구 카드 생성 (CLI)

```bash
# 연구 주제 실행 (기본 Ollama qwen3:30b)
python -m src.research.executor run "한국 아파트 공포" --tags horror korean apartment

# 다른 Ollama 모델로 연구
python -m src.research.executor run "병원 공포" --model qwen:14b

# Gemini API로 연구 (GEMINI_ENABLED=true 필요)
python -m src.research.executor run "도시 전설" --model gemini

# Gemini Deep Research Agent로 연구 (권장, GEMINI_ENABLED=true 필요)
# API: Google AI Studio, 모델: deep-research-pro-preview-12-2025
python -m src.research.executor run "한국 공포 문화" --model deep-research

# 연구 카드 목록 조회
python -m src.research.executor list

# 중복 검사
python -m src.research.executor dedup RC-20260112-123456
```

### API 서버 실행

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

**주요 엔드포인트:**
| Method | Path | 설명 |
|--------|------|------|
| POST | `/jobs/story/trigger` | 스토리 생성 트리거 |
| POST | `/jobs/research/trigger` | 연구 생성 트리거 |
| GET | `/jobs/{job_id}` | 작업 상태 조회 |
| POST | `/research/dedup` | 시맨틱 중복 검사 |

**인증 (선택):**

API 인증은 기본 비활성화입니다. 외부 노출 시 활성화하세요:

```bash
# .env
API_AUTH_ENABLED=true
API_KEY=your-secure-api-key
```

인증 활성화 시 `X-API-Key` 헤더 필요:
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/jobs/story/trigger
```

---

## 프로그래밍 방식 사용

```python
from src.story.generator import generate_horror_story

# 기본 실행 (템플릿 자동 선택)
result = generate_horror_story()
print(result["story"])

# 커스텀 요청으로 실행
result = generate_horror_story(
    custom_request="1980년대 한국의 시골 마을을 배경으로 한 귀신 이야기를 써주세요."
)

# 파일 저장 없이 실행
result = generate_horror_story(save_output=False)
```

---

## 출력 파일

생성된 소설은 `generated_stories/` 디렉토리에 저장됩니다:

- `horror_story_YYYYMMDD_HHMMSS.md`: 생성된 소설 본문 (마크다운)
- `horror_story_YYYYMMDD_HHMMSS_metadata.json`: 생성 메타데이터

---

## 프로젝트 구조

```
horror-story-generator/
├── main.py                      # 스토리 생성 CLI 진입점
├── src/
│   ├── story/                   # 스토리 생성 파이프라인
│   │   ├── generator.py         # 핵심 생성 로직
│   │   ├── api_client.py        # Claude API 클라이언트
│   │   └── template_loader.py   # 템플릿 스켈레톤 로더
│   ├── research/                # 연구 생성
│   │   ├── executor/            # CLI 실행기
│   │   └── integration/         # 스토리-연구 연동
│   ├── dedup/                   # 중복 검사
│   │   ├── similarity.py        # 스토리 중복 (Canonical)
│   │   ├── research/            # 연구 중복 (FAISS)
│   │   └── story/               # 스토리 시맨틱 중복 (v1.4.0)
│   ├── registry/                # 데이터 저장소
│   ├── infra/                   # 인프라 (로깅, 경로 등)
│   │   └── research_context/    # 연구↔스토리 연동 (공유 모듈)
│   └── api/                     # FastAPI 서버
├── assets/
│   └── templates/               # 15개 템플릿 스켈레톤
├── data/                        # 런타임 데이터
├── generated_stories/           # 출력 디렉토리
└── docs/                        # 문서
```

---

## 중복 검사 시스템

### 스토리 중복 (Canonical Fingerprint)

5개의 canonical 차원으로 스토리 fingerprint를 생성하여 유사도 검사:

| 차원 | 설명 |
|------|------|
| setting_archetype | 공간 원형 (apartment, hospital, digital 등) |
| primary_fear | 핵심 공포 (isolation, identity_erasure 등) |
| antagonist_archetype | 적대 원형 (system, ghost, technology 등) |
| threat_mechanism | 위협 방식 (surveillance, erosion 등) |
| twist_family | 결말 패턴 (revelation, inevitability 등) |

**신호 레벨:**
| Signal | Score | 동작 |
|--------|-------|------|
| LOW | < 0.3 | 수락 |
| MEDIUM | 0.3-0.6 | 수락 (로깅) |
| HIGH | > 0.6 | 재생성 (최대 2회) |

### 스토리 시맨틱 중복 (v1.4.0, FAISS Hybrid)

시그니처 기반 정확 매칭과 시맨틱 임베딩을 결합한 **하이브리드 중복 검사**:

```
hybrid_score = (canonical_score × 0.3) + (semantic_score × 0.7)
```

| 컴포넌트 | 설명 | 가중치 |
|---------|------|--------|
| Canonical | 시그니처 정확 매칭 (0 또는 1) | 30% |
| Semantic | `nomic-embed-text` 임베딩 유사도 | 70% |

**신호 레벨:**
| Signal | Score | 동작 |
|--------|-------|------|
| LOW | < 0.70 | 수락 |
| MEDIUM | 0.70-0.85 | 수락 (로깅) |
| HIGH | ≥ 0.85 | 중복 판정 |

### 연구 중복 (FAISS Semantic)

`nomic-embed-text` 임베딩 (768차원)으로 시맨틱 유사도 검사:

| Signal | Score | 의미 |
|--------|-------|------|
| LOW | < 0.70 | 고유 콘텐츠 |
| MEDIUM | 0.70-0.85 | 일부 중복 |
| HIGH | ≥ 0.85 | 중복 가능성 높음 |

---

## 팁

1. **Temperature 조정**: `.env` 파일의 `TEMPERATURE` 값으로 창의성 조절
   - 0.7-0.8: 균형잡힌 창의성 (권장)
   - 0.9-1.0: 더 창의적
   - 0.5-0.6: 더 일관됨

2. **토큰 수 조정**: 긴 소설을 원하면 `MAX_TOKENS` 값을 높이세요 (최대 8192)

3. **중복 검사 활성화**: 여러 스토리 생성 시 `--enable-dedup` 플래그 사용 권장

---

## 문서

| 문서 | 설명 |
|------|------|
| [docs/OPERATIONAL_STATUS.md](docs/OPERATIONAL_STATUS.md) | 운영 상태 선언 |
| [docs/core/README.md](docs/core/README.md) | 상세 기술 문서 |
| [docs/core/ARCHITECTURE.md](docs/core/ARCHITECTURE.md) | 시스템 아키텍처 |
| [docs/technical/TRIGGER_API.md](docs/technical/TRIGGER_API.md) | API 레퍼런스 |
| [docs/technical/REGISTRY_BACKUP_GUIDE.md](docs/technical/REGISTRY_BACKUP_GUIDE.md) | 백업 및 복구 가이드 |
| [docs/technical/runbook_24h_test.md](docs/technical/runbook_24h_test.md) | 24시간 테스트 절차 |

---

## 라이선스

MIT License

## 문의

이슈나 개선 제안이 있으시면 언제든지 연락주세요!
