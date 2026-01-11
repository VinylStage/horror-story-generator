# TASK 1: 현재 시스템 실동작 요약 (As-Is Overview)

**작성일:** 2026-01-12
**상태:** 분석 완료
**범위:** 코드 분석 기반 실제 동작 정리

---

## 1. 시스템 진입점 (Entry Points)

현재 시스템은 **3개의 독립적인 진입점**을 가진다:

| 진입점 | 명령어 | 용도 |
|--------|--------|------|
| Story Generation CLI | `python main.py` | 공포 스토리 생성 루프 |
| Research Executor CLI | `python -m research_executor run <topic>` | 리서치 카드 생성 |
| Trigger API Server | `uvicorn research_api.main:app` | 비동기 작업 트리거 |

---

## 2. 스토리 생성 파이프라인 (실제 동작)

### 2.1 실행 흐름

```
main.py
  └─> horror_story_generator.py (HorrorStoryGenerator)
        ├─> ku_selector.py (지식 유닛 선택)
        ├─> template_manager.py (템플릿 로드)
        ├─> prompt_builder.py (프롬프트 구성)
        ├─> api_client.py (Claude API 호출)
        ├─> story_saver.py (스토리 저장)
        └─> story_registry.py (중복 체크 - 선택적)
```

### 2.2 핵심 모듈 역할

| 모듈 | 파일 | 실제 동작 |
|------|------|----------|
| 지식 유닛 선택 | `ku_selector.py` | `phase1_foundation/01_knowledge_units/` 에서 랜덤 선택 |
| 템플릿 관리 | `template_manager.py` | `phase1_foundation/03_templates/` 에서 로드 |
| 프롬프트 빌드 | `prompt_builder.py` | System + User 프롬프트 조합 |
| API 호출 | `api_client.py` | Claude Sonnet 3.5 호출 |
| 스토리 저장 | `story_saver.py` | `generated_stories/` 또는 `data/stories/` 저장 |
| 중복 체크 | `story_registry.py` | SQLite 기반 canonical fingerprint 비교 |

### 2.3 CLI 옵션 (main.py)

```bash
python main.py \
  --max-stories 5 \           # 최대 스토리 개수
  --duration-seconds 3600 \   # 실행 시간 제한
  --interval-seconds 30 \     # 스토리 간 대기 시간
  --enable-dedup \            # 중복 체크 활성화
  --db-path ./data/stories.db \ # SQLite 경로
  --load-history              # 기존 스토리 로드
```

---

## 3. 리서치 생성 파이프라인 (실제 동작)

### 3.1 실행 흐름

```
research_executor/cli.py (run 서브커맨드)
  └─> research_generator.py (ResearchGenerator)
        ├─> ollama_client.py (Ollama API 호출 - qwen3:30b)
        ├─> validator.py (응답 검증)
        └─> data/research/ (리서치 카드 저장)
```

### 3.2 CLI 옵션 (research_executor)

```bash
python -m research_executor run "Korean apartment horror" \
  --tags urban isolation \    # 태그
  --model qwen3:30b \         # Ollama 모델
  --timeout 120               # 타임아웃 (초)
```

### 3.3 리서치 카드 출력 포맷

```json
{
  "card_id": "RC-20260112-143052",
  "version": "1.0",
  "metadata": { "model": "qwen3:30b", "status": "complete" },
  "output": {
    "title": "...",
    "summary": "...",
    "key_concepts": [...],
    "horror_applications": [...],
    "canonical_affinity": { "setting": [...], "primary_fear": [...] }
  },
  "validation": { "quality_score": "good" }
}
```

---

## 4. Trigger API 파이프라인 (실제 동작)

### 4.1 아키텍처

```
Client (HTTP)
  └─> research_api/routers/jobs.py
        ├─> job_manager.py (Job 생성/저장)
        ├─> subprocess.Popen (CLI 실행)
        └─> job_monitor.py (PID 모니터링)
```

### 4.2 엔드포인트 (실제 구현됨)

| Method | Path | 동작 |
|--------|------|------|
| POST | `/jobs/story/trigger` | main.py subprocess 실행 |
| POST | `/jobs/research/trigger` | research_executor subprocess 실행 |
| GET | `/jobs/{job_id}` | Job 상태 조회 |
| GET | `/jobs` | Job 목록 조회 |
| POST | `/jobs/{job_id}/cancel` | SIGTERM 전송 |
| POST | `/jobs/monitor` | 모든 running job 상태 업데이트 |
| POST | `/jobs/{job_id}/monitor` | 단일 job 상태 업데이트 |
| POST | `/jobs/{job_id}/dedup_check` | 리서치 카드 중복 체크 |

### 4.3 Job 저장 구조

```
jobs/
└── {job_id}.json   # Job 메타데이터 (status, pid, artifacts)

logs/
├── story_{job_id}.log    # 스토리 작업 로그
└── research_{job_id}.log # 리서치 작업 로그
```

---

## 5. 중복 제어 시스템 (Dedup)

### 5.1 스토리 중복 체크 (story_registry.py)

- **방식:** Canonical dimension 매칭 (setting, primary_fear, antagonist, mechanism)
- **저장소:** SQLite (`data/stories.db`)
- **정책:** HIGH (>0.6) 시그널만 블로킹, LOW/MEDIUM 허용

### 5.2 리서치 중복 체크 (research_dedup_manager.py)

- **방식:** FAISS 벡터 유사도 (sentence-transformers)
- **저장소:** SQLite (`data/research_registry.db`) + FAISS 인덱스
- **정책:** 중복 감지 시 advisory 시그널 반환

---

## 6. Phase 1 Foundation 자산 (현재 상태)

### 6.1 실제 사용 중인 자산

| 디렉토리 | 파일 수 | 사용 여부 |
|----------|---------|----------|
| `phase1_foundation/01_knowledge_units/` | ~52 JSON | **사용 중** (ku_selector.py) |
| `phase1_foundation/03_templates/` | 15 JSON | **사용 중** (template_manager.py) |

### 6.2 미사용/참조용 자산

| 디렉토리 | 상태 |
|----------|------|
| `phase1_foundation/00_raw_research/` | 참조용 (코드에서 미사용) |
| `phase1_foundation/02_canonical_abstraction/` | 참조용 (코드에서 미사용) |

---

## 7. 데이터 디렉토리 구조 (현재)

```
data/
├── stories.db          # 스토리 중복 체크 SQLite
├── research_registry.db # 리서치 중복 체크 SQLite
├── stories/            # 생성된 스토리 JSON
├── research/           # 리서치 카드 JSON
└── research_cards.jsonl # (레거시 - 미사용)

generated_stories/      # (레거시 스토리 저장 경로)

jobs/                   # Trigger API Job 메타데이터
logs/                   # Job 실행 로그
```

---

## 8. 외부 의존성 (실제 사용 중)

| 서비스 | 용도 | 설정 |
|--------|------|------|
| Claude API | 스토리 생성 | `ANTHROPIC_API_KEY` 환경변수 |
| Ollama | 리서치 생성 | 로컬 서버 (http://localhost:11434) |
| FAISS-cpu | 리서치 벡터 검색 | pip 패키지 |
| SQLite | 중복 레지스트리 | 로컬 파일 |

---

## 9. 구현 상태 요약

| 기능 | 상태 | 비고 |
|------|------|------|
| 스토리 생성 (Claude) | **구현 완료** | main.py |
| 템플릿 기반 프롬프트 | **구현 완료** | 15개 템플릿 활성화 |
| 스토리 중복 체크 | **구현 완료** | SQLite + canonical matching |
| 리서치 생성 (Ollama) | **구현 완료** | research_executor |
| 리서치 중복 체크 | **구현 완료** | FAISS + SQLite |
| Trigger API | **구현 완료** | FastAPI + subprocess |
| Job 모니터링 | **구현 완료** | PID 추적 + 상태 업데이트 |
| Webhook 통합 | **미구현** | 설계 문서만 존재 |
| n8n 통합 | **미구현** | 설계 문서만 존재 |
| 벡터 기반 스토리 중복 | **미구현** | 리서치만 FAISS 적용 |

---

## 10. 코드베이스 규모

- **총 Python 라인 수:** ~18,276
- **핵심 모듈 수:** ~25
- **테스트 커버리지:** ~93%
- **문서 파일 수:** ~30+ (많은 문서가 outdated)

---

**문서 끝**
