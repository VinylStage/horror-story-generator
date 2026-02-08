# System Architecture

**Status:** Active
**Version:** v1.7.0 <!-- x-release-please-version -->

---

## Overview

The Horror Story Generator is a multi-pipeline content generation system with three execution paths:

1. **Story Generation** - Claude API-based horror story creation
2. **Research Generation** - Ollama-based research card creation
3. **Task Scheduler** - Queue-based task execution via HTTP API

All pipelines share common infrastructure for deduplication, storage, and monitoring.

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Entry["Entry Points"]
        API["uvicorn src.api.main:app<br/>(API Server)"]
    end

    subgraph Core["Core Generators"]
        SG["HorrorStory<br/>Generator"]
        RG["Research<br/>Generator"]
        Scheduler["Task Scheduler<br/>(SQLite Queue)"]
    end

    subgraph External["External APIs"]
        Claude["Claude API<br/>(api_client)"]
        Ollama["Ollama API<br/>(ollama_client)"]
    end

    subgraph Infra["Shared Infrastructure"]
        StoryReg["Story Registry<br/>(SQLite)"]
        ResDedup["Research Dedup<br/>(FAISS + SQLite)"]
    end

    subgraph Storage["Storage Layer"]
        DS["data/stories/<br/>stories.db"]
        DR["data/research/<br/>research_registry.db"]
        TaskDB["data/<br/>scheduler.db"]
    end

    API --> Scheduler
    API --> SG
    API --> RG

    Scheduler --> SG
    Scheduler --> RG

    SG --> Claude
    RG --> Ollama

    Claude --> StoryReg
    Ollama --> ResDedup

    StoryReg --> DS
    ResDedup --> DR
    Scheduler --> TaskDB
```

---

## Pipeline 1: Story Generation

### Flow

```mermaid
flowchart LR
    A["Template Selection<br/>template_loader.py"] --> B["Research Selection<br/>research_context/"]
    B --> C["Prompt Construction<br/>prompt_builder.py"]
    C --> D["Claude API Call<br/>api_client.py"]
    D --> CK["Story CK Extraction<br/>canonical_extractor.py"]
    CK --> E{"Dedup Check<br/>enabled?"}
    E -->|No| G["Save Story<br/>generator.py"]
    E -->|Yes| F{"Signal?"}
    F -->|LOW/MED| G
    F -->|HIGH| H{"Retry<br/>< 2?"}
    H -->|Yes| C
    H -->|No| I["Skip"]
    G --> J["Record in SQLite<br/>story_registry.py"]
```

### Topic-Based Generation (v1.2.0+)

When a topic is provided, the generator uses a different flow:

```mermaid
flowchart LR
    A["Topic Input"] --> B{"Research Card<br/>Exists?"}
    B -->|Yes| C["Use Existing<br/>Card"]
    B -->|No| D{"auto_research<br/>enabled?"}
    D -->|Yes| E["Generate New<br/>Research"]
    D -->|No| F["No Research<br/>Context"]
    E --> C
    C --> G["Template Selection"]
    F --> G
    G --> H["Story Generation"]
```

### Output Format (v1.6.1+)

**Filename Convention**:
- Markdown: `story-{timestamp}.md` (hyphens, not underscores)
- Metadata: `story-{timestamp}_metadata.json`
- Example: `story-20260118-183713.md`

**Frontmatter Structure**:
1. Core: title, slug, category
2. Temporal: date (quoted ISO format)
3. Content: excerpt, tags (YAML array)
4. Reading: readTime, featured, thumbnail
5. System: genre, wordCount, model, temperature, draft

**Field Calculation**:
- `slug`: `story-{timestamp}` (hyphens)
- `excerpt`: First 200 chars (escaped)
- `readTime`: `round(wordCount / 200)` min (min 1)
- `tags`: YAML array format

**Topic Matching:**
1. Search cards by topic keyword (exact match > partial match > title match)
2. If no match and `auto_research=True`, generate new research via `run_research_pipeline()`
3. Use matched/generated research card for story context

**Auto-Research 실패 시 동작:**
- auto-research가 실패하거나 예외가 발생하면 **경고를 로깅**하고 스토리 생성을 계속합니다
- 연구 카드 없이 템플릿 기반으로만 스토리를 생성합니다
- 단, `RESEARCH_INJECT_REQUIRE=true`인 경우 연구 카드가 없으면 생성이 중단됩니다

**API Entry Point:** `POST /story/generate` (blocking) or `POST /tasks` with type `"story"` (non-blocking, scheduler-based)

### Research Auto-Injection (Default: ON)

Story generation automatically selects and injects matching research cards:

1. **Selection**: Uses `select_research_for_template()` from `src/infra/research_context/`
2. **Affinity Scoring**: Matches template's `canonical_core` against research `canonical_affinity`
3. **Dedup Filter**: Excludes HIGH-dedup cards by default (configurable)
4. **Injection**: Adds research context to system prompt

**Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `AUTO_INJECT_RESEARCH` | `true` | Enable/disable auto-injection |
| `RESEARCH_INJECT_TOP_K` | `1` | Number of cards to inject |
| `RESEARCH_INJECT_REQUIRE` | `false` | Fail if no research matches |
| `RESEARCH_INJECT_EXCLUDE_DUP_LEVEL` | `HIGH` | Exclude HIGH/MEDIUM duplicates |

**Traceability**: Story metadata includes `research_used` field listing injected card IDs.

### Story-Level Deduplication

Story-level dedup prevents structurally duplicated stories even with cosmetic variations.

#### Signature-Based Dedup (v1.0+)

**Story Signature:**
```
canonical_core + research_used → SHA256 hash
```

**Detection Flow:**
```mermaid
flowchart LR
    A["Template + Research<br/>Selection"] --> B["Compute<br/>Signature"]
    B --> C{"Signature<br/>Exists?"}
    C -->|No| D["Generate<br/>Story"]
    C -->|Yes| E{"STRICT<br/>Mode?"}
    E -->|No| F["Warn +<br/>Try New Template"]
    E -->|Yes| G["Abort"]
    F --> A
    D --> H["Save with<br/>Signature"]
```

#### Semantic Embedding Dedup (v1.4.0+)

In addition to signature-based dedup, story content can be checked for semantic similarity using embeddings.

**Architecture:**
```mermaid
flowchart LR
    A["Story Text"] --> B["Ollama Embedding<br/>(nomic-embed-text)"]
    B --> C["FAISS Index<br/>(story_vectors/)"]
    C --> D["Cosine Similarity"]
    D --> E{"Score >= 0.85?"}
    E -->|Yes| F["HIGH Signal"]
    E -->|No| G["LOW/MEDIUM"]
```

**Hybrid Scoring:**
```
hybrid_score = (canonical_score × 0.3) + (semantic_score × 0.7)
```

| Component | Weight | Description |
|-----------|--------|-------------|
| Canonical | 30% | Exact signature match (0 or 1) |
| Semantic | 70% | Cosine similarity (0.0 to 1.0) |

**Duplicate Detection:**
- Exact signature match → Always HIGH
- Hybrid score ≥ 0.85 → HIGH (semantic duplicate)
- Hybrid score 0.70-0.85 → MEDIUM
- Hybrid score < 0.70 → LOW

**Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `ENABLE_STORY_DEDUP` | `true` | Enable signature-based dedup |
| `STORY_DEDUP_STRICT` | `false` | Abort generation on duplicate |
| `ENABLE_STORY_SEMANTIC_DEDUP` | `true` | Enable semantic embedding dedup |
| `STORY_SEMANTIC_THRESHOLD_HIGH` | `0.85` | HIGH similarity threshold |
| `STORY_HYBRID_CANONICAL_WEIGHT` | `0.3` | Canonical weight in hybrid score |
| `STORY_HYBRID_SEMANTIC_WEIGHT` | `0.7` | Semantic weight in hybrid score |

**Story Metadata:**
```json
{
  "story_signature": "abc123...",
  "story_dedup_result": "unique",
  "story_dedup_reason": "unique",
  "semantic_similarity_score": 0.45,
  "hybrid_dedup_score": 0.315,
  "nearest_story_id": "story-20260112-143052"
}
```

**Key Modules:**
| Module | File | Purpose |
|--------|------|---------|
| Story Embedder | `src/dedup/story/embedder.py` | Extract text and generate embeddings |
| Story FAISS Index | `src/dedup/story/index.py` | Vector storage for stories |
| Semantic Dedup | `src/dedup/story/semantic_dedup.py` | Similarity checking |
| Hybrid Dedup | `src/dedup/story/hybrid_dedup.py` | Combined scoring |

**Storage:**
```
data/story_vectors/
├── story.faiss          # FAISS index for story embeddings
└── metadata.json        # story_id ↔ vector mapping
```

### Story Canonical Key Extraction

After story generation, the system extracts canonical dimensions from the **actual story text** to compare against the template's predefined `canonical_core`.

**Extraction Flow:**
```mermaid
flowchart LR
    A["Story Text"] --> B["LLM Analysis<br/>canonical_extractor.py"]
    B --> C["canonical_affinity<br/>(arrays)"]
    C --> D["Collapse to<br/>canonical_core"]
    D --> E["Compare with<br/>Template CK"]
    E --> F["Alignment Score<br/>(0-100%)"]
```

**Purpose:**
- Validate that generated content matches intended structure
- Track divergence between template intent and actual output
- Provide quality signals for future improvements

**Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `ENABLE_STORY_CK_EXTRACTION` | `true` | Enable/disable extraction |
| `STORY_CK_MODEL` | (none) | Override model for extraction |

**Alignment Score Calculation:**
```
alignment_score = matched_dimensions / 5 × 100%
```

| Score | Interpretation |
|-------|----------------|
| 100% | Perfect alignment |
| 80% | 4/5 dimensions match |
| 60% | 3/5 dimensions match |
| <40% | Significant divergence |

**Story Metadata:**
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
    "template_comparison": {
      "match_score": 0.8,
      "matches": ["setting_archetype", "primary_fear", "threat_mechanism", "twist_family"],
      "divergences": [{"dimension": "antagonist_archetype", "template": "system", "story": "collective"}]
    }
  }
}
```

### Story Canonical Key Extraction & Enforcement

After story generation, the system extracts canonical dimensions from the **actual story text** to compare against the template's predefined `canonical_core`, then applies enforcement policy.

**Extraction & Enforcement Flow:**
```mermaid
flowchart LR
    A["Story Text"] --> B["LLM Analysis<br/>canonical_extractor.py"]
    B --> C["canonical_affinity<br/>(arrays)"]
    C --> D["Collapse to<br/>canonical_core"]
    D --> E["Compare with<br/>Template CK"]
    E --> F["Alignment Score<br/>(0-100%)"]
    F --> G{"Enforcement<br/>Check"}
    G -->|Pass| H["Accept"]
    G -->|Fail + retry| I["Re-generate"]
    G -->|Fail + strict| J["Reject"]
```

**Purpose:**
- Validate that generated content matches intended structure
- Track divergence between template intent and actual output
- Enforce alignment constraints via configurable policy
- Provide quality signals for future improvements

**Extraction Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `ENABLE_STORY_CK_EXTRACTION` | `true` | Enable/disable extraction |
| `STORY_CK_MODEL` | (none) | Override model for extraction |

**Enforcement Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `STORY_CK_ENFORCEMENT` | `warn` | Policy: none/warn/retry/strict |
| `STORY_CK_MIN_ALIGNMENT` | `0.6` | Minimum alignment score (0.0-1.0) |

**Enforcement Policies:**
| Policy | Action on Failure |
|--------|-------------------|
| `none` | Always accept (disabled) |
| `warn` | Log warning, accept anyway (default) |
| `retry` | Re-attempt with different template |
| `strict` | Reject story entirely |

**Alignment Score Calculation:**
```
alignment_score = matched_dimensions / 5 × 100%
```

| Score | Interpretation |
|-------|----------------|
| 100% | Perfect alignment |
| 80% | 4/5 dimensions match |
| 60% | 3/5 dimensions match (default threshold) |
| <40% | Significant divergence |

**Story Metadata:**
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
    "template_comparison": {
      "match_score": 0.8,
      "matches": ["setting_archetype", "primary_fear", "threat_mechanism", "twist_family"],
      "divergences": [{"dimension": "antagonist_archetype", "template": "system", "story": "collective"}]
    },
    "enforcement": {
      "passed": true,
      "action": "accept",
      "reason": "Alignment 80% meets threshold 60%",
      "policy": "warn"
    }
  }
}
```

### Template Weight Penalty (Phase 3B)

특정 템플릿 클러스터의 과도한 반복을 방지하기 위해 **소프트 가중치 페널티**가 적용됩니다.

**SYSTEMIC_INEVITABILITY_CLUSTER:**

`antagonist=system` AND `twist=inevitability` 조합의 템플릿 그룹:

| Template ID | Template Name |
|-------------|---------------|
| `T-SYS-001` | Systemic Erosion |
| `T-APT-001` | Apartment Social Surveillance |
| `T-INF-001` | Infrastructure Isolation |
| `T-ECO-001` | Economic Annihilation |

**가중치 페널티 규칙:**

최근 수락된 스토리 10개(`PHASE3B_LOOKBACK_WINDOW`) 내에서 클러스터 템플릿 출현 빈도에 따라 선택 가중치를 감소시킵니다:

| 출현 횟수 | 가중치 배수 | 효과 |
|-----------|------------|------|
| < 4 | 1.00 | 페널티 없음 |
| ≥ 4 | 0.50 | -50% 가중치 |
| ≥ 6 | 0.20 | -80% 가중치 |
| ≥ 8 | 0.05 | -95% 가중치 |

> **설계 원칙:** 가중치는 0이 되지 않습니다 (하드 블로킹 없음). 이는 사전 생성(pre-generation) 단계의 소프트 제어입니다.

### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Generator | `src/story/generator.py` | Orchestrates generation pipeline (`generate_story`, `generate_with_topic`) |
| Template Loader | `src/story/template_loader.py` | Loads/selects templates |
| Prompt Builder | `src/story/prompt_builder.py` | Constructs LLM prompts |
| API Client | `src/story/api_client.py` | Claude API communication |
| **Canonical Extractor** | `src/story/canonical_extractor.py` | Story CK extraction & alignment scoring |
| Story Registry | `src/registry/story_registry.py` | Deduplication database |
| Research Context | `src/infra/research_context/` | Unified research selection & injection |
| Story Dedup | `src/story/dedup/` | Story-level signature-based deduplication |
| Research Executor | `src/research/executor/executor.py` | `run_research_pipeline()` for auto-research |
| **Image Generator** | `src/image/` | Thumbnail generation with multi-provider support (v1.6.1) |

### Deduplication Control

The dedup system uses **canonical fingerprinting**:

```python
canonical_core = {
    "setting": "apartment",
    "primary_fear": "social_displacement",
    "antagonist": "system",
    "mechanism": "surveillance",
    "twist": "inevitability"
}
```

**Signal Calculation:**
- Compare new story's canonical_core against all stored stories
- Count matching dimensions (0-5)
- Score = matches / 5

**Decision Logic:**
| Signal | Score | Action |
|--------|-------|--------|
| LOW | < 0.3 | Accept |
| MEDIUM | 0.3-0.6 | Accept (logged) |
| HIGH | > 0.6 | Regenerate (max 2x), then skip |

---

## Pipeline 2: Research Generation

### Flow

```mermaid
flowchart LR
    A["Topic Input<br/>CLI"] --> B["Prompt Construction<br/>prompt_template.py"]
    B --> C["Ollama Generation<br/>executor.py"]
    C --> D["Validation<br/>validator.py"]
    D --> E["Create Embedding<br/>embedder.py"]
    E --> F["Add to FAISS<br/>index.py"]
    F --> G["Dedup Check<br/>dedup.py"]
    G --> H["Save to<br/>data/research/"]
```

### Research Card Schema

```json
{
  "card_id": "RC-20260112-143052",
  "version": "1.0",
  "metadata": {
    "created_at": "2026-01-12T14:30:52",
    "model": "qwen3:30b",
    "status": "complete"
  },
  "output": {
    "title": "...",
    "summary": "...",
    "key_concepts": ["..."],
    "horror_applications": ["..."],
    "canonical_affinity": {
      "setting": ["urban", "apartment"],
      "primary_fear": ["isolation"],
      "antagonist": ["system"],
      "mechanism": ["surveillance"]
    }
  },
  "canonical_core": {
    "setting_archetype": "apartment",
    "primary_fear": "isolation",
    "antagonist_archetype": "system",
    "threat_mechanism": "surveillance",
    "twist_family": "inevitability"
  },
  "dedup": {
    "level": "LOW",
    "similarity_score": 0.45,
    "most_similar_card": "RC-20260110-091234"
  },
  "validation": {
    "has_title": true,
    "has_summary": true,
    "has_concepts": true,
    "has_applications": true,
    "canonical_parsed": true,
    "quality_score": "good"
  }
}
```

### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| CLI | `src/research/executor/cli.py` | Command-line interface |
| Executor | `src/research/executor/executor.py` | Ollama API + generation |
| Validator | `src/research/executor/validator.py` | Output parsing/validation |
| Output Writer | `src/research/executor/output_writer.py` | File persistence |
| Embedder | `src/dedup/research/embedder.py` | Ollama embedding (nomic-embed-text) |
| FAISS Index | `src/dedup/research/index.py` | Vector storage |
| Dedup | `src/dedup/research/dedup.py` | Similarity checking |
| Canonical Collapse | `src/research/executor/canonical_collapse.py` | canonical_affinity → canonical_core |
| Vector Backend | `src/research/integration/vector_backend_hooks.py` | Unified vector operations |

### Vector Backend Hooks (v1.4.0+)

Centralized vector operations for research card semantic search and clustering.

```mermaid
flowchart LR
    A["Research Card"] --> B["generate_embedding()"]
    B --> C["FAISS Index"]
    C --> D["vector_search_research_cards()"]
    D --> E["Similar Cards"]

    F["Template"] --> G["compute_semantic_affinity()"]
    A --> G
    G --> H["Affinity Score"]

    I["Card Collection"] --> J["cluster_research_cards()"]
    J --> K["K-Means Clusters"]
```

**Functions:**
| Function | Description |
|----------|-------------|
| `init_vector_backend()` | Initialize Ollama embedder and FAISS index |
| `generate_embedding(text)` | Generate embedding via nomic-embed-text |
| `vector_search_research_cards(embedding, top_k)` | Search similar cards in FAISS |
| `index_research_card(card_id, content, metadata)` | Add card to FAISS index |
| `compute_semantic_affinity(template_canonical, research_content)` | Cosine similarity between template and research |
| `cluster_research_cards(cards, n_clusters)` | K-means++ clustering on embeddings |

**Configuration:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `VECTOR_BACKEND_ENABLED` | `true` | Enable vector backend features |

### Canonical Core Normalization

Research cards include `canonical_core` - a normalized, schema-valid representation collapsed from `canonical_affinity`:

```
canonical_affinity (arrays)     →     canonical_core (single values)
────────────────────────────────────────────────────────────────────
setting: ["apartment", "urban"] →     setting_archetype: "apartment"
primary_fear: ["isolation"]     →     primary_fear: "isolation"
antagonist: ["system"]          →     antagonist_archetype: "system"
mechanism: ["surveillance"]     →     threat_mechanism: "surveillance"
(missing twist)                 →     twist_family: "inevitability" (default)
```

**Collapse Rules:**
- First valid value wins (invalid values are filtered)
- Primary fear uses priority ordering (annihilation > identity_erasure > ...)
- Missing dimensions get sensible defaults

---

## Pipeline 3: Task Scheduler

### Design Principle

> **API Server = Sole Execution Interface**

All task execution is managed through the API server. Tasks are enqueued via `POST /tasks` and the scheduler dispatches them sequentially.

### Flow

```mermaid
flowchart LR
    A["HTTP Request<br/>POST /tasks"] --> B["Task Creation<br/>persistence.py"]
    B --> C["Queue (SQLite)"]
    C --> D["Scheduler Dispatch<br/>service.py"]
    D --> E["Executor<br/>executor.py"]
    E --> F["Task Completion<br/>Update Status"]
```

### Task Lifecycle

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    QUEUED --> CANCELLED
    RUNNING --> COMPLETED: TaskRun
    RUNNING --> FAILED: TaskRun
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Scheduler Router | `src/api/routers/scheduler.py` | Scheduler control endpoints |
| Tasks Router | `src/api/routers/tasks.py` | Task CRUD endpoints |
| Story Router | `src/api/routers/story.py` | Direct story generation/listing |
| Schemas | `src/api/schemas/` | Pydantic models |
| Scheduler Service | `src/scheduler/service.py` | Dispatch loop, task execution |
| Persistence | `src/scheduler/persistence.py` | SQLite task storage |

### Task Storage

Tasks are stored in SQLite database (`data/scheduler.db`) with the following structure:

| Table | Purpose |
|-------|---------|
| `tasks` | Task queue and status |
| `task_runs` | Execution history and results |
| `task_groups` | Group execution management |

---

## Foundation Assets

### Knowledge Units (52 total)

Located in `assets/knowledge_units/`

| Category | Count | Description |
|----------|-------|-------------|
| horror_concept | 14 | Theoretical foundations |
| horror_theme | 15 | Specific motifs/scenarios |
| social_fear | 17 | Real-world systemic threats |
| writing_technique | 6 | Craft techniques |

### Templates (15 total)

Located in `assets/templates/`

Each template defines:
- `canonical_core` - Unique identity fingerprint
- `required_ku_categories` - Compatible KU types
- `story_skeleton` - 3-act structure
- `variation_axes` - Allowed variations

**Template Distribution:**
- Systemic horror: 6 templates
- Domestic horror: 3 templates
- Medical horror: 2 templates
- Digital horror: 2 templates
- Other: 2 templates

### Canonical Dimensions

| Dimension | Values |
|-----------|--------|
| `setting_archetype` | apartment, hospital, rural, domestic_space, digital, liminal, infrastructure, body, abstract |
| `primary_fear` | loss_of_autonomy, identity_erasure, social_displacement, contamination, isolation, annihilation |
| `antagonist_archetype` | ghost, system, technology, body, collective, unknown |
| `threat_mechanism` | surveillance, possession, debt, infection, impersonation, confinement, erosion, exploitation |
| `twist_family` | revelation, inevitability, inversion, circularity, self_is_monster, ambiguity |

---

## Data Storage

### SQLite Databases

| Database | Location | Purpose |
|----------|----------|---------|
| Story Registry | `data/story_registry.db` | Story dedup fingerprints (configurable via `STORY_REGISTRY_DB_PATH`) |
| Research Registry | `data/research_registry.db` | Research card metadata |

**Story Registry 스키마 버전 이력:**

| Version | 변경 내용 |
|---------|----------|
| 1.0.0 | 초기 스키마 - 기본 스토리 메타데이터 저장 |
| 1.1.0 | `story_signature`, `canonical_core_json`, `research_used_json` 컬럼 추가 (스토리 레벨 중복 검사 지원) |

> 스키마 버전 불일치 시 자동 마이그레이션이 실행되며, 마이그레이션 전 자동 백업이 생성됩니다.

### File Storage

| Directory | Contents |
|-----------|----------|
| `data/novel/` | Generated story files (v1.3.1+, configurable via `NOVEL_OUTPUT_DIR`) |
| `data/research/` | Research card JSON files |
| `jobs/` | Job metadata JSON files (configurable via `JOB_DIR`) |
| `logs/` | Execution logs |

---

## Model Selection

### Overview

The system supports multiple LLM providers through a unified abstraction layer:

| Pipeline | Default Provider | Alternative Providers |
|----------|------------------|----------------------|
| Story Generation | Claude (Anthropic) | Ollama (local) |
| Research Generation | Ollama (local) | Gemini (optional, feature-flagged) |

### Provider Abstraction

```mermaid
flowchart TB
    subgraph Story["Story Generation"]
        S1["generator.py"] --> S2["model_provider.py"]
        S2 --> S3["ClaudeProvider"]
        S2 --> S4["OllamaProvider"]
    end

    subgraph Research["Research Generation"]
        R1["executor.py"] --> R2["model_provider.py"]
        R2 --> R3["OllamaResearchProvider"]
        R2 --> R4["GeminiResearchProvider"]
    end

    S3 --> Claude["Claude API"]
    S4 --> Ollama1["Ollama API"]
    R3 --> Ollama2["Ollama API"]
    R4 --> Gemini["Gemini API"]
```

### Model Specification Format

| Format | Provider | Example |
|--------|----------|---------|
| `ollama:{model}` | Ollama | `ollama:llama3`, `ollama:qwen` |
| `gemini` | Gemini | `gemini` (uses GOOGLE_AI_MODEL env) |
| `gemini:{model}` | Gemini | `gemini:gemini-2.5-flash` |
| `{claude-model}` | Anthropic | `claude-sonnet-4-5-20250929` |
| (none) | Default | Story: Claude, Research: Ollama |

### Story Model Selection

**API (Direct):**
```json
POST /story/generate
{
  "topic": "Korean apartment horror",
  "model": "ollama:llama3"
}
```

**API (Scheduler):**
```json
POST /tasks
[{"type": "story", "params": {"model": "ollama:llama3"}, "priority": 10}]
```

**Metadata Recording:**
```json
{
  "model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic"
}
```

### Research Model Selection

**API (Direct):**
```json
POST /research/run
{
  "topic": "Korean apartment horror",
  "model": "deep-research",
  "timeout": 300
}
```

**API (Scheduler):**
```json
POST /tasks
[{"type": "research", "params": {"topic": "Korean apartment horror", "model": "deep-research", "timeout": 300}}]
```

**Metadata Recording (Ollama):**
```json
{
  "model": "qwen3:30b",
  "provider": "ollama"
}
```

**Metadata Recording (Deep Research):**
```json
{
  "model": "deep-research-pro-preview-12-2025",
  "provider": "gemini",
  "execution_mode": "deep_research",
  "interaction_id": "<interaction_id>"
}
```

### Gemini API (Research Only)

Gemini is **feature-flagged** and only available for research generation.

**Two Execution Modes:**

| Mode | Model Spec | API | Use Case |
|------|-----------|-----|----------|
| Standard | `gemini` | models.generate_content | Quick research |
| Deep Research | `deep-research` | Interactions API | Comprehensive research |

**Configuration:**
```env
GEMINI_ENABLED=false          # Must be true to use Gemini
GEMINI_API_KEY=your_key       # Required when enabled
GOOGLE_AI_MODEL=deep-research-pro-preview-12-2025  # Default model
```

**API Provider:** Google AI Studio (not Vertex AI)

**Requirements:**
```bash
pip install google-genai
```

**Usage:**
```bash
# Enable Gemini in .env
GEMINI_ENABLED=true
GEMINI_API_KEY=your_api_key

# Run research with Gemini standard
python -m src.research.executor run "Korean horror themes" --model gemini

# Run research with Gemini Deep Research Agent (recommended)
python -m src.research.executor run "Korean horror themes" --model deep-research
```

### Gemini Deep Research Agent

The Deep Research mode uses the Gemini Interactions API with background execution and polling.

**Agent:** `deep-research-pro-preview-12-2025`

**Execution Flow:**
```mermaid
flowchart LR
    A["Create<br/>Interaction"] --> B["Execute<br/>Query"]
    B --> C["Poll for<br/>Completion"]
    C --> D["Extract<br/>Response"]
    D --> E["Build<br/>Metadata"]
```

**Features:**
- Asynchronous interaction with polling
- Longer timeout support (up to 10 minutes)
- Detailed research output
- Compatible with existing dedup and canonical pipelines

---

## External Dependencies

| Service | Purpose | Required |
|---------|---------|----------|
| Claude API | Story generation (default) | Yes |
| Ollama | Research generation (default), Story (optional) | Optional |
| Gemini API | Research generation (optional, feature-flagged) | No |

### Local-First Architecture

The system is designed to run locally without external services beyond Claude API:
- SQLite for persistence (no external database)
- FAISS-cpu for vector search (no GPU required)
- File-based job storage (no message queue)

---

## Graceful Shutdown

The story generator supports graceful shutdown via SIGINT/SIGTERM:

1. Signal received → `shutdown_requested = True`
2. Current generation completes
3. Results saved
4. Final statistics logged
5. Clean exit (code 0)

---

## CLI Resource Cleanup (Research Executor)

The research executor CLI automatically unloads Ollama models after execution to release VRAM:

```mermaid
flowchart LR
    A["CLI Start"] --> B["Setup<br/>Signal Handlers"]
    B --> C["Execute<br/>Research"]
    C --> D["Unload Model<br/>(keep_alive=0)"]
    D --> E["Exit"]

    F["SIGINT/SIGTERM"] --> G["Cleanup Handler"]
    G --> D
```

**Cleanup Mechanism:**
1. Model tracked when `execute_research()` starts
2. On success: Model unloaded via `unload_model()`
3. On SIGINT/SIGTERM: Signal handler calls cleanup before exit
4. `atexit` handler as fallback for abnormal exits

**API vs CLI:**
| Context | Resource Manager | Cleanup Trigger |
|---------|------------------|-----------------|
| API Server | `OllamaResourceManager` | FastAPI lifespan events |
| CLI | Signal handlers + atexit | Execution complete or signal |

---

## Registry Backup

The story registry automatically creates a backup before schema migration:

```mermaid
flowchart LR
    A["Registry Init"] --> B{"Version<br/>Mismatch?"}
    B -->|No| C["Continue"]
    B -->|Yes| D["Create Backup"]
    D --> E["Run Migration"]
    E --> F["Update Version"]
    F --> C
```

**Backup Details:**
- **Trigger:** Schema version mismatch (e.g., 1.0.0 → 1.1.0)
- **Location:** Same directory as original DB
- **Naming:** `{db}.backup.{version}.{timestamp}.db`
- **Method:** `shutil.copy2` (preserves metadata)

**Example:**
```
data/story_registry.backup.1.0.0.20260112_130012.db
```

**See also:** [Registry Backup Guide](../technical/REGISTRY_BACKUP_GUIDE.md)

---

## Unified Backup/Restore System (v1.4.3+)

In addition to the automatic schema-migration backup, the system provides unified CLI scripts for comprehensive backup and restore of all data components.

### Backup Targets

| Component | Path | Description |
|-----------|------|-------------|
| `story-registry` | `data/story_registry.db` | Story metadata & dedup records |
| `research` | `data/research/` | Research DB, FAISS index, card JSON files |
| `stories` | `data/novel/` | Generated story files (md + metadata) |
| `story-vectors` | `data/story_vectors/` | Story FAISS index for semantic dedup |
| `seeds` | `data/seeds/` | Seed registry |

### CLI Scripts

```
scripts/
├── backup_config.sh   # Common configuration
├── backup.sh          # Create backups (supports compression)
├── restore.sh         # Restore from backup (with dry-run)
└── verify_backup.sh   # 13-test integrity verification
```

### Quick Usage

```bash
# Full backup with compression
./scripts/backup.sh --compress

# Restore from backup
./scripts/restore.sh backups/backup_20260118_120000.tar.gz

# Verify backup integrity (13 tests)
./scripts/verify_backup.sh
```

### Verification Tests

The `verify_backup.sh` script runs 13 integrity tests:

| Test | Description |
|------|-------------|
| Backup Creation | Validates backup file generation |
| Archive Integrity | SHA256 checksum verification |
| Manifest Validation | manifest.json structure check |
| Restore Dry-Run | Non-destructive restore test |
| Data Integrity | File count/checksum comparison |
| SQLite Integrity | `PRAGMA integrity_check` |
| **Schema Validation** | DB table/column structure validation |
| **Research Card JSON** | JSON structure and required fields |
| **Story Metadata JSON** | Metadata JSON validation |
| **Story File Pairs** | .md ↔ _metadata.json pairing |
| **FAISS Consistency** | Dimension and mapping validation |
| **Cross-References** | Story → Research card references |
| Full Restore Cycle | End-to-end restore simulation |

**See also:** [Backup & Restore Guide](../technical/BACKUP_RESTORE_GUIDE.md)

---

## Unified Research Context Module

Located at `src/infra/research_context/`, this module provides a single source of truth for research card selection and injection, used by both CLI and API.

### Module Structure

| File | Exports | Purpose |
|------|---------|---------|
| `policy.py` | `DedupLevel`, `is_usable_card`, `get_dedup_level` | Dedup level rules and card usability |
| `repository.py` | `load_usable_research_cards`, `get_card_by_id`, `search_cards_by_topic`, `get_best_card_for_topic` | Card loading with dedup filtering and topic search |
| `selector.py` | `ResearchSelection`, `select_research_for_template` | Canonical affinity matching |
| `formatter.py` | `build_research_context`, `format_research_for_prompt`, `format_research_for_metadata` | Prompt formatting and traceability |

### Dedup Level Policy

| Level | Similarity Score | Default Behavior |
|-------|------------------|------------------|
| LOW | < 0.70 | Usable (unique content) |
| MEDIUM | 0.70-0.85 | Usable (some overlap) |
| HIGH | ≥ 0.85 | **Excluded** (likely duplicate) |

### Selection Algorithm

1. Load all usable cards (excludes HIGH dedup by default)
2. For each card, compute affinity score against template's `canonical_core`
3. Weight dimensions: primary_fear (0.3), setting (0.25), antagonist (0.25), mechanism (0.2)
4. Return top-K cards with scores above threshold

### Traceability

Story metadata includes:
```json
{
  "research_used": ["RC-20260112-143052"],
  "research_injection_mode": "auto",
  "research_selection_score": 0.85,
  "research_selection_reason": "Matched 1/21 usable cards"
}
```

---

## Design Decisions

Key architectural decisions are documented in `docs/technical/decision_log.md`:

- **D-001**: CLI as source of truth for business logic
- **D-002**: Hybrid KU selection (category + canonical matching)
- **D-003**: Assisted manual generation (not fully automated)
- **D-004**: HIGH-only blocking policy for deduplication
- **D-005**: File-based job storage for simplicity
- **D-006**: Unified research context module (`src/infra/research_context/`) for CLI/API consistency
- **D-007**: Research auto-injection ON by default with traceability metadata
- **D-008**: Story-level dedup using signature (canonical_core + research_used → SHA256)
- **D-009**: Story dedup WARN by default, STRICT mode optional for abort

---

## Assumptions and Uncertainties

### Assumptions

- Single-user/single-instance deployment
- Claude API rate limits are sufficient for intended usage
- Ollama runs on same machine as the application

### Uncertainties

- [Uncertain] Optimal KU count per template (currently 2-5 recommended)
- [Uncertain] Long-term scalability of file-based job storage
- [Uncertain] FAISS index performance beyond 10,000 research cards

---

**Note:** All documentation reflects v1.5.0 with model selection, Gemini Deep Research integration, unified backup/restore system, and complete deduplication pipeline.
