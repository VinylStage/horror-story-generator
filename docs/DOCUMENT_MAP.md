# Documentation Map

**Version:** 1.0
**Last Updated:** 2026-01-15

---

## Overview

이 문서는 Horror Story Generator 프로젝트의 문서 구조를 설명합니다.

---

## Directory Structure

```
docs/
├── core/                    # 핵심 문서 (필독)
├── technical/               # 기술 참조 문서
├── data-model/              # 데이터 모델 스펙
├── verification/            # 검증 및 테스트 보고서
├── audit/                   # 감사 보고서
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

---

## Technical Documents (`docs/technical/`)

기술 참조 문서입니다.

| 문서 | 설명 |
|------|------|
| [openapi.yaml](technical/openapi.yaml) | OpenAPI 3.0 스펙 |
| [dataflow.md](technical/dataflow.md) | 데이터 흐름도 |
| [decision_log.md](technical/decision_log.md) | 기술 결정 로그 |
| [TRIGGER_API.md](technical/TRIGGER_API.md) | 트리거 API 상세 |
| [runbook_24h_test.md](technical/runbook_24h_test.md) | 24시간 테스트 런북 |
| [REGISTRY_BACKUP_GUIDE.md](technical/REGISTRY_BACKUP_GUIDE.md) | 레지스트리 백업 가이드 |
| [RESEARCH_DEDUP_SETUP.md](technical/RESEARCH_DEDUP_SETUP.md) | 연구 중복 제거 설정 |
| [canonical_enum.md](technical/canonical_enum.md) | Canonical 열거형 정의 |
| [KU_TO_CANONICAL_KEY_RULES.md](technical/KU_TO_CANONICAL_KEY_RULES.md) | KU → Canonical Key 변환 규칙 |
| [CANONICAL_KEY_APPLICATION_SCOPE.md](technical/CANONICAL_KEY_APPLICATION_SCOPE.md) | Canonical Key 적용 범위 |
| [FUTURE_VECTOR_BACKEND_NOTE.md](technical/FUTURE_VECTOR_BACKEND_NOTE.md) | 향후 벡터 백엔드 노트 |

---

## Data Model (`docs/data-model/`)

데이터 구조 스펙입니다.

| 문서 | 설명 |
|------|------|
| [canonical-data.md](data-model/canonical-data.md) | 핵심 데이터 구조 스펙 |

---

## Verification Reports (`docs/verification/`)

기능 검증 및 테스트 보고서입니다.

| 문서 | 설명 |
|------|------|
| [SECURITY_PATCH_v1.3.2.md](verification/SECURITY_PATCH_v1.3.2.md) | v1.3.2 보안 패치 |
| [GEMINI_DEEP_RESEARCH_VERIFICATION.md](verification/GEMINI_DEEP_RESEARCH_VERIFICATION.md) | Gemini Deep Research 검증 |
| [MODEL_SELECTION_VERIFICATION.md](verification/MODEL_SELECTION_VERIFICATION.md) | 모델 선택 검증 |
| [WEBHOOK_NOTIFICATIONS_TEST.md](verification/WEBHOOK_NOTIFICATIONS_TEST.md) | 웹훅 알림 테스트 |
| [FULL_PIPELINE_TEST_20260113.md](verification/FULL_PIPELINE_TEST_20260113.md) | 전체 파이프라인 테스트 |
| [V131_TECH_DEBT_CLEANUP_TEST.md](verification/V131_TECH_DEBT_CLEANUP_TEST.md) | v1.3.1 기술 부채 정리 |
| [STORY_GENERATION_E2E_TEST.md](verification/STORY_GENERATION_E2E_TEST.md) | 스토리 생성 E2E 테스트 |
| [RELEASE_v1.2.1_SUMMARY.md](verification/RELEASE_v1.2.1_SUMMARY.md) | v1.2.1 릴리스 요약 |

---

## Audit Reports (`docs/audit/`)

구현 감사 보고서입니다.

| 문서 | 설명 |
|------|------|
| [IMPLEMENTATION_AUDIT.md](audit/IMPLEMENTATION_AUDIT.md) | 구현 상태 감사 보고서 |

---

## Archive (`docs/archive/`)

더 이상 활성화되지 않은 역사적 문서입니다.

### Archive Structure

```
docs/archive/
├── reports/           # 마이그레이션 및 분석 보고서
├── feature_docs/      # 기능별 설계 문서
├── v1_legacy/         # v1 레거시 문서
├── v2_design/         # v2 설계 문서
├── work_logs/         # 작업 로그
├── n8n_guides/        # n8n 가이드
├── n8n_workflows/     # n8n 워크플로우 파일
├── legacy_todo/       # 레거시 TODO 인덱스
└── raw_research/      # 원본 연구 자료
```

### When to Use Archive

- 역사적 맥락이 필요할 때
- 이전 결정의 이유를 파악할 때
- 레거시 시스템 이해가 필요할 때

---

## Quick Reference

### For New Contributors

1. [README.md](core/README.md) - 프로젝트 개요
2. [ARCHITECTURE.md](core/ARCHITECTURE.md) - 시스템 구조
3. [API.md](core/API.md) - API 사용법

### For Operations

1. [OPERATIONAL_STATUS.md](core/OPERATIONAL_STATUS.md) - 운영 상태
2. [runbook_24h_test.md](technical/runbook_24h_test.md) - 테스트 런북
3. [REGISTRY_BACKUP_GUIDE.md](technical/REGISTRY_BACKUP_GUIDE.md) - 백업 가이드

### For Development

1. [ROADMAP.md](core/ROADMAP.md) - 개발 계획
2. [decision_log.md](technical/decision_log.md) - 결정 로그
3. [canonical-data.md](data-model/canonical-data.md) - 데이터 스펙

---

## Maintenance

이 문서는 문서 구조 변경 시 업데이트되어야 합니다.

**관련 이슈:** #14
