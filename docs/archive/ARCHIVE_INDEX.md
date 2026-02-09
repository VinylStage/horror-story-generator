# Archive Index

> **Last Updated:** 2026-02-09

---

## Overview

이 디렉토리는 더 이상 현재 코드와 일치하지 않는 역사적 문서를 보관합니다.
아카이브된 문서는 **참고용으로만** 사용하며, 현재 시스템 동작을 반영하지 않습니다.

---

## verification_reports/

v1.2.1~v1.3.2 기준으로 작성된 검증 보고서. 현재 코드(v1.7.0+)와 일치하지 않음.

| 파일 | 원래 위치 | 아카이브 사유 |
|------|----------|-------------|
| FULL_PIPELINE_TEST_20260113.md | docs/verification/ | v1.2.x 기준 파이프라인 테스트 |
| GEMINI_DEEP_RESEARCH_VERIFICATION.md | docs/verification/ | v1.3.x 기준 모델 검증 |
| MODEL_SELECTION_VERIFICATION.md | docs/verification/ | v1.3.x 기준 모델 선택 검증 |
| RELEASE_v1.2.1_SUMMARY.md | docs/verification/ | v1.2.1 릴리스 요약 |
| SECURITY_PATCH_v1.3.2.md | docs/verification/ | v1.3.2 보안 패치 기록 |
| STORY_GENERATION_E2E_TEST.md | docs/verification/ | v1.2.x 기준 E2E 테스트 |
| V131_TECH_DEBT_CLEANUP_TEST.md | docs/verification/ | v1.3.1 기술 부채 정리 검증 |
| WEBHOOK_NOTIFICATIONS_TEST.md | docs/verification/ | v1.3.x 기준 웹훅 테스트 |

---

## feature_docs/

이전 버전의 설계 문서 또는 통합된 문서.

| 파일 | 원래 위치 | 아카이브 사유 | 대체 문서 |
|------|----------|-------------|----------|
| task-scheduler-AS_IS_TO_BE_API_DESIGN-v1.md | docs/technical/ | AS-IS 상태가 제거됨 (PR #139). TO-BE가 현재 구현 | docs/task-scheduler/API_CONTRACT.md |
| REGISTRY_BACKUP_GUIDE.md | docs/technical/ | BACKUP_RESTORE_GUIDE.md에 통합됨 (중복) | docs/technical/BACKUP_RESTORE_GUIDE.md |
| PHASE2C_RESEARCH_JOB.md | (원래 위치) | 레거시 Job 시스템 기반 설계 | docs/task-scheduler/ |

---

## analysis/

프로젝트 초기 구조 분석 및 마이그레이션 계획 문서.

| 파일 | 내용 |
|------|------|
| STEP3_AS_IS_STRUCTURE.md | 기존 프로젝트 구조 분석 |
| STEP3_FILE_CLASSIFICATION.csv | 파일 분류 데이터 |
| STEP3_MIGRATION_PLAN.md | 마이그레이션 계획 |
| STEP3_MULTIREPO_SPLIT.md | 멀티 레포 분할 검토 |
| STEP3_TO_BE_STRUCTURE.md | 목표 프로젝트 구조 |
| STEP4B_FINAL_REPORT.md | Step 4B 최종 보고서 |
| STEP4B_VALIDATION_REPORT.md | Step 4B 검증 보고서 |
| STEP4C_DOCUMENTATION_ALIGNMENT_REPORT.md | 문서 정합성 보고서 |
| CLI_RESOURCE_CLEANUP_VERIFICATION.md | CLI 리소스 정리 검증 |
| FINAL_PIPELINE_SMOKE_TEST.md | 파이프라인 스모크 테스트 |
| STORY_DEDUP_FINAL_VERIFICATION.md | 스토리 중복 제거 검증 |
| UNIFIED_PIPELINE_FINAL_VERIFICATION.md | 통합 파이프라인 검증 |
| TASK1~6 분석 문서 | 프로젝트 초기 분석 시리즈 |

---

## 참고

- 아카이브 문서의 "job" 용어는 의도적으로 보존합니다 (역사적 맥락)
- 현재 시스템은 "task" 용어를 사용합니다 (v1.7.0+)
- 현재 문서는 `docs/core/`, `docs/technical/`, `docs/task-scheduler/` 참조
