# 문서 감사 액션 체크리스트 (Documentation Audit Issues)

**이슈:** #146
**생성일:** 2026-02-09
**기준 버전:** v1.7.0
**관련 문서:** [DOC_AUDIT_REPORT.md](DOC_AUDIT_REPORT.md)

---

## 개요

이 문서는 문서 감사 보고서에서 발견된 불일치를 해결하기 위한 **액션 체크리스트**이다.
커밋 단위(Phase)별로 작업을 분리하여 점진적으로 수정한다.

---

## Commit 1: 감사 보고서 및 이슈 목록 생성

**범위:** 감사 문서 생성 (이 파일 포함)

- [x] `docs/audit/DOC_AUDIT_REPORT.md` 생성
- [x] `docs/audit/DOC_AUDIT_ISSUES.md` 생성 (이 파일)

---

## Commit 2: 활성 문서-코드베이스 정합성 수정

**범위:** P1 (ROADMAP.md), P2 (README.md), P8 (openapi.yaml)
**대상 파일:**
- `docs/core/ROADMAP.md`
- `README.md`
- `docs/technical/openapi.yaml`

### ROADMAP.md 수정

- [ ] **P1-1:** Current State Summary에서 "Trigger API for non-blocking job execution" 삭제
  - Task Scheduler 기반 비동기 실행으로 교체
- [ ] **P1-2:** Version Milestones 섹션 전면 재작성
  - v0.3.x~v1.0.0 → 실제 릴리스 히스토리 (v1.3.0~v1.7.0) 반영
  - 또는 섹션 삭제 후 GitHub Releases 참조로 대체
- [ ] **P1-3:** Recently Implemented Features 섹션 용어 정규화
  - "Job Scheduler" → "Task Scheduler"
  - "Job 실행 모델" → "Task 실행 모델"
  - "`/jobs` CRUD" → "`/tasks` CRUD"
  - "Legacy trigger endpoints deprecated" → 삭제 또는 "삭제됨 (v1.7.0)" 표기
- [ ] **P1-3:** Planned Features 섹션 업데이트
  - "Job Scheduler Templates & Cron" → "Task Scheduler Templates & Cron"
  - "JobTemplate" → "TaskTemplate"
- [ ] **P1-3:** Technical Debt 섹션 업데이트
  - "Job history cleanup" 표기 정규화
- [ ] **P1-3:** Open Questions 섹션 업데이트
  - "Job storage scalability?" → "Task storage scalability?"

### README.md 수정

- [ ] **P2-1:** 프로젝트 구조 트리에서 `generated_stories/` 행 삭제
  - 이미 `data/novel/` 행이 존재하므로 중복 제거

### openapi.yaml 수정

- [ ] **P8:** `info.version` 필드: `1.6.0` → 동적 관리 또는 `1.7.0` 수동 업데이트
- [ ] **P8:** `info.description`에서 "Phase B+ Additions" 문구 삭제
- [ ] **P8:** `info.title`: "Horror Story Research API" → 실제 범위 반영
- [ ] **P8:** `info.license.name`: `Private` → `CC BY-NC-SA 4.0` (README와 통일)

---

## Commit 3: 아카이브 정리 및 인덱스 생성

**범위:** P6 (Archive 중복), P7 (Verification 아카이빙)

### Archive 중복 해소 (P6)

- [ ] `docs/archive/reports/` 내 7개 중복 파일 삭제
  - `CLI_RESOURCE_CLEANUP_VERIFICATION.md`
  - `FINAL_PIPELINE_SMOKE_TEST.md`
  - `STEP4B_FINAL_REPORT.md`
  - `STEP4B_VALIDATION_REPORT.md`
  - `STEP4C_DOCUMENTATION_ALIGNMENT_REPORT.md`
  - `STORY_DEDUP_FINAL_VERIFICATION.md`
  - `UNIFIED_PIPELINE_FINAL_VERIFICATION.md`
- [ ] `docs/archive/reports/` 디렉토리에 남은 파일이 없으면 디렉토리 삭제

### Verification 아카이빙 (P7)

- [ ] 다음 파일을 `docs/verification/` → `docs/archive/verification/`으로 이동:
  - `RELEASE_v1.2.1_SUMMARY.md`
  - `SECURITY_PATCH_v1.3.2.md`
  - `V131_TECH_DEBT_CLEANUP_TEST.md`
  - `WEBHOOK_NOTIFICATIONS_TEST.md`
  - `STORY_GENERATION_E2E_TEST.md`
- [ ] `docs/archive/verification/` 디렉토리 생성 (필요 시)

### DOCUMENT_MAP.md 업데이트 (P5)

- [ ] task-scheduler 섹션에 누락된 3개 문서 추가:
  - `IMPLEMENTATION_PLAN.md`
  - `TEST_STRATEGY.md`
  - `TASKGROUP_BEHAVIOR_OPTIONS.md`
- [ ] Verification Reports 섹션에서 아카이브 이동된 5개 문서 제거
- [ ] Archive 섹션 구조 업데이트 (verification/ 추가, reports/ 제거)

---

## Commit 4: 문서 헤더 및 네비게이션 README 추가

**범위:** 문서 구조 개선

- [ ] 주요 docs/ 하위 디렉토리에 네비게이션 README.md 추가 (필요 시)
- [ ] 문서 헤더에 버전 정보, 최종 수정일 추가 (주요 문서)

---

## Commit 5: 깨진 링크 수정 및 링크 검사 가이드

**범위:** 링크 정합성

- [ ] 전체 문서 내부 링크 검사
- [ ] 깨진 링크 수정
- [ ] 링크 검사 절차 문서화 (선택)

---

## Commit 6: 라이선스 파일 및 정합성

**범위:** P4 (라이선스 불일치)

- [ ] `LICENSE` 파일 생성 (CC BY-NC-SA 4.0 전문)
- [ ] `docs/technical/openapi.yaml` — `info.license.name` 통일
- [ ] `pyproject.toml` — `license` 필드 확인 및 통일

---

## 범위 외 (Out of Scope)

다음 항목은 이번 문서 감사에서 **수정하지 않는다:**

| 항목 | 이유 |
|------|------|
| `src/` 내 `jobs` 용어 정규화 | 코드 변경은 별도 이슈 필요 |
| DB 스키마 `job_id` → `task_id` 마이그레이션 | 마이그레이션 계획 필요 |
| `docs/archive/` 내 `jobs` 용어 | 역사적 기록 보존 |
| IMPLEMENTATION_AUDIT.md 전면 갱신 | 별도 감사 주기에서 수행 |

---

## 진행 상태 요약

| Commit | 설명 | 상태 |
|--------|------|------|
| Commit 1 | 감사 보고서 생성 | **완료** |
| Commit 2 | 활성 문서 정합성 수정 | 대기 |
| Commit 3 | 아카이브 정리 | 대기 |
| Commit 4 | 문서 헤더/네비게이션 | 대기 |
| Commit 5 | 링크 수정 | 대기 |
| Commit 6 | 라이선스 정합성 | 대기 |

---

**End of Issues List**
