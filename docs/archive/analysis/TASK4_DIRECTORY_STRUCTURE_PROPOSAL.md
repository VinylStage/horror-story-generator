# TASK 4: 디렉토리 구조 재설계 제안

**작성일:** 2026-01-12
**상태:** 제안 (Human confirmation required)
**원칙:** Phase 기반 명명 제거, 기능/역할 기반 구조

---

## 1. 현재 구조 (As-Is)

```
horror-story-generator/
├── main.py                          # 스토리 생성 진입점
├── horror_story_generator.py        # 핵심 생성 로직
├── api_client.py                    # Claude API
├── prompt_builder.py                # 프롬프트 구성
├── ku_selector.py                   # KU 선택
├── template_manager.py              # 템플릿 관리
├── story_saver.py                   # 스토리 저장
├── story_registry.py                # 스토리 중복 체크
├── job_manager.py                   # Job CRUD
├── job_monitor.py                   # Job 모니터링
│
├── research_executor/               # 리서치 CLI 모듈
│   ├── __init__.py
│   ├── cli.py
│   ├── research_generator.py
│   ├── ollama_client.py
│   └── validator.py
│
├── research_api/                    # FastAPI 모듈
│   ├── main.py
│   ├── routers/
│   │   └── jobs.py
│   ├── schemas/
│   │   └── jobs.py
│   └── services/
│       └── dedup_service.py
│
├── research_integration/            # 리서치 통합 모듈
│   ├── story_seeds.py
│   ├── faiss_index.py
│   └── research_dedup_manager.py
│
├── phase1_foundation/               # [PHASE 기반 - 변경 필요]
│   ├── 00_raw_research/
│   ├── 01_knowledge_units/
│   ├── 02_canonical_abstraction/
│   └── 03_templates/
│
├── phase2_execution/                # [PHASE 기반 - 변경 필요]
│
├── data/                            # 런타임 데이터
│   ├── stories/
│   ├── research/
│   ├── stories.db
│   └── research_registry.db
│
├── generated_stories/               # [레거시 - 정리 필요]
│
├── jobs/                            # Job 메타데이터
├── logs/                            # 실행 로그
│
├── tests/                           # 테스트
│
└── docs/                            # 문서
    ├── phase_b/                     # [PHASE 기반 - 변경 필요]
    ├── PHASE*.md                    # [PHASE 기반 - 변경 필요]
    └── ...
```

---

## 2. 제안 구조 (To-Be)

```
horror-story-generator/
│
├── README.md                        # 프로젝트 개요
├── VERSION                          # 버전 파일 (예: 0.3.0)
├── pyproject.toml                   # Python 프로젝트 설정
│
├── src/                             # 소스 코드 (패키지화)
│   ├── __init__.py
│   ├── story/                       # 스토리 생성 모듈
│   │   ├── __init__.py
│   │   ├── generator.py             # (기존 horror_story_generator.py)
│   │   ├── prompt_builder.py
│   │   ├── template_manager.py
│   │   ├── ku_selector.py
│   │   ├── saver.py                 # (기존 story_saver.py)
│   │   └── registry.py              # (기존 story_registry.py)
│   │
│   ├── research/                    # 리서치 모듈
│   │   ├── __init__.py
│   │   ├── generator.py             # (기존 research_generator.py)
│   │   ├── ollama_client.py
│   │   ├── validator.py
│   │   ├── dedup_manager.py         # (기존 research_dedup_manager.py)
│   │   ├── story_seeds.py
│   │   └── faiss_index.py
│   │
│   ├── api/                         # API 모듈
│   │   ├── __init__.py
│   │   ├── main.py                  # (기존 research_api/main.py)
│   │   ├── routers/
│   │   │   └── jobs.py
│   │   ├── schemas/
│   │   │   └── jobs.py
│   │   └── services/
│   │       └── dedup_service.py
│   │
│   ├── job/                         # Job 관리 모듈
│   │   ├── __init__.py
│   │   ├── manager.py               # (기존 job_manager.py)
│   │   └── monitor.py               # (기존 job_monitor.py)
│   │
│   └── common/                      # 공통 모듈
│       ├── __init__.py
│       └── api_client.py            # Claude API 클라이언트
│
├── cli/                             # CLI 진입점
│   ├── story.py                     # python -m cli.story (기존 main.py)
│   └── research.py                  # python -m cli.research (기존 research_executor/cli.py)
│
├── assets/                          # 정적 자산 (코드에서 참조)
│   ├── knowledge_units/             # (기존 phase1_foundation/01_knowledge_units/)
│   │   └── *.json
│   └── templates/                   # (기존 phase1_foundation/03_templates/)
│       └── *.json
│
├── data/                            # 런타임 데이터 (gitignore 대상)
│   ├── db/
│   │   ├── stories.db
│   │   └── research_registry.db
│   ├── output/
│   │   ├── stories/
│   │   └── research/
│   ├── jobs/
│   └── logs/
│
├── archive/                         # 아카이브 (역사 보존)
│   ├── raw_research/                # (기존 phase1_foundation/00_raw_research/)
│   ├── canonical_abstraction/       # (기존 phase1_foundation/02_canonical_abstraction/)
│   └── legacy_docs/                 # 이전 Phase 문서
│
├── tests/                           # 테스트
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── docs/                            # 문서 (Phase 제거)
    ├── README.md                    # 문서 인덱스
    ├── architecture.md              # 시스템 아키텍처
    ├── api-reference.md             # API 레퍼런스
    ├── cli-reference.md             # CLI 레퍼런스
    ├── schemas/
    │   ├── story.md                 # 스토리 스키마
    │   └── research-card.md         # 리서치 카드 스키마
    ├── guides/
    │   ├── getting-started.md
    │   ├── configuration.md
    │   └── deployment.md
    └── changelog/
        ├── CHANGELOG.md             # 통합 변경 로그
        └── releases/
            ├── v0.1.0.md
            ├── v0.2.0.md
            └── v0.3.0.md
```

---

## 3. 변경 매핑 테이블

### 3.1 소스 파일 이동

| 현재 위치 | 새 위치 | 비고 |
|----------|--------|------|
| `main.py` | `cli/story.py` | 진입점 분리 |
| `horror_story_generator.py` | `src/story/generator.py` | 패키지화 |
| `api_client.py` | `src/common/api_client.py` | 공통 모듈 |
| `prompt_builder.py` | `src/story/prompt_builder.py` | 스토리 모듈 |
| `ku_selector.py` | `src/story/ku_selector.py` | 스토리 모듈 |
| `template_manager.py` | `src/story/template_manager.py` | 스토리 모듈 |
| `story_saver.py` | `src/story/saver.py` | 스토리 모듈 |
| `story_registry.py` | `src/story/registry.py` | 스토리 모듈 |
| `job_manager.py` | `src/job/manager.py` | Job 모듈 |
| `job_monitor.py` | `src/job/monitor.py` | Job 모듈 |
| `research_executor/*` | `src/research/*` | 리서치 모듈 |
| `research_api/*` | `src/api/*` | API 모듈 |
| `research_integration/*` | `src/research/*` | 리서치 모듈 통합 |

### 3.2 데이터 디렉토리 이동

| 현재 위치 | 새 위치 | 비고 |
|----------|--------|------|
| `phase1_foundation/01_knowledge_units/` | `assets/knowledge_units/` | Phase 제거 |
| `phase1_foundation/03_templates/` | `assets/templates/` | Phase 제거 |
| `phase1_foundation/00_raw_research/` | `archive/raw_research/` | 아카이브 |
| `phase1_foundation/02_canonical_abstraction/` | `archive/canonical_abstraction/` | 아카이브 |
| `data/stories.db` | `data/db/stories.db` | 정리 |
| `data/research_registry.db` | `data/db/research_registry.db` | 정리 |
| `data/stories/` | `data/output/stories/` | 정리 |
| `data/research/` | `data/output/research/` | 정리 |
| `generated_stories/` | `data/output/stories/` | 레거시 통합 |
| `jobs/` | `data/jobs/` | 정리 |
| `logs/` | `data/logs/` | 정리 |

### 3.3 문서 이동

| 현재 위치 | 새 위치 | 비고 |
|----------|--------|------|
| `PHASE1_IMPLEMENTATION_SUMMARY.md` | `archive/legacy_docs/` | 아카이브 |
| `docs/PHASE*.md` | `archive/legacy_docs/` | 아카이브 |
| `docs/phase_b/*` | `archive/legacy_docs/` | 아카이브 |
| `docs/TRIGGER_API.md` | `docs/api-reference.md` | 통합 |
| `docs/PHASE_B_PLUS.md` | `docs/architecture.md` | 통합 |

---

## 4. 영향 받는 코드 (Import 변경 필요)

### 4.1 경로 상수 수정 필요

| 파일 | 수정 필요 상수 |
|------|---------------|
| `ku_selector.py` | `KU_DIR` 경로 |
| `template_manager.py` | `TEMPLATE_DIR` 경로 |
| `story_saver.py` | `OUTPUT_DIR` 경로 |
| `story_registry.py` | `DB_PATH` 경로 |
| `job_manager.py` | `JOBS_DIR` 경로 |
| `job_monitor.py` | `LOGS_DIR` 경로 |

### 4.2 Import 문 수정 필요

모든 상대 import를 패키지 기반으로 변경:
```python
# 변경 전
from story_registry import StoryRegistry

# 변경 후
from src.story.registry import StoryRegistry
```

---

## 5. Human Confirmation Required

| 항목 | 확인 필요 사유 |
|------|---------------|
| `src/` 패키지 구조 채택 | pyproject.toml 기반 패키지화 여부 |
| `assets/` vs `data/` 분리 | 정적 자산과 런타임 데이터 분리 적절성 |
| `archive/` 디렉토리 유지 | Git 히스토리로 충분한지 vs 명시적 보존 |
| CLI 진입점 분리 | `python main.py` → `python -m cli.story` 변경 |
| 레거시 `generated_stories/` 처리 | 기존 데이터 마이그레이션 방법 |

---

## 6. 대안 구조 (간소화 버전)

구조 변경을 최소화하려면 다음과 같이 진행 가능:

```
horror-story-generator/
├── main.py                      # 유지
├── *.py                         # 루트 모듈 유지
│
├── assets/                      # phase1_foundation → assets
│   ├── knowledge_units/
│   └── templates/
│
├── data/                        # 통합
│   ├── stories/
│   ├── research/
│   ├── db/
│   ├── jobs/
│   └── logs/
│
├── archive/                     # 역사 보존
│   └── ...
│
└── docs/                        # Phase 제거, 통합
    └── ...
```

이 경우 코드 변경은 경로 상수 수정만 필요.

---

**문서 끝**
