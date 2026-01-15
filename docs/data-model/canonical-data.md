# Canonical Data Structures Specification

**Version:** 1.0
**Last Updated:** 2026-01-14
**Status:** Active

---

## Overview

이 문서는 Horror Story Generator 시스템에서 사용되는 핵심 데이터 구조를 정의합니다. 모든 데이터 구조는 구현 코드와 동기화되어 있습니다.

---

## 1. Research Card

Research Card는 공포 연구 주제에 대한 LLM 분석 결과를 저장하는 기본 단위입니다.

### 1.1 저장 위치

```
data/research/YYYY/MM/RC-YYYYMMDD-HHMMSS.json
```

### 1.2 스키마

```json
{
  "card_id": "string (required)",
  "version": "string (required, default: '1.0')",
  "metadata": {
    "created_at": "ISO 8601 datetime (required)",
    "model": "string (required)",
    "generation_time_ms": "integer (required)",
    "prompt_tokens_est": "integer (optional)",
    "output_tokens_est": "integer (optional)",
    "status": "enum: complete | error (required)",
    "provider": "enum: ollama | gemini (required)",
    "execution_mode": "string (optional, deep_research only)",
    "interaction_id": "string (optional, deep_research only)"
  },
  "input": {
    "topic": "string (required)",
    "tags": "string[] (required, may be empty)"
  },
  "output": {
    "title": "string (required)",
    "summary": "string (required)",
    "key_concepts": "string[] (required)",
    "horror_applications": "string[] (required)",
    "canonical_affinity": {
      "setting": "string[] (optional)",
      "primary_fear": "string[] (optional)",
      "antagonist": "string[] (optional)",
      "mechanism": "string[] (optional)"
    },
    "raw_response": "string (required)"
  },
  "validation": {
    "has_title": "boolean (required)",
    "has_summary": "boolean (required)",
    "has_concepts": "boolean (required)",
    "has_applications": "boolean (required)",
    "canonical_parsed": "boolean (required)",
    "quality_score": "enum: good | acceptable | poor (required)",
    "parse_error": "string | null (required)"
  },
  "canonical_core": {
    "setting_archetype": "string (required if present)",
    "primary_fear": "string (required if present)",
    "antagonist_archetype": "string (required if present)",
    "threat_mechanism": "string (required if present)",
    "twist_family": "string (required if present)"
  },
  "dedup": {
    "similarity_score": "float 0.0-1.0 (required if present)",
    "level": "enum: LOW | MEDIUM | HIGH (required if present)",
    "nearest_card_id": "string | null (required if present)"
  }
}
```

### 1.3 예제

```json
{
  "card_id": "RC-20260114-005317",
  "version": "1.0",
  "metadata": {
    "created_at": "2026-01-14T00:53:17.273913",
    "model": "gemma-3-27b-it",
    "generation_time_ms": 12788,
    "prompt_tokens_est": 331,
    "output_tokens_est": 325,
    "status": "complete",
    "provider": "gemini"
  },
  "input": {
    "topic": "Japanese Neapolitan-style Urban Legend",
    "tags": ["Creepypasta", "RulesHorror"]
  },
  "output": {
    "title": "Neapolitan Urban Legend: The Vanishing Pedestrians",
    "summary": "The Japanese Neapolitan urban legend describes pedestrians disappearing after being offered a ride by a phantom car...",
    "key_concepts": [
      "phantom vehicle",
      "vanishing individuals",
      "urban vulnerability",
      "unseen observers",
      "collective memory"
    ],
    "horror_applications": [
      "A character repeatedly sees the car, but no one else does, questioning their sanity.",
      "The car's driver isn't malicious, but the 'ride' leads to a subtle, insidious erasure of the passenger's identity.",
      "A community investigates a pattern of disappearances, uncovering a disturbing social or infrastructural issue masked by the legend."
    ],
    "canonical_affinity": {
      "setting": ["urban", "liminal", "infrastructure", "domestic_space"],
      "primary_fear": ["loss_of_autonomy", "annihilation", "identity_erasure", "isolation"],
      "antagonist": ["system", "unknown", "collective"],
      "mechanism": ["erosion", "impersonation", "surveillance", "exploitation"]
    },
    "raw_response": "```json\n{...}\n```"
  },
  "validation": {
    "has_title": true,
    "has_summary": true,
    "has_concepts": true,
    "has_applications": true,
    "canonical_parsed": true,
    "quality_score": "good",
    "parse_error": null
  },
  "canonical_core": {
    "setting_archetype": "liminal",
    "primary_fear": "annihilation",
    "antagonist_archetype": "system",
    "threat_mechanism": "erosion",
    "twist_family": "inevitability"
  },
  "dedup": {
    "similarity_score": 0.0,
    "level": "LOW",
    "nearest_card_id": null
  }
}
```

### 1.4 관련 코드

| 파일 | 역할 |
|------|------|
| `src/research/executor/output_writer.py` | JSON 구조 빌드 및 저장 |
| `src/research/executor/validator.py` | 검증 로직 |
| `src/research/executor/canonical_collapse.py` | affinity → core 변환 |

---

## 2. Canonical Core

Canonical Core는 공포 이야기의 본질적 구조를 5개 차원으로 정의합니다.

### 2.1 JSON Schema

**위치:** `schema/canonical_key.schema.json`

### 2.2 차원 정의

#### setting_archetype (공간 원형)

| 값 | 설명 |
|----|------|
| `apartment` | 공동 주거 공간 |
| `hospital` | 의료 공간 |
| `rural` | 시골/외딴 지역 |
| `domestic_space` | 안전해야 할 집 |
| `digital` | 온라인/가상 공간 |
| `liminal` | 전이 공간 (백룸 등) |
| `infrastructure` | 사회 기반시설 |
| `body` | 인체 자체가 공간 |
| `abstract` | 물리 공간 없음 |

#### primary_fear (핵심 공포)

| 값 | 설명 |
|----|------|
| `loss_of_autonomy` | 통제력 상실 |
| `identity_erasure` | 정체성 상실 |
| `social_displacement` | 사회적 배제 |
| `contamination` | 오염/침식 |
| `isolation` | 완전한 고립 |
| `annihilation` | 존재 소멸 |

#### antagonist_archetype (적대 원형)

| 값 | 설명 |
|----|------|
| `ghost` | 초자연 존재 |
| `system` | 제도/조직/구조 |
| `technology` | 기술/AI/기계 |
| `body` | 신체 내부 위협 |
| `collective` | 군중/공동체 |
| `unknown` | 정체 불명 |

#### threat_mechanism (위협 메커니즘)

| 값 | 설명 |
|----|------|
| `surveillance` | 감시/노출 |
| `possession` | 빙의/장악 |
| `debt` | 빚/의무/계약 |
| `infection` | 감염/확산 |
| `impersonation` | 대체/위장 |
| `confinement` | 물리/심리적 구속 |
| `erosion` | 점진적 붕괴 |
| `exploitation` | 착취/수탈 |

#### twist_family (결말 구조)

| 값 | 설명 |
|----|------|
| `revelation` | 숨겨진 진실 드러남 |
| `inevitability` | 탈출 불가 |
| `inversion` | 역할/의미 뒤집힘 |
| `circularity` | 끝이 시작 |
| `self_is_monster` | 내가 가해자 |
| `ambiguity` | 해석 불가 결말 |

### 2.3 Collapse 규칙

`canonical_affinity` (다중값)에서 `canonical_core` (단일값)로 변환할 때:

1. **우선순위**: `primary_fear`는 아래 순서로 선택
   - `annihilation` > `identity_erasure` > `loss_of_autonomy` > `isolation` > `social_displacement` > `contamination`

2. **첫 번째 유효값**: 다른 차원은 첫 번째 유효한 값 사용

3. **기본값**:
   - `setting_archetype`: `abstract`
   - `primary_fear`: `isolation`
   - `antagonist_archetype`: `unknown`
   - `threat_mechanism`: `erosion`
   - `twist_family`: `inevitability`

### 2.4 관련 코드

**파일:** `src/research/executor/canonical_collapse.py:104-149`

---

## 3. Story Registry Record

스토리 중복 제거를 위한 영구 저장소 레코드입니다.

### 3.1 저장 위치

```
data/story_registry.db (SQLite)
```

### 3.2 스키마 (v1.1.0)

```sql
CREATE TABLE stories (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT,
    template_id TEXT,
    template_name TEXT,
    semantic_summary TEXT NOT NULL,
    similarity_method TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    decision_reason TEXT NOT NULL,
    source_run_id TEXT,
    story_signature TEXT,
    canonical_core_json TEXT,
    research_used_json TEXT
);
```

### 3.3 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | TEXT | 스토리 ID (타임스탬프 기반) |
| `created_at` | TEXT | ISO 8601 생성 시간 |
| `title` | TEXT | 스토리 제목 |
| `template_id` | TEXT | 사용된 템플릿 ID |
| `template_name` | TEXT | 템플릿 이름 |
| `semantic_summary` | TEXT | 시맨틱 요약 (중복 비교용) |
| `similarity_method` | TEXT | 유사도 계산 방법 |
| `accepted` | INTEGER | 수락 여부 (0/1) |
| `decision_reason` | TEXT | 결정 사유 |
| `source_run_id` | TEXT | 실행 ID |
| `story_signature` | TEXT | SHA256 시그니처 (v1.1.0) |
| `canonical_core_json` | TEXT | canonical_core JSON (v1.1.0) |
| `research_used_json` | TEXT | 사용된 리서치 카드 IDs (v1.1.0) |

### 3.4 관련 코드

**파일:** `src/registry/story_registry.py`

---

## 4. Research Registry Record

리서치 카드 메타데이터 추적용 레지스트리입니다.

### 4.1 저장 위치

```
data/research/registry.sqlite (SQLite)
```

### 4.2 스키마

```sql
CREATE TABLE research_cards (
    card_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    embedding_indexed INTEGER DEFAULT 0,
    dedup_score REAL DEFAULT 0.0,
    dedup_signal TEXT DEFAULT 'LOW',
    status TEXT DEFAULT 'pending'
);
```

### 4.3 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `card_id` | TEXT | 카드 ID (`RC-YYYYMMDD-HHMMSS`) |
| `topic` | TEXT | 연구 주제 |
| `created_at` | TIMESTAMP | 생성 시간 |
| `file_path` | TEXT | JSON 파일 경로 |
| `embedding_indexed` | INTEGER | FAISS 인덱싱 여부 |
| `dedup_score` | REAL | 유사도 점수 |
| `dedup_signal` | TEXT | 중복 신호 레벨 |
| `status` | TEXT | 상태 (pending/completed/failed) |

### 4.4 관련 코드

**파일:** `src/registry/research_registry.py`

---

## 5. FAISS Vector Index

리서치 카드 임베딩 벡터 저장소입니다.

### 5.1 저장 위치

```
data/research/vectors/research.faiss    # FAISS 인덱스
data/research/vectors/metadata.json     # 메타데이터 매핑
```

### 5.2 메타데이터 구조

```json
{
  "dimension": 768,
  "id_to_card": {
    "0": "RC-20260111-174048",
    "1": "RC-20260112-082330"
  },
  "card_to_id": {
    "RC-20260111-174048": 0,
    "RC-20260112-082330": 1
  }
}
```

### 5.3 임베딩 모델

- **모델:** `nomic-embed-text` (Ollama)
- **차원:** 768
- **정규화:** L2 (코사인 유사도용)

### 5.4 관련 코드

| 파일 | 역할 |
|------|------|
| `src/dedup/research/index.py` | FAISS 인덱스 관리 |
| `src/dedup/research/embedder.py` | 임베딩 생성 |

---

## 6. Job Record

비동기 작업 관리용 레코드입니다.

### 6.1 저장 위치

```
jobs/{job_id}.json
```

### 6.2 스키마

```json
{
  "job_id": "string (required)",
  "type": "enum: story_generation | research_generation (required)",
  "status": "enum: queued | running | succeeded | failed | cancelled (required)",
  "pid": "integer | null",
  "log_path": "string (required)",
  "artifacts": "string[] (required)",
  "created_at": "ISO 8601 datetime (required)",
  "started_at": "ISO 8601 datetime | null",
  "completed_at": "ISO 8601 datetime | null",
  "webhook_url": "URL string | null",
  "webhook_sent": "boolean"
}
```

### 6.3 관련 코드

**파일:** `src/infra/job_manager.py`

---

## 7. Story Canonical Extraction

스토리 텍스트에서 추출된 Canonical Key 데이터 구조입니다.

### 7.1 개요

스토리 생성 후, LLM이 생성된 텍스트를 분석하여 5개 canonical 차원을 추출합니다. 이는 템플릿의 `canonical_core`와 독립적으로 "실제 작성된 내용"을 반영합니다.

### 7.2 저장 위치

스토리 메타데이터 JSON 내부:

```
data/novel/horror_story_YYYYMMDD_HHMMSS_metadata.json
└── story_canonical_extraction: {...}
```

### 7.3 스키마

```json
{
  "story_canonical_extraction": {
    "canonical_core": {
      "setting_archetype": "string (required)",
      "primary_fear": "string (required)",
      "antagonist_archetype": "string (required)",
      "threat_mechanism": "string (required)",
      "twist_family": "string (required)"
    },
    "canonical_affinity": {
      "setting": "string[] (required)",
      "primary_fear": "string[] (required)",
      "antagonist": "string[] (required)",
      "mechanism": "string[] (required)",
      "twist": "string[] (optional)"
    },
    "analysis_notes": "string (optional)",
    "extraction_model": "string (required)",
    "story_truncated": "boolean (required)",
    "template_comparison": {
      "match_score": "float 0.0-1.0 (required)",
      "match_count": "integer (required)",
      "total_dimensions": "integer (required, always 5)",
      "matches": "string[] (required)",
      "divergences": [
        {
          "dimension": "string (required)",
          "template": "string (required)",
          "story": "string (required)"
        }
      ]
    }
  }
}
```

### 7.4 예제

```json
{
  "story_canonical_extraction": {
    "canonical_core": {
      "setting_archetype": "apartment",
      "primary_fear": "social_displacement",
      "antagonist_archetype": "collective",
      "threat_mechanism": "surveillance",
      "twist_family": "inevitability"
    },
    "canonical_affinity": {
      "setting": ["apartment", "domestic_space"],
      "primary_fear": ["social_displacement", "isolation"],
      "antagonist": ["collective", "system"],
      "mechanism": ["surveillance", "confinement"],
      "twist": ["inevitability"]
    },
    "analysis_notes": "Social horror in apartment setting with collective antagonism",
    "extraction_model": "claude-sonnet-4-5-20250929",
    "story_truncated": false,
    "template_comparison": {
      "match_score": 0.8,
      "match_count": 4,
      "total_dimensions": 5,
      "matches": [
        "setting_archetype",
        "primary_fear",
        "threat_mechanism",
        "twist_family"
      ],
      "divergences": [
        {
          "dimension": "antagonist_archetype",
          "template": "system",
          "story": "collective"
        }
      ]
    }
  }
}
```

### 7.5 정렬 점수 계산

```
alignment_score = matches / 5 × 100%
```

- **100%**: 모든 차원이 템플릿과 일치
- **80%**: 4/5 차원 일치
- **60%**: 3/5 차원 일치
- **40% 이하**: 상당한 divergence 발생

### 7.6 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ENABLE_STORY_CK_EXTRACTION` | `true` | 추출 활성화 |
| `STORY_CK_MODEL` | (없음) | 추출용 모델 오버라이드 |

### 7.7 관련 코드

| 파일 | 역할 |
|------|------|
| `src/story/canonical_extractor.py` | 추출 로직 |
| `src/story/generator.py` | 통합 및 호출 |

---

## Version History

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.1 | 2026-01-15 | Story Canonical Extraction 섹션 추가 |
| 1.0 | 2026-01-14 | 초기 문서 작성 |
