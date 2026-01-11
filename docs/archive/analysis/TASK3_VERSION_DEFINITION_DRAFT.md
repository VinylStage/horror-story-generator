# TASK 3: VERSION_DEFINITION.md (Draft)

**작성일:** 2026-01-12
**상태:** 초안 (Human confirmation required)
**대상 버전:** v0.3.0

---

## 1. 버전 정의 철학

### 1.1 Phase 기반 → Version 기반 전환

| 이전 방식 (Phase) | 새 방식 (Version) |
|------------------|------------------|
| Phase 1, 2A, 2B, 2C, B+ | Semantic Versioning (MAJOR.MINOR.PATCH) |
| 순차적 개발 단계 표현 | 기능 완성도 및 호환성 표현 |
| 문서 분산 (각 Phase별 문서) | 릴리스 노트 중심 통합 |

### 1.2 Semantic Versioning 규칙

```
MAJOR.MINOR.PATCH

MAJOR: 호환성 깨지는 변경 (API, 데이터 포맷)
MINOR: 새 기능 추가 (하위 호환 유지)
PATCH: 버그 수정, 문서 개선
```

---

## 2. 버전 히스토리 (역추적)

### v0.1.0 - Foundation (Phase 1 해당)
**포함 기능:**
- 52개 Knowledge Unit 정의
- 15개 Template Skeleton 정의
- Canonical Dimension 체계
- 기본 프롬프트 빌더

**데이터 자산:**
- `knowledge_units/` (52 JSON)
- `templates/` (15 JSON)

---

### v0.2.0 - Generation Memory (Phase 2A-2C 해당)
**포함 기능:**
- 템플릿 활성화 (T-APT-001 등 15개)
- 인메모리 유사도 관찰
- SQLite 기반 스토리 레지스트리
- HIGH-only 블로킹 정책
- Claude API 통합

**데이터 자산:**
- `data/stories.db` (SQLite)
- `generated_stories/` (출력)

---

### v0.3.0 - Research Integration (Phase B+ 및 Trigger API 해당) [현재]

**포함 기능:**
- Ollama 기반 리서치 생성
- FAISS 벡터 중복 체크
- Story Seeds 시스템
- Research Card 스키마
- FastAPI Trigger API
- PID 기반 Job 모니터링
- 비동기 작업 실행

**데이터 자산:**
- `data/research_registry.db` (SQLite)
- `data/research/` (리서치 카드)
- `jobs/` (Job 메타데이터)
- `logs/` (실행 로그)

**신규 진입점:**
- `python -m research_executor run`
- `uvicorn research_api.main:app`

---

## 3. v0.3.0 상세 정의

### 3.1 기능 목록 (Features)

| 기능 ID | 기능명 | 상태 | 설명 |
|---------|--------|------|------|
| F-STORY-GEN | 스토리 생성 | **구현 완료** | Claude API 기반 공포 스토리 생성 |
| F-TEMPLATE | 템플릿 시스템 | **구현 완료** | 15개 스켈레톤 기반 프롬프트 구성 |
| F-STORY-DEDUP | 스토리 중복 체크 | **구현 완료** | Canonical matching + SQLite |
| F-RESEARCH-GEN | 리서치 생성 | **구현 완료** | Ollama 기반 리서치 카드 생성 |
| F-RESEARCH-DEDUP | 리서치 중복 체크 | **구현 완료** | FAISS 벡터 유사도 |
| F-TRIGGER-API | Trigger API | **구현 완료** | Non-blocking job 실행 |
| F-JOB-MONITOR | Job 모니터링 | **구현 완료** | PID 추적, 상태 업데이트 |
| F-WEBHOOK | Webhook 통합 | **미구현** | 향후 v0.4.0 |
| F-N8N | n8n 통합 | **미구현** | 향후 v0.4.0 |

### 3.2 API 엔드포인트 (v0.3.0)

| Method | Path | 상태 |
|--------|------|------|
| POST | `/jobs/story/trigger` | **구현 완료** |
| POST | `/jobs/research/trigger` | **구현 완료** |
| GET | `/jobs/{job_id}` | **구현 완료** |
| GET | `/jobs` | **구현 완료** |
| POST | `/jobs/{job_id}/cancel` | **구현 완료** |
| POST | `/jobs/monitor` | **구현 완료** |
| POST | `/jobs/{job_id}/dedup_check` | **구현 완료** |

### 3.3 CLI 명령어 (v0.3.0)

```bash
# 스토리 생성
python main.py [--max-stories N] [--enable-dedup] [--db-path PATH]

# 리서치 생성
python -m research_executor run <topic> [--tags TAG...] [--model MODEL]

# API 서버
uvicorn research_api.main:app --host 0.0.0.0 --port 8000
```

### 3.4 데이터 스키마 (v0.3.0)

#### Story Output
```json
{
  "story_id": "string",
  "title": "string",
  "content": "string",
  "canonical_core": {
    "setting": "string",
    "primary_fear": "string",
    "antagonist": "string",
    "mechanism": "string"
  },
  "template_id": "string",
  "created_at": "ISO8601"
}
```

#### Research Card
```json
{
  "card_id": "string",
  "version": "1.0",
  "metadata": { "model": "string", "status": "string" },
  "output": {
    "title": "string",
    "summary": "string",
    "key_concepts": ["string"],
    "horror_applications": ["string"],
    "canonical_affinity": { ... }
  },
  "validation": { "quality_score": "string" }
}
```

#### Job Metadata
```json
{
  "job_id": "string",
  "type": "story_generation | research",
  "status": "queued | running | succeeded | failed | cancelled",
  "pid": "number",
  "log_path": "string",
  "artifacts": ["string"],
  "created_at": "ISO8601"
}
```

---

## 4. 향후 버전 로드맵

### v0.4.0 - Workflow Integration (예정)
- Webhook on job completion
- n8n 통합 예제
- 배치 작업 트리거

### v0.5.0 - Vector Enhancement (예정)
- 스토리 임베딩 기반 중복 체크
- 크로스-모달 유사도 검색
- 벡터 인덱스 최적화

### v1.0.0 - Production Ready (예정)
- 안정화된 API 스키마
- 완전한 테스트 커버리지
- 프로덕션 배포 가이드

---

## 5. 호환성 정책

### 5.1 하위 호환성

| 버전 전환 | 호환성 |
|----------|--------|
| v0.2.x → v0.3.x | **호환** (기존 스토리 DB 유지) |
| v0.3.x → v0.4.x | **호환 예정** |

### 5.2 Breaking Changes 예고

v1.0.0 릴리스 전 다음 변경 예정:
- 디렉토리 구조 재편 (`phase1_foundation/` 제거)
- 레거시 데이터 포맷 제거 (`research_cards.jsonl`)
- API 스키마 확정

---

## 6. Human Confirmation Required

| 항목 | 확인 필요 사유 |
|------|---------------|
| 버전 번호 체계 (v0.3.0) | 현재 상태를 v0.3.0으로 정의하는 것이 적절한지 |
| 역추적 버전 (v0.1.0, v0.2.0) | 과거 상태를 이렇게 정의해도 되는지 |
| 향후 로드맵 (v0.4.0+) | 우선순위 및 기능 범위 확인 |

---

**문서 끝**
