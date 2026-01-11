# TASK 2: Phase 기반 문서 분류표

**작성일:** 2026-01-12
**상태:** 분석 완료

---

## 분류 기준

| 분류 | 설명 | 처리 방향 |
|------|------|----------|
| `HISTORICAL_RECORD` | 과거 작업 기록, 현재 참조용 | 아카이브로 이동 |
| `DESIGN_ONLY_NOT_IMPLEMENTED` | 설계만 존재, 코드 미구현 | 삭제 또는 roadmap 통합 |
| `IMPLEMENTED_BUT_OUTDATED` | 구현됨, 문서가 실제와 불일치 | 업데이트 또는 삭제 |
| `STILL_RELEVANT` | 현재 구현과 일치, 유효함 | 유지 및 통합 |

---

## 1. 루트 디렉토리 Phase 문서

| 파일명 | 분류 | 근거 | 권장 조치 |
|--------|------|------|----------|
| `PHASE1_IMPLEMENTATION_SUMMARY.md` | `HISTORICAL_RECORD` | Phase 1 작업 완료 보고서, 현재 동작 가이드 아님 | `docs/archive/` 이동 |

---

## 2. docs/ 디렉토리 Phase 문서

| 파일명 | 분류 | 근거 | 권장 조치 |
|--------|------|------|----------|
| `docs/PHASE2_PREPARATION_ANALYSIS.md` | `HISTORICAL_RECORD` | "IMMUTABLE REFERENCE DOCUMENT" 명시, 과거 분석 기록 | `docs/archive/` 이동 |
| `docs/PHASE2A_TEMPLATE_ACTIVATION.md` | `IMPLEMENTED_BUT_OUTDATED` | 템플릿 활성화 완료됨, 전환 과정 설명은 불필요 | `docs/archive/` 이동 또는 삭제 |
| `docs/PHASE2B_GENERATION_MEMORY.md` | `IMPLEMENTED_BUT_OUTDATED` | 기능 구현됨, 문서는 초기 설계 상태 | `docs/archive/` 이동 또는 삭제 |
| `docs/PHASE2C_DEDUP_CONTROL.md` | `STILL_RELEVANT` | 현재 story_registry.py 동작과 일치함 | 유지, 메인 문서로 통합 |
| `docs/PHASE2C_RESEARCH_JOB.md` | `DESIGN_ONLY_NOT_IMPLEMENTED` | "SKELETON ONLY" 명시, 실제 research는 Ollama 사용 | 삭제 (research_executor 문서로 대체) |
| `docs/PHASE_B_PLUS.md` | `STILL_RELEVANT` | FAISS, Ollama, Story Seeds 현재 아키텍처 반영 | 유지, 아키텍처 문서로 통합 |
| `docs/TRIGGER_API.md` | `STILL_RELEVANT` | 현재 API 구현과 일치함 | 유지 |

---

## 3. docs/phase_b/ 서브디렉토리

| 파일명 | 분류 | 근거 | 권장 조치 |
|--------|------|------|----------|
| `docs/phase_b/overview.md` | `DESIGN_ONLY_NOT_IMPLEMENTED` | "Influence, Not Control" 철학 - 실제 구현 없음 | 삭제 또는 roadmap 통합 |
| `docs/phase_b/dedup_signal_policy.md` | `STILL_RELEVANT` | LOW/MEDIUM/HIGH 정의가 현재 코드와 일치 | 유지, dedup 문서로 통합 |
| `docs/phase_b/research_quality_schema.md` | `STILL_RELEVANT` | 리서치 카드 스키마가 실제 출력과 일치 | 유지, 스키마 문서로 통합 |
| `docs/phase_b/cultural_scope_strategy.md` | `DESIGN_ONLY_NOT_IMPLEMENTED` | 문화 가중치 로직이 코드에 미구현 | 삭제 또는 roadmap 통합 |
| `docs/phase_b/future_vector_backend.md` | `DESIGN_ONLY_NOT_IMPLEMENTED` | "STATUS: TODO — Not implemented" 명시 | 삭제 또는 roadmap 통합 |

---

## 4. phase1_foundation/ 디렉토리

| 디렉토리 | 분류 | 근거 | 권장 조치 |
|----------|------|------|----------|
| `phase1_foundation/00_raw_research/` | `HISTORICAL_RECORD` | 원본 리서치 노트, 코드에서 미사용 | `archive/` 이동 또는 유지 (참조용) |
| `phase1_foundation/01_knowledge_units/` | `STILL_RELEVANT` | ku_selector.py에서 활발히 사용 | **디렉토리 구조 변경 필요** (phase 제거) |
| `phase1_foundation/02_canonical_abstraction/` | `HISTORICAL_RECORD` | 참조 문서, 코드에서 미사용 | `archive/` 이동 |
| `phase1_foundation/03_templates/` | `STILL_RELEVANT` | template_manager.py에서 활발히 사용 | **디렉토리 구조 변경 필요** (phase 제거) |

---

## 5. phase2_execution/ 디렉토리

| 상태 | 설명 |
|------|------|
| **디렉토리 존재하지만 내용 미확인** | 파일 접근 오류 발생 |
| **권장 조치** | [Human confirmation required] - 수동 확인 후 삭제 또는 통합 결정 |

---

## 6. 분류 결과 요약

### 분류별 문서 수

| 분류 | 문서 수 | 비율 |
|------|---------|------|
| `HISTORICAL_RECORD` | 5 | 33% |
| `DESIGN_ONLY_NOT_IMPLEMENTED` | 5 | 33% |
| `IMPLEMENTED_BUT_OUTDATED` | 2 | 13% |
| `STILL_RELEVANT` | 6 | 40% |

**총 Phase 관련 문서: 15개** (일부 중복 분류 가능)

---

## 7. 권장 조치 요약

### 7.1 즉시 삭제 가능 (확인 후)

- `docs/PHASE2C_RESEARCH_JOB.md` - 스켈레톤만 있음, research_executor로 대체됨
- `docs/phase_b/overview.md` - 미구현 철학 문서
- `docs/phase_b/future_vector_backend.md` - "NOT STARTED" 명시

### 7.2 아카이브로 이동

- `PHASE1_IMPLEMENTATION_SUMMARY.md`
- `docs/PHASE2_PREPARATION_ANALYSIS.md`
- `docs/PHASE2A_TEMPLATE_ACTIVATION.md`
- `docs/PHASE2B_GENERATION_MEMORY.md`
- `phase1_foundation/00_raw_research/`
- `phase1_foundation/02_canonical_abstraction/`

### 7.3 유지 및 통합

- `docs/PHASE2C_DEDUP_CONTROL.md` → `docs/dedup_system.md`로 통합
- `docs/PHASE_B_PLUS.md` → `docs/architecture.md`로 통합
- `docs/TRIGGER_API.md` → 유지 (이미 유효)
- `docs/phase_b/dedup_signal_policy.md` → `docs/dedup_system.md`로 통합
- `docs/phase_b/research_quality_schema.md` → `docs/research_card_schema.md`로 통합

### 7.4 구조 변경 필요

- `phase1_foundation/01_knowledge_units/` → `data/knowledge_units/`
- `phase1_foundation/03_templates/` → `data/templates/`

---

## 8. Human Confirmation Required

다음 항목은 수동 확인이 필요함:

| 항목 | 확인 필요 사유 |
|------|---------------|
| `phase2_execution/` 디렉토리 내용 | 파일 접근 오류로 내용 미확인 |
| `docs/phase_b/cultural_scope_strategy.md` | 향후 구현 의도 확인 필요 |
| 원본 리서치 노트 보존 여부 | 히스토리 가치 판단 필요 |

---

**문서 끝**
