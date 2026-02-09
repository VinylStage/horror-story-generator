# 문서 감사 보고서 (Documentation Audit Report)

**이슈:** #146
**감사일:** 2026-02-09
**버전:** v1.7.0
**작성자:** Claude Code (Documentation Audit Agent)

---

## 1. 감사 개요 (Executive Summary)

Horror Story Generator v1.7.0 기준으로 전체 문서를 코드베이스와 대조 감사한 결과,
**8개 우선순위 영역**에서 문서-코드 불일치가 발견되었다.

| 등급 | 건수 | 설명 |
|------|------|------|
| **P1 — Critical** | 3건 | 삭제된 기능이 문서에 잔존, 버전 마일스톤 오류 |
| **P2 — High** | 2건 | README 부정확, 라이선스 파일 누락 |
| **P3 — Medium** | 4건 | 용어 잔존, DOCUMENT_MAP 누락, 아카이브 중복 |
| **P4 — Low** | 2건 | verification 아카이빙, openapi.yaml 정합성 |

**핵심 수치:**
- `jobs` / `job_` 용어 잔존: src/ 32건 (4파일), docs/ 410건 (45파일), 합계 **~442건**
- 아카이브 중복 파일 (reports/ vs analysis/): **7건**
- DOCUMENT_MAP.md 미등재 문서: **3건** (task-scheduler 하위)
- LICENSE 파일: **미존재**

---

## 2. 문서-코드 추적 테이블 (Doc-to-Code Trace)

### 2.1 핵심 문서 정합성

| 문서 | 위치 | 코드 일치 | 주요 불일치 |
|------|------|-----------|-------------|
| README.md | `/README.md` | **부분 일치** | `generated_stories/` 프로젝트 구조 표기 잔존 (L239), `.env` 예제 정합 |
| ROADMAP.md | `docs/core/ROADMAP.md` | **부분 불일치** | Current State에 삭제된 기능 잔존, Version Milestones 완전 오류 |
| ARCHITECTURE.md | `docs/core/ARCHITECTURE.md` | 부분 일치 | 경로 불일치 (`cards/` vs `YYYY/MM/`) |
| API.md | `docs/core/API.md` | 일치 | - |
| OPERATIONAL_STATUS.md | `docs/core/OPERATIONAL_STATUS.md` | 일치 | - |
| DOCUMENT_MAP.md | `docs/DOCUMENT_MAP.md` | **부분 불일치** | task-scheduler 하위 3문서 미등재 |
| openapi.yaml | `docs/technical/openapi.yaml` | **부분 불일치** | 버전 1.6.0 (실제 1.7.0), Phase B+ 문구 잔존 |

### 2.2 삭제된 코드 vs 문서 참조

| 삭제된 항목 | 삭제 PR | 문서 잔존 위치 |
|-------------|---------|----------------|
| `main.py` (루트 CLI) | #139 | ROADMAP.md L22 "main.py CLI" |
| `src/infra/job_monitor.py` | #139 | ROADMAP.md L29 "src/infra/job_monitor.py" |
| `src/infra/job_manager.py` | #139 | IMPLEMENTATION_AUDIT.md L55-56 |
| Trigger API (`/trigger/*`) | #139 | ROADMAP.md L13 "Trigger API", L28, L263 |
| Legacy trigger endpoints | #139 | ROADMAP.md L52 "deprecated" (실제는 완전 삭제) |

### 2.3 구현됐으나 미반영된 항목

| 구현 항목 | 코드 위치 | 문서 상태 |
|-----------|-----------|-----------|
| 썸네일 생성 (v1.6.1) | `src/image/` (10개 소스파일) | ROADMAP.md 반영 완료 |
| Task (Job→Task 리네임) | `src/scheduler/`, `src/api/routers/tasks.py` | ROADMAP.md 일부 반영, 다수 문서 미반영 |

---

## 3. 불일치 목록 (Mismatch List)

### P1: ROADMAP.md — 삭제된 기능 잔존 및 버전 오류

**심각도:** Critical
**영향:** 신규 기여자가 존재하지 않는 기능을 전제로 작업할 위험

#### P1-1: Current State Summary에 삭제된 기능 나열

**위치:** `docs/core/ROADMAP.md` L10-14

```markdown
The system currently supports:
- Story generation via Claude API with deduplication control
- Research generation via Ollama with FAISS-based similarity
- Trigger API for non-blocking job execution        ← 삭제됨 (PR #139)
- 24-hour continuous operation with graceful shutdown
```

**실제 상태:** Trigger API는 PR #139에서 완전 삭제됨. 현재는 Task Scheduler가 비동기 실행 담당.

#### P1-2: Version Milestones 완전 오류

**위치:** `docs/core/ROADMAP.md` L258-284

```markdown
### v0.3.x (Current)    ← 실제 v1.7.0
### v0.4.0 (Next)       ← 이미 구현됨 (Webhook = v1.3.0, Batch = v1.4.0)
### v0.5.0 (Future)     ← 일부 구현됨
### v1.0.0 (Stable)     ← 이미 v1.7.0
```

**실제 상태:** 현재 버전 v1.7.0. Webhook(v1.3.0), Batch(v1.4.0), Scheduler(v1.5.0) 모두 구현 완료.

#### P1-3: Recently Implemented Features 용어 오류

**위치:** `docs/core/ROADMAP.md` L38-57

- "Job Scheduler System" → 실제 "Task Scheduler System"
- "Job 실행 모델" → "Task 실행 모델"
- "SQLite 기반 Job persistence" → "Task persistence"
- "`/jobs` CRUD" → "`/tasks` CRUD"
- "Legacy trigger endpoints deprecated" → 실제로는 완전 삭제됨

---

### P2: README.md 부정확

**심각도:** High
**영향:** 사용자가 잘못된 설정으로 실행

#### P2-1: 프로젝트 구조 `generated_stories/` 표기

**위치:** `README.md` L239

```
├── generated_stories/           # 출력 디렉토리
```

**실제 상태:** 출력 디렉토리는 `data/novel/YYYY/MM/`이며 L204에 올바르게 기술됨. 프로젝트 구조도만 미수정.

#### P2-2: 라이선스 표기 vs LICENSE 파일 부재

**위치:** `README.md` L326

```
CC BY-NC-SA 4.0
```

**실제 상태:** README에 `CC BY-NC-SA 4.0`으로 표기되어 있으나 `LICENSE` 파일이 저장소에 존재하지 않음.
openapi.yaml L40에는 `name: Private`로 표기되어 일치하지 않음.

---

### P3: `jobs` 용어 잔존

**심각도:** Medium
**영향:** 코드-문서 간 용어 혼란

#### 잔존 현황

| 영역 | 파일 수 | 발생 건수 | 비고 |
|------|---------|-----------|------|
| `src/` | 4 | 32 | scheduler 내부 변수, routers |
| `tests/` | 0 | 0 | 테스트는 이미 정리됨 |
| `docs/` | 45 | 410 | 대부분 task-scheduler 설계 문서, archive |
| **합계** | **49** | **~442** | |

#### 주요 잔존 파일 (docs/)

| 파일 | 건수 | 조치 방향 |
|------|------|-----------|
| `docs/task-scheduler/PERSISTENCE_SCHEMA.md` | 43 | 정규화 필요 |
| `docs/task-scheduler/IMPLEMENTATION_PLAN.md` | 23 | 정규화 필요 |
| `docs/task-scheduler/TEST_STRATEGY.md` | 22 | 정규화 필요 |
| `docs/task-scheduler/API_IMPACT.md` | 20 | 정규화 필요 |
| `docs/task-scheduler/RECOVERY_SCENARIOS.md` | 19 | 정규화 필요 |
| `docs/technical/TASK_SCHEDULER_DESIGN.md` | 40 | 정규화 필요 |
| `docs/technical/task-scheduler-AS_IS_TO_BE_API_DESIGN-v1.md` | 16 | As-Is 섹션은 유지, To-Be 정규화 |

#### 주요 잔존 파일 (src/)

| 파일 | 건수 | 비고 |
|------|------|------|
| `src/scheduler/persistence.py` | 27 | SQLite 컬럼명 (DB 호환성) |
| `src/scheduler/queue_manager.py` | 3 | 변수명 |
| `src/api/routers/tasks.py` | 1 | 주석 |
| `src/api/routers/story.py` | 1 | 주석 |

> **참고:** `src/scheduler/persistence.py`의 SQLite 컬럼명(`job_id`, `job_group_id` 등)은 DB 마이그레이션 없이 변경 불가.
> 코드 레벨 alias만 정규화하고, DB 컬럼은 backward-compat으로 유지하는 것을 권장.

---

### P4: 라이선스 불일치

**심각도:** High
**영향:** 법적 명확성 부재

| 소스 | 표기 |
|------|------|
| README.md L326 | CC BY-NC-SA 4.0 |
| openapi.yaml L40 | Private |
| pyproject.toml | (확인 필요) |
| LICENSE 파일 | **존재하지 않음** |

**권장 조치:**
1. `LICENSE` 파일 생성 (CC BY-NC-SA 4.0 전문)
2. openapi.yaml `license.name` 통일
3. pyproject.toml `license` 필드 통일

---

### P5: DOCUMENT_MAP.md 누락 항목

**심각도:** Medium
**영향:** 문서 탐색 시 누락

#### 미등재 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| `IMPLEMENTATION_PLAN.md` | `docs/task-scheduler/` | Task Scheduler 구현 계획 |
| `TEST_STRATEGY.md` | `docs/task-scheduler/` | 테스트 전략 |
| `TASKGROUP_BEHAVIOR_OPTIONS.md` | `docs/task-scheduler/` | TaskGroup 동작 옵션 |

---

### P6: Archive 중복

**심각도:** Medium
**영향:** 불필요한 파일 중복, 유지보수 혼란

#### 중복 파일 (reports/ vs analysis/)

`docs/archive/reports/`와 `docs/archive/analysis/`에 동일 파일명이 **7건** 존재:

| 파일명 | reports/ | analysis/ |
|--------|----------|-----------|
| `CLI_RESOURCE_CLEANUP_VERIFICATION.md` | O | O |
| `FINAL_PIPELINE_SMOKE_TEST.md` | O | O |
| `STEP4B_FINAL_REPORT.md` | O | O |
| `STEP4B_VALIDATION_REPORT.md` | O | O |
| `STEP4C_DOCUMENTATION_ALIGNMENT_REPORT.md` | O | O |
| `STORY_DEDUP_FINAL_VERIFICATION.md` | O | O |
| `UNIFIED_PIPELINE_FINAL_VERIFICATION.md` | O | O |

**권장 조치:** `reports/` 디렉토리 삭제 후 `analysis/`로 통합, 또는 역순.

---

### P7: Verification 보고서 아카이빙 대상

**심각도:** Low
**영향:** 최신 상태가 아닌 보고서가 활성 디렉토리에 잔존

#### 아카이빙 후보 (v1.2.1~v1.3.2 기준)

| 문서 | 기준 버전 | 조치 |
|------|-----------|------|
| `RELEASE_v1.2.1_SUMMARY.md` | v1.2.1 | 아카이브 이동 |
| `SECURITY_PATCH_v1.3.2.md` | v1.3.2 | 아카이브 이동 |
| `V131_TECH_DEBT_CLEANUP_TEST.md` | v1.3.1 | 아카이브 이동 |
| `WEBHOOK_NOTIFICATIONS_TEST.md` | v1.3.0 | 아카이브 이동 |
| `STORY_GENERATION_E2E_TEST.md` | v1.2.x | 아카이브 이동 |

**유지 대상:**
- `FULL_PIPELINE_TEST_20260113.md` — 최신 파이프라인 테스트
- `GEMINI_DEEP_RESEARCH_VERIFICATION.md` — 현행 기능
- `MODEL_SELECTION_VERIFICATION.md` — 현행 기능

---

### P8: openapi.yaml 정합성

**심각도:** Low
**영향:** API 문서와 실제 API 간 불일치

| 항목 | openapi.yaml | 실제 |
|------|-------------|------|
| 버전 | `1.6.0` | `1.7.0` |
| 설명 | "Horror Story Research API" | 전체 API (story, scheduler, tasks, research 포함) |
| Phase B+ | "Phase B+ Additions" 문구 잔존 | Phase 개념 폐기됨 |
| 라이선스 | `Private` | README: CC BY-NC-SA 4.0 |
| `jobs` 관련 경로 | 없음 (이미 정리) | 일치 |

---

## 4. 용어 정규화 요약 (jobs → tasks)

### 정규화 범위

| 계층 | 상태 | 비고 |
|------|------|------|
| API 엔드포인트 | **완료** | `/tasks` CRUD, `/scheduler/*` |
| 테스트 코드 | **완료** | 0건 잔존 |
| 소스 코드 | **부분 완료** | 32건 잔존 (4파일) |
| 문서 | **미완료** | 410건 잔존 (45파일) |
| DB 스키마 | **미적용** | `job_id`, `job_group_id` 컬럼 유지 (호환성) |

### 정규화 전략 권장

1. **소스 코드:** 변수명/주석만 정규화 (DB 컬럼명은 유지)
2. **활성 문서 (docs/core/, docs/technical/, docs/task-scheduler/):** 전면 정규화
3. **아카이브 (docs/archive/):** 변경하지 않음 (역사적 기록)
4. **IMPLEMENTATION_AUDIT.md:** 현재 시점 기준으로 업데이트

---

## 5. 아카이브 대상 요약

### 5.1 docs/archive/ 내 중복 정리

- `docs/archive/reports/` — 7개 파일이 `docs/archive/analysis/`와 중복
- **권장:** `reports/` 디렉토리 통합 삭제, `analysis/`만 유지

### 5.2 docs/verification/ → docs/archive/ 이동 대상

- 5개 파일 (v1.2.1~v1.3.2 기준, 위 P7 참조)

---

## 6. 버전관리 스킴 설명

| 항목 | 현재 값 | 관리 방식 |
|------|---------|-----------|
| 애플리케이션 버전 | v1.7.0 | `release-please` 자동 관리 |
| 버전 마커 | `<!-- x-release-please-version -->` | 자동 치환 |
| 문서 버전 (DOCUMENT_MAP) | 1.1 | 수동 관리 |
| openapi.yaml 버전 | 1.6.0 | **수동 관리 — 미업데이트** |
| ROADMAP 마일스톤 | v0.3.x~v1.0.0 | **완전 오류 — 업데이트 필요** |

---

## 7. 라이선스 정합성

| 소스 | 값 | 일치 여부 |
|------|-----|-----------|
| README.md | CC BY-NC-SA 4.0 | 기준값 |
| openapi.yaml | Private | **불일치** |
| LICENSE 파일 | (없음) | **누락** |

---

## 8. 확인 필요 항목

| 항목 | 이유 | 담당 |
|------|------|------|
| pyproject.toml license 필드 | 라이선스 통일 확인 | 유지보수자 |
| DB 컬럼 job→task 마이그레이션 여부 | 호환성 vs 정합성 트레이드오프 | 아키텍트 |
| openapi.yaml 버전 자동화 여부 | release-please 연동 가능한지 | DevOps |
| `data/research/cards/` vs `data/research/YYYY/MM/` 경로 정규화 | data_paths.py 주석과 실제 동작 불일치 | 개발자 |

---

**End of Audit Report**
