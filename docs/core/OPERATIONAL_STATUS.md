# 운영 상태 선언

**버전:** v1.4.1 <!-- x-release-please-version -->
**상태:** OPERATIONAL
**선언일:** 2026-01-13

---

## 현재 상태

이 릴리스는 **운영 승인**되었습니다.

모든 검증 축이 통과되었으며, 전체 파이프라인 스모크 테스트가 완료되었습니다.

---

## 보장 사항

### 1. 통합 파이프라인

| 기능 | 상태 |
|------|------|
| 연구 카드 자동 선택 | 보장됨 |
| 템플릿 affinity 기반 매칭 | 보장됨 |
| 스토리 프롬프트 주입 | 보장됨 |
| 메타데이터 추적성 | 보장됨 |

### 2. 중복 검사

| 레벨 | 방식 | 상태 |
|------|------|------|
| 연구 카드 | FAISS 시맨틱 (nomic-embed-text) | 보장됨 |
| 스토리 | SHA256 시그니처 | 보장됨 |
| 스토리 | 시맨틱 임베딩 (하이브리드, v1.4.0) | 보장됨 |

### 3. Canonical 무결성

| 항목 | 상태 |
|------|------|
| 5차원 정규화 | 보장됨 |
| 템플릿↔연구 카드 일관성 | 보장됨 |
| 스토리 시그니처 결정성 | 보장됨 |
| 스토리 CK 추출 | 보장됨 |
| 템플릿↔스토리 CK 정렬 점수 | 보장됨 |

### 4. 데이터 이식성

| 항목 | 상태 |
|------|------|
| 환경 변수 기반 설정 | 보장됨 |
| 파일 시스템 기반 저장 | 보장됨 |
| SQLite 레지스트리 | 보장됨 |
| 마이그레이션 전 백업 | 보장됨 |

---

## 설정 가능 항목

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `AUTO_INJECT_RESEARCH` | `true` | 연구 카드 자동 주입 |
| `RESEARCH_INJECT_TOP_K` | `1` | 주입할 연구 카드 수 |
| `RESEARCH_INJECT_REQUIRE` | `false` | 연구 카드 필수 여부 |
| `RESEARCH_INJECT_EXCLUDE_DUP_LEVEL` | `HIGH` | 제외할 중복 레벨 |
| `ENABLE_STORY_DEDUP` | `true` | 스토리 레벨 중복 검사 |
| `STORY_DEDUP_STRICT` | `false` | 중복 시 생성 중단 |

### 스토리 시맨틱 중복 검사 (v1.4.0)

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `ENABLE_STORY_SEMANTIC_DEDUP` | `true` | 시맨틱 임베딩 기반 중복 검사 |
| `STORY_SEMANTIC_THRESHOLD` | `0.85` | 시맨틱 HIGH 신호 기준점 |
| `STORY_HYBRID_THRESHOLD` | `0.85` | 하이브리드 중복 판정 기준점 |
| `STORY_HYBRID_CANONICAL_WEIGHT` | `0.3` | 하이브리드 canonical 가중치 |
| `STORY_HYBRID_SEMANTIC_WEIGHT` | `0.7` | 하이브리드 semantic 가중치 |

### 스토리 Canonical Key 추출 설정

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `ENABLE_STORY_CK_EXTRACTION` | `true` | 스토리 CK 추출 활성화 |
| `STORY_CK_MODEL` | (없음) | 추출용 모델 오버라이드 |

> **Note:** 스토리 CK 추출은 생성된 텍스트에서 canonical 차원을 LLM으로 분석합니다.
> 템플릿 CK와 비교하여 정렬 점수(alignment score)를 메타데이터에 기록합니다.

### 벡터 백엔드 설정 (v1.4.0)

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `VECTOR_BACKEND_ENABLED` | `true` | 벡터 기반 연구 카드 검색/클러스터링 활성화 |

> **Note:** 벡터 백엔드는 Ollama (nomic-embed-text)와 FAISS를 사용합니다.
> `init_vector_backend()`, `generate_embedding()`, `vector_search_research_cards()`,
> `compute_semantic_affinity()`, `cluster_research_cards()` 함수를 제공합니다.

### 경로 설정 (v1.3.1)

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `NOVEL_OUTPUT_DIR` | `data/novel` | 스토리 출력 디렉토리 |
| `JOB_DIR` | `jobs/` | 작업 파일 디렉토리 |

### 작업 정리 설정 (v1.3.1)

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `JOB_PRUNE_ENABLED` | `false` | 자동 작업 정리 활성화 |
| `JOB_PRUNE_DAYS` | `30` | N일 이상 된 작업 정리 |
| `JOB_PRUNE_MAX_COUNT` | `1000` | 최대 N개 최근 작업 유지 |

---

## 명시적 범위 외 (향후 작업)

다음 기능은 v1.3.2에 **포함되지 않습니다**:

| 기능 | 상태 |
|------|------|
| 스토리 품질 검증 | 미구현 |
| 플랫폼 자동 업로드 | 미구현 |
| 분산 실행 | 미구현 |
| 웹 UI | 미구현 |
| 실시간 모니터링 대시보드 | 미구현 |

---

## 검증 보고서

| 보고서 | 위치 |
|--------|------|
| 통합 파이프라인 검증 | `docs/analysis/UNIFIED_PIPELINE_FINAL_VERIFICATION.md` |
| 스토리 중복 검사 검증 | `docs/analysis/STORY_DEDUP_FINAL_VERIFICATION.md` |
| 전체 파이프라인 스모크 테스트 | `docs/analysis/FINAL_PIPELINE_SMOKE_TEST.md` |
| 모델 선택 검증 | `docs/verification/MODEL_SELECTION_VERIFICATION.md` |
| Gemini Deep Research 검증 | `docs/verification/GEMINI_DEEP_RESEARCH_VERIFICATION.md` |
| 전체 파이프라인 테스트 (v1.2.0) | `docs/verification/FULL_PIPELINE_TEST_20260113.md` |
| 스토리 생성 E2E 테스트 (v1.2.1) | `docs/verification/STORY_GENERATION_E2E_TEST.md` |

---

## 운영 주의사항

### API 서버 시작 오류

API 서버 초기 시작 시 실패할 수 있습니다:
- 포트 이미 사용 중 (이전 프로세스 미종료)
- 환경 변수 미로드 (`.env` 파일 누락)

**해결:** `pkill -f uvicorn` 후 재시작하거나, `.env` 파일 확인 후 재시작

### 환경 변수 변경 시 재시작 필요

`.env` 파일의 환경 변수는 **서버 시작 시 1회만 로드**됩니다.

환경 변수 변경 후에는 반드시 uvicorn을 재시작해야 적용됩니다:

```bash
# API 서버 재시작
pkill -f uvicorn
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**영향받는 변수:** `GOOGLE_AI_MODEL`, `GEMINI_API_KEY`, `GEMINI_ENABLED` 등

> **팁:** 모델을 변경할 경우, 환경 변수 대신 API 호출 시 `model` 파라미터로 명시적 지정 가능:
> ```bash
> curl -X POST .../research/run -d '{"topic": "...", "model": "gemini:gemma-3-27b-it"}'
> ```

---

## 운영 가이드

| 문서 | 용도 |
|------|------|
| `README.md` | 빠른 시작 |
| `docs/core/ARCHITECTURE.md` | 시스템 아키텍처 |
| `docs/technical/runbook_24h_test.md` | 24시간 테스트 절차 |
| `docs/technical/REGISTRY_BACKUP_GUIDE.md` | 백업 및 복구 |

---

## 선언

이 문서는 v1.3.2의 운영 계약입니다.

문서에 명시되지 않은 동작은 보장되지 않습니다.

---

**검증자:** Claude Opus 4.5
**태그:** v1.3.2

---

## 보안 패치 이력

| 버전 | 날짜 | CVE | 설명 |
|------|------|-----|------|
| v1.3.2 | 2026-01-13 | CVE-2025-27600, CVE-2024-47874 | Starlette DoS 취약점 수정 |
