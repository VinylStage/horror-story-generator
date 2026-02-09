# Documentation Map

**Version:** 2.0
**Application Version:** 1.7.0 <!-- x-release-please-version -->
**Last Updated:** 2026-02-09

---

## Overview

이 문서는 Horror Story Generator 프로젝트의 문서 구조를 설명합니다.

---

## Directory Structure

```
docs/
├── core/                    # 핵심 문서 (필독)
├── technical/               # 기술 참조 문서
├── task-scheduler/          # Task Scheduler 설계 문서
├── data-model/              # 데이터 모델 스펙
├── audit/                   # 문서 감사 보고서
├── legal/                   # 라이선스 및 법적 문서
└── archive/                 # 아카이브 (역사적 기록)
```

---

## Core Documents (`docs/core/`)

프로젝트의 핵심 문서입니다. 새로운 기여자는 이 문서들을 먼저 읽어야 합니다.

| 문서 | 설명 |
|------|------|
| [README.md](core/README.md) | 프로젝트 소개 및 빠른 시작 |
| [ARCHITECTURE.md](core/ARCHITECTURE.md) | 시스템 아키텍처 개요 |
| [API.md](core/API.md) | REST API 참조 |
| [ROADMAP.md](core/ROADMAP.md) | 개발 로드맵 및 계획 |
| [OPERATIONAL_STATUS.md](core/OPERATIONAL_STATUS.md) | 운영 상태 및 제한 사항 |
| [RELEASE_GUIDE.md](core/RELEASE_GUIDE.md) | 릴리스 프로세스 가이드 |

---

## Technical Documents (`docs/technical/`)

기술 참조 문서입니다.

| 문서 | 설명 |
|------|------|
| [openapi.yaml](technical/openapi.yaml) | OpenAPI 3.0 스펙 |
| [TASK_SCHEDULER_DESIGN.md](technical/TASK_SCHEDULER_DESIGN.md) | Task Scheduler 시스템 설계 |
| [dataflow.md](technical/dataflow.md) | 데이터 흐름도 |
| [decision_log.md](technical/decision_log.md) | 기술 결정 로그 |
| [runbook_24h_test.md](technical/runbook_24h_test.md) | 24시간 테스트 런북 |
| [BACKUP_RESTORE_GUIDE.md](technical/BACKUP_RESTORE_GUIDE.md) | 통합 백업/복구 CLI 가이드 |
| [SYNC_WEBHOOK_DESIGN.md](technical/SYNC_WEBHOOK_DESIGN.md) | 동기 웹훅 설계 문서 |
| [THUMBNAIL_GENERATION.md](technical/THUMBNAIL_GENERATION.md) | 썸네일 이미지 자동 생성 가이드 |
| [STORY_SEMANTIC_DEDUP.md](technical/STORY_SEMANTIC_DEDUP.md) | 스토리 의미 중복 제거 |
| [RESEARCH_DEDUP_SETUP.md](technical/RESEARCH_DEDUP_SETUP.md) | 연구 중복 제거 설정 |
| [canonical_enum.md](technical/canonical_enum.md) | Canonical 열거형 정의 |
| [KU_TO_CANONICAL_KEY_RULES.md](technical/KU_TO_CANONICAL_KEY_RULES.md) | KU → Canonical Key 변환 규칙 |
| [CANONICAL_KEY_APPLICATION_SCOPE.md](technical/CANONICAL_KEY_APPLICATION_SCOPE.md) | Canonical Key 적용 범위 |
| [FUTURE_VECTOR_BACKEND_NOTE.md](technical/FUTURE_VECTOR_BACKEND_NOTE.md) | 향후 벡터 백엔드 노트 |

---

## Task Scheduler Documents (`docs/task-scheduler/`)

Task Scheduler 시스템 설계 및 구현 문서입니다.

| 문서 | 설명 |
|------|------|
| [API_CONTRACT.md](task-scheduler/API_CONTRACT.md) | API 계약 및 구현 상태 |
| [API_IMPACT.md](task-scheduler/API_IMPACT.md) | API 영향 분석 |
| [DOMAIN_MODEL.md](task-scheduler/DOMAIN_MODEL.md) | 도메인 모델 정의 |
| [ENTITY_RELATIONSHIPS.md](task-scheduler/ENTITY_RELATIONSHIPS.md) | 엔티티 관계 정의 |
| [DESIGN_GUARDS.md](task-scheduler/DESIGN_GUARDS.md) | 설계 가드레일 |
| [EXECUTION_FLOW.md](task-scheduler/EXECUTION_FLOW.md) | 실행 흐름 다이어그램 |
| [PERSISTENCE_SCHEMA.md](task-scheduler/PERSISTENCE_SCHEMA.md) | SQLite 스키마 |
| [RECOVERY_SCENARIOS.md](task-scheduler/RECOVERY_SCENARIOS.md) | 복구 시나리오 |
| [CONCURRENCY_OPTIONS.md](task-scheduler/CONCURRENCY_OPTIONS.md) | 동시성 전략 결정 팩 |
| [TASKGROUP_BEHAVIOR_OPTIONS.md](task-scheduler/TASKGROUP_BEHAVIOR_OPTIONS.md) | TaskGroup 실패 동작 결정 팩 |
| [IMPLEMENTATION_PLAN.md](task-scheduler/IMPLEMENTATION_PLAN.md) | 구현 계획 |
| [TEST_STRATEGY.md](task-scheduler/TEST_STRATEGY.md) | 테스트 전략 |
| [E2E_TEST_PLAN.md](task-scheduler/E2E_TEST_PLAN.md) | E2E 테스트 계획 |
| [E2E_TEST_REPORT.md](task-scheduler/E2E_TEST_REPORT.md) | E2E 테스트 결과 |

---

## Data Model (`docs/data-model/`)

데이터 구조 스펙입니다.

| 문서 | 설명 |
|------|------|
| [canonical-data.md](data-model/canonical-data.md) | 핵심 데이터 구조 스펙 |

---

## Audit Reports (`docs/audit/`)

문서 감사 보고서입니다.

| 문서 | 설명 |
|------|------|
| [IMPLEMENTATION_AUDIT.md](audit/IMPLEMENTATION_AUDIT.md) | 구현 상태 감사 보고서 |
| [DOC_AUDIT_REPORT.md](audit/DOC_AUDIT_REPORT.md) | 문서 감사 보고서 (v1.7.0) |
| [DOC_AUDIT_ISSUES.md](audit/DOC_AUDIT_ISSUES.md) | 문서 감사 액션 체크리스트 |

---

## Legal (`docs/legal/`)

라이선스 및 법적 문서입니다.

| 문서 | 설명 |
|------|------|
| [LICENSING.md](legal/LICENSING.md) | 라이선스 상세 설명 (CC BY-NC-SA 4.0) |

---

## Archive (`docs/archive/`)

더 이상 활성화되지 않은 역사적 문서입니다. 자세한 내용은 [ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md) 참조.

```
docs/archive/
├── ARCHIVE_INDEX.md          # 아카이브 인덱스
├── verification_reports/     # v1.2~v1.3 검증 보고서
├── analysis/                 # 프로젝트 초기 분석 보고서
├── feature_docs/             # 이전 버전 설계 문서
├── v1_legacy/                # v1 레거시 문서
├── v2_design/                # v2 설계 문서
├── work_logs/                # 작업 로그
├── n8n_guides/               # n8n 가이드
├── n8n_workflows/            # n8n 워크플로우 파일
├── legacy_todo/              # 레거시 TODO 인덱스
└── raw_research/             # 원본 연구 자료
```

---

## Quick Reference

### For New Contributors

1. [README.md](core/README.md) - 프로젝트 개요
2. [ARCHITECTURE.md](core/ARCHITECTURE.md) - 시스템 구조
3. [API.md](core/API.md) - API 사용법

### For Operations

1. [OPERATIONAL_STATUS.md](core/OPERATIONAL_STATUS.md) - 운영 상태
2. [runbook_24h_test.md](technical/runbook_24h_test.md) - 테스트 런북
3. [BACKUP_RESTORE_GUIDE.md](technical/BACKUP_RESTORE_GUIDE.md) - 통합 백업/복구 가이드

### For Development

1. [ROADMAP.md](core/ROADMAP.md) - 개발 계획
2. [decision_log.md](technical/decision_log.md) - 결정 로그
3. [canonical-data.md](data-model/canonical-data.md) - 데이터 스펙

### For Task Scheduler

1. [API_CONTRACT.md](task-scheduler/API_CONTRACT.md) - API 계약
2. [TASK_SCHEDULER_DESIGN.md](technical/TASK_SCHEDULER_DESIGN.md) - 시스템 설계
3. [DESIGN_GUARDS.md](task-scheduler/DESIGN_GUARDS.md) - 설계 가드레일

---

## Maintenance

이 문서는 문서 구조 변경 시 업데이트되어야 합니다.

**관련 이슈:** #14, #146
