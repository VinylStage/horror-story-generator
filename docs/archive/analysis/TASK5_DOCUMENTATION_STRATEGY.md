# TASK 5: 문서화 전략 및 통합 계획

**작성일:** 2026-01-12
**상태:** 제안 (Human confirmation required)

---

## 1. 현재 문서 현황

### 1.1 문서 위치 분산

| 위치 | 문서 수 | 상태 |
|------|---------|------|
| 루트 디렉토리 | 2 | 혼재 (README + Phase 문서) |
| `docs/` | ~10 | Phase 기반 명명, 일부 outdated |
| `docs/phase_b/` | 5 | 미구현 설계 문서 다수 |
| `phase1_foundation/` | 디렉토리별 | 데이터 자산과 혼재 |
| `phase2_execution/` | ? | 접근 불가 (확인 필요) |

### 1.2 문서 유형별 분류

| 유형 | 현재 상태 | 문제점 |
|------|----------|--------|
| 아키텍처 설명 | 분산 (PHASE_B_PLUS, 여러 Phase 문서) | 통합 뷰 부재 |
| API 레퍼런스 | TRIGGER_API.md | 최신 상태 |
| 스키마 정의 | Phase 문서에 분산 | 일관성 부족 |
| 가이드 | 부재 | Getting started 없음 |
| 변경 로그 | 부재 | 릴리스 히스토리 없음 |

---

## 2. 문서화 원칙

### 2.1 핵심 원칙

1. **Single Source of Truth**: 각 주제는 하나의 문서에서만 정의
2. **Phase 제거**: 모든 문서에서 Phase 기반 명명 제거
3. **버전 기반**: 변경 사항은 CHANGELOG에 버전별 기록
4. **유지보수 가능성**: 코드 변경 시 문서도 함께 업데이트

### 2.2 문서 대상 독자

| 문서 유형 | 대상 독자 | 작성 방향 |
|----------|----------|----------|
| README | 신규 사용자 | 빠른 시작, 핵심 기능 |
| 아키텍처 | 개발자/기여자 | 시스템 구조, 모듈 관계 |
| API 레퍼런스 | API 사용자 | 엔드포인트, 요청/응답 |
| CLI 레퍼런스 | CLI 사용자 | 명령어, 옵션 |
| 스키마 | 개발자 | 데이터 포맷 정의 |
| 가이드 | 사용자/운영자 | 단계별 절차 |

---

## 3. 목표 문서 구조

```
docs/
├── README.md                    # 문서 인덱스
│
├── architecture.md              # 시스템 아키텍처 (통합)
│   - 시스템 개요
│   - 모듈 구조
│   - 데이터 흐름
│   - 외부 의존성
│
├── api-reference.md             # API 레퍼런스 (TRIGGER_API 확장)
│   - 엔드포인트 목록
│   - 요청/응답 스키마
│   - 에러 코드
│   - 사용 예시
│
├── cli-reference.md             # CLI 레퍼런스 (신규)
│   - 스토리 생성 CLI
│   - 리서치 생성 CLI
│   - 옵션 설명
│
├── schemas/                     # 스키마 문서
│   ├── story.md                 # 스토리 출력 스키마
│   ├── research-card.md         # 리서치 카드 스키마
│   └── job.md                   # Job 메타데이터 스키마
│
├── guides/                      # 가이드 문서
│   ├── getting-started.md       # 빠른 시작 가이드
│   ├── configuration.md         # 설정 가이드
│   ├── deployment.md            # 배포 가이드
│   └── development.md           # 개발자 가이드
│
├── decisions/                   # 아키텍처 결정 기록 (ADR)
│   ├── 001-cli-as-source-of-truth.md
│   ├── 002-sqlite-for-dedup.md
│   └── 003-faiss-for-vector.md
│
└── changelog/                   # 변경 로그
    ├── CHANGELOG.md             # 통합 변경 로그
    └── releases/
        ├── v0.1.0.md
        ├── v0.2.0.md
        └── v0.3.0.md
```

---

## 4. 문서 통합 매핑

### 4.1 아키텍처 통합 (architecture.md)

**소스 문서:**
- `docs/PHASE_B_PLUS.md` (Phase B+ 아키텍처)
- `docs/PHASE2C_DEDUP_CONTROL.md` (중복 제어 아키텍처)
- `docs/phase_b/overview.md` (철학 - 선택적)

**통합 내용:**
```markdown
# 시스템 아키텍처

## 1. 개요
- 시스템 목적
- 핵심 기능 요약

## 2. 모듈 구조
- 스토리 생성 모듈
- 리서치 생성 모듈
- API 모듈
- 중복 제어 모듈

## 3. 데이터 흐름
- 스토리 생성 파이프라인
- 리서치 생성 파이프라인
- API 트리거 파이프라인

## 4. 외부 의존성
- Claude API
- Ollama
- SQLite
- FAISS

## 5. 설계 원칙
- CLI = Source of Truth
- Non-blocking API
- 파일 기반 저장소
```

### 4.2 스키마 통합

**story.md 소스:**
- `docs/PHASE2C_DEDUP_CONTROL.md` (canonical core)
- 실제 코드 (`story_saver.py`)

**research-card.md 소스:**
- `docs/phase_b/research_quality_schema.md`
- 실제 코드 (`validator.py`)

**job.md 소스:**
- `docs/TRIGGER_API.md` (Job 스키마)
- 실제 코드 (`job_manager.py`)

### 4.3 가이드 통합

**getting-started.md:**
- 기존 README 내용 확장
- 환경 설정 → configuration.md로 분리

**configuration.md:**
- 환경 변수 설명
- 경로 설정
- 외부 서비스 설정

**deployment.md (신규):**
- API 서버 배포
- Ollama 설정
- systemd 서비스 설정

---

## 5. Phase 문서 처리 전략

### 5.1 삭제 대상 (확인 후)

| 문서 | 삭제 사유 |
|------|----------|
| `docs/PHASE2C_RESEARCH_JOB.md` | SKELETON ONLY, research_executor로 대체됨 |
| `docs/phase_b/overview.md` | 미구현 철학, 필요시 ADR로 이관 |
| `docs/phase_b/future_vector_backend.md` | NOT STARTED 명시, 필요시 roadmap으로 이관 |
| `docs/phase_b/cultural_scope_strategy.md` | 미구현 가중치 로직 |

### 5.2 아카이브 대상

| 문서 | 아카이브 사유 |
|------|-------------|
| `PHASE1_IMPLEMENTATION_SUMMARY.md` | 역사 기록, 현재 동작과 무관 |
| `docs/PHASE2_PREPARATION_ANALYSIS.md` | IMMUTABLE REFERENCE, 분석 기록 |
| `docs/PHASE2A_TEMPLATE_ACTIVATION.md` | 전환 완료, 과정 기록 |
| `docs/PHASE2B_GENERATION_MEMORY.md` | 구현 완료, 초기 설계 기록 |

### 5.3 통합 후 삭제

| 문서 | 통합 대상 | 처리 |
|------|----------|------|
| `docs/PHASE_B_PLUS.md` | `architecture.md` | 통합 후 삭제 |
| `docs/PHASE2C_DEDUP_CONTROL.md` | `architecture.md` + `schemas/story.md` | 통합 후 삭제 |
| `docs/TRIGGER_API.md` | `api-reference.md` | 확장 후 대체 |
| `docs/phase_b/dedup_signal_policy.md` | `schemas/story.md` | 통합 후 삭제 |
| `docs/phase_b/research_quality_schema.md` | `schemas/research-card.md` | 통합 후 삭제 |

---

## 6. ADR (Architecture Decision Records) 제안

Phase 문서에 포함된 설계 결정 중 보존 가치가 있는 것들:

| ADR ID | 제목 | 출처 |
|--------|------|------|
| ADR-001 | CLI를 Source of Truth로 선택한 이유 | PHASE_B_PLUS |
| ADR-002 | SQLite를 중복 저장소로 선택한 이유 | PHASE2C_DEDUP |
| ADR-003 | FAISS를 벡터 백엔드로 선택한 이유 | PHASE_B_PLUS |
| ADR-004 | HIGH-only 블로킹 정책 결정 | PHASE2C_DEDUP |
| ADR-005 | Non-blocking API 설계 결정 | TRIGGER_API |

---

## 7. CHANGELOG 구조

### CHANGELOG.md 형식

```markdown
# Changelog

모든 주요 변경 사항이 이 파일에 기록됩니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따릅니다.

## [Unreleased]

### Added
- ...

### Changed
- ...

### Fixed
- ...

## [0.3.0] - 2026-01-12

### Added
- Ollama 기반 리서치 생성 기능
- FAISS 벡터 중복 체크
- FastAPI Trigger API
- PID 기반 Job 모니터링

### Changed
- 리서치 카드 스키마 v1.0 확정

## [0.2.0] - 2026-01-09

### Added
- SQLite 기반 스토리 레지스트리
- HIGH-only 블로킹 정책
- 템플릿 15개 활성화

## [0.1.0] - 2026-01-07

### Added
- 52개 Knowledge Unit
- 15개 Template Skeleton
- Canonical Dimension 체계
- 기본 프롬프트 빌더
```

---

## 8. Human Confirmation Required

| 항목 | 확인 필요 사유 |
|------|---------------|
| ADR 도입 여부 | 설계 결정 기록을 별도 유지할지 |
| 한국어 vs 영어 문서 | 일부 문서 한국어, 일부 영어 혼재 처리 방향 |
| CHANGELOG 형식 | Keep a Changelog 형식 채택 여부 |
| 삭제 대상 최종 확인 | 각 Phase 문서 삭제 전 마지막 확인 |

---

**문서 끝**
