# Execution Structure Analysis Report

**Analysis Date:** 2026-01-12
**Purpose:** Diagnostic report for STEP 4-B planning
**Status:** ANALYSIS ONLY - No changes proposed

---

## 1. Entry Points

### 1.1 Story Generation CLI (`main.py`)

**File:** `main.py`
**Invocation:** `python main.py [options]`

**Key Flags:**
- `--enable-dedup` - Enable Phase 2C deduplication
- `--max-stories N` - Generate N stories then exit
- `--duration-seconds N` - Run for N seconds (24h mode)
- `--log-level` - DEBUG/INFO/WARNING/ERROR

**Execution Flow:**
1. Parse arguments
2. Initialize logging via `setup_logging()` from `logging_config.py`
3. If dedup enabled: call `generate_with_dedup_control()` from `horror_story_generator.py`
4. Else: call `generate_horror_story()` directly
5. Loop until max_stories or duration reached

**Direct Dependencies:**
- `horror_story_generator` (core generation)
- `story_registry` (persistence)
- `similarity` (in-memory dedup)
- `logging_config` (logging setup)

---

### 1.2 Research CLI (`research_executor/__main__.py`)

**File:** `research_executor/__main__.py`, `research_executor/cli.py`
**Invocation:** `python -m research_executor <subcommand> [options]`

**Subcommands:**
| Command | Description |
|---------|-------------|
| `run` | Execute research generation |
| `list` | List existing research cards |
| `validate` | Validate card JSON structure |
| `dedup` | Check card for duplicates |
| `index` | Build/rebuild FAISS index |
| `seed-gen` | Generate Story Seeds from cards |
| `seed-list` | List existing Story Seeds |

**Execution Flow (run):**
1. Parse CLI arguments
2. Check Ollama availability via `check_ollama_available()`
3. Check model availability via `check_model_available()`
4. Call `execute_research()` from `executor.py`
5. Parse JSON from response via `validator.py`
6. Write outputs via `output_writer.py` (JSON + Markdown)
7. Optionally add to FAISS index

**Direct Dependencies:**
- `research_executor.config` (settings)
- `research_executor.executor` (Ollama API)
- `research_executor.validator` (JSON parsing)
- `research_executor.output_writer` (file output)
- `research_dedup` (FAISS indexing)
- `story_seed` (seed generation)
- `seed_registry` (seed tracking)
- `data_paths` (path resolution)

---

### 1.3 API Server (`research_api/main.py`)

**File:** `research_api/main.py`, `research_api/routers/*.py`
**Invocation:** `uvicorn research_api.main:app --reload`

**API Pattern:** CLI-as-source-of-truth
The API does NOT run generation directly. It spawns subprocess commands.

**Key Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trigger/story` | POST | Trigger story generation |
| `/api/trigger/research` | POST | Trigger research generation |
| `/api/jobs/{id}` | GET | Get job status |
| `/api/jobs/{id}/cancel` | POST | Cancel running job |
| `/api/dedup/check` | POST | Pre-flight dedup check |

**Execution Flow (trigger):**
1. Receive trigger request with parameters
2. Create job record via `job_manager.py`
3. Build CLI command string (`python main.py` or `python -m research_executor run`)
4. Spawn subprocess via `subprocess.Popen(start_new_session=True)`
5. Return job ID immediately (async execution)

**Direct Dependencies:**
- `job_manager` (job CRUD)
- `subprocess` (process spawning)
- `research_dedup` (dedup check endpoint)

**Important Pattern:**
```
API → subprocess → CLI → Core logic
```
The API is a thin orchestration layer. Business logic lives in CLI/core modules.

---

## 2. Story Generation Pipeline

### 2.1 Core Generator (`horror_story_generator.py`)

**File:** `horror_story_generator.py` (~800 lines)

**Two Generation Modes:**

| Function | Description |
|----------|-------------|
| `generate_horror_story()` | Basic generation, no dedup |
| `generate_with_dedup_control()` | Full pipeline with dedup loop |

**Generation Flow (with dedup):**
```
1. Load template skeleton (template_loader.py)
   ↓
2. [Optional] Select research context (research_integration/)
   ↓
3. Build prompt (prompt_builder.py)
   ↓
4. Call Claude API (api_client.py)
   ↓
5. Observe similarity (similarity.py) → returns signal
   ↓
6. If HIGH signal: reject, retry (up to max attempts)
   ↓
7. Accept story → add to registry (story_registry.py)
   ↓
8. Save story to file
```

**Retry Logic (Phase 2C):**
- Max 3 retry attempts on HIGH similarity
- Each retry increments "novelty pressure" in prompt
- If all retries fail: accept story anyway (never blocks)

---

### 2.2 Template Loading (`template_loader.py`)

**File:** `template_loader.py`

**Path Reference (OUTDATED):**
```python
TEMPLATE_SKELETONS_PATH = Path(__file__).parent / "phase1_foundation" / "03_templates" / "template_skeletons_v1.json"
```
This path references the old location. After STEP 4-A restructuring, templates are now at:
```
assets/templates/template_skeletons_v1.json
```

**Key Function:** `select_random_template()`

**Selection Algorithm (Phase 3B):**
1. Load all templates from JSON
2. Query `story_registry` for recent usage counts per template
3. Apply weight penalty to over-used templates
4. Special penalty for "Systemic Inevitability" cluster
5. Weighted random selection

---

### 2.3 Prompt Building (`prompt_builder.py`)

**File:** `prompt_builder.py`

**Key Function:** `build_prompt(skeleton, research_context=None)`

**Prompt Structure:**
```
System message
  + Template structure
  + Canonical dimensions
  + [Optional] Research context injection
  + Tone/style guidelines
```

**Research Injection Pattern:**
If `research_context` is provided, appends:
- Key concepts from matched research cards
- Horror application suggestions
- Source card IDs for tracing

---

### 2.4 API Client (`api_client.py`)

**File:** `api_client.py`

**LLM Provider:** Claude (Anthropic API)

**Key Function:** `call_claude_api(prompt, system_message)`

**Configuration:**
- Model configurable via environment
- Temperature, max_tokens from config
- Retry logic with exponential backoff

---

## 3. Research Pipeline

### 3.1 Research Executor (`research_executor/executor.py`)

**File:** `research_executor/executor.py`

**LLM Provider:** Ollama (local)

**Key Function:** `execute_research(topic, model, timeout)`

**Execution Flow:**
1. Build prompt via `build_prompt(topic)` from `prompt_template.py`
2. POST to `OLLAMA_GENERATE_ENDPOINT` (`/api/generate`)
3. Parse JSON response
4. Return (raw_response, metadata)

**Error Handling:**
- `OllamaConnectionError` - Server not reachable
- `OllamaModelNotFoundError` - Model not available
- `OllamaTimeoutError` - Request timeout

---

### 3.2 Output Writer (`research_executor/output_writer.py`)

**File:** `research_executor/output_writer.py`

**Output Structure:**
```
data/research/
  └── YYYY/MM/
      ├── RC-YYYYMMDD-HHMMSS.json
      └── RC-YYYYMMDD-HHMMSS.md
```

**Card ID Format:** `RC-YYYYMMDD-HHMMSS`

**JSON Schema Fields:**
- `card_id`, `version`, `metadata`
- `input`: topic, tags
- `output`: title, summary, key_concepts, horror_applications, canonical_affinity
- `validation`: quality_score, field completeness

---

### 3.3 Research Integration (`research_integration/`)

**Files:**
- `__init__.py` - Module exports
- `loader.py` - Load cards from filesystem
- `selector.py` - Select cards by affinity matching
- `phase_b_hooks.py` - Status helpers

**Selection Algorithm:**
1. Load all cards with quality_filter
2. For each card, compute affinity score against template's `canonical_core`
3. Score uses weighted dimension matching (setting, primary_fear, antagonist, mechanism)
4. Filter by `MIN_MATCH_SCORE` (0.25)
5. Return top `MAX_SELECTED_CARDS` (3)

**Key Principle:** Research influence is READ-ONLY. It guides but never blocks generation.

---

## 4. Deduplication Flow

### 4.1 Two Dedup Systems

The project has **two separate deduplication systems** that serve different purposes:

| System | File(s) | Purpose | Persistence |
|--------|---------|---------|-------------|
| Story Similarity | `similarity.py` | Detect similar stories during generation | In-memory only |
| Research Dedup | `research_dedup/` | Detect similar research cards | FAISS + SQLite |

---

### 4.2 Story Similarity (`similarity.py`)

**File:** `similarity.py`

**Scope:** Single process session (resets on restart)

**Data Structure:**
```python
_generation_memory: List[GenerationRecord] = []  # In-memory only
```

**Key Functions:**
- `observe_similarity(story_text, registry)` - Compare against recent stories
- `should_accept_story(signal)` - Returns True unless HIGH signal
- `compute_similarity(text1, text2)` - Basic similarity metric

**Signal Levels:**
- `LOW` - Accept immediately
- `MEDIUM` - Accept with note
- `HIGH` - Retry or escalate

**Important:** This is observation-only. Never blocks generation permanently.

---

### 4.3 Story Registry (`story_registry.py`)

**File:** `story_registry.py`

**Persistence:** SQLite at `./data/story_registry.db`

**Schema (stories table):**
- story_id, template_id, skeleton_name
- canonical dimensions (setting, primary_fear, etc.)
- similarity metrics, created_at

**Schema (similarity_edges table):**
- Tracks story-to-story similarity relationships

**Key Methods:**
- `add_story()` - Insert new story record
- `load_recent_accepted()` - Get recent stories for comparison
- `get_template_usage_counts()` - For weighted template selection

---

### 4.4 Research Dedup (`research_dedup/`)

**Files:**
- `embedder.py` - Ollama embedding generation
- `index.py` - FAISS index management
- `dedup.py` - Deduplication logic

**Persistence:**
- FAISS index: `data/research/vectors/research.faiss`
- Metadata: `data/research/vectors/metadata.json`

**Embedding Flow:**
1. Extract text via `create_card_text_for_embedding(card_data)`
2. Call Ollama `/api/embed` endpoint
3. Normalize vector (L2)
4. Store in FAISS IndexFlatIP (inner product for cosine similarity)

**Dedup Check Flow:**
1. Generate embedding for new card
2. Search FAISS for nearest neighbor
3. Return `DedupResult(score, nearest_card_id, signal)`

**Signal Thresholds:**
- `LOW`: score < 0.70
- `MEDIUM`: 0.70 <= score < 0.85
- `HIGH`: score >= 0.85

**Key Principle:** High similarity does NOT block research. It only provides a signal.

---

## 5. Registries and State Management

### 5.1 Registry Overview

| Registry | File | DB Path | Purpose |
|----------|------|---------|---------|
| Story Registry | `story_registry.py` | `data/story_registry.db` | Track generated stories |
| Seed Registry | `seed_registry.py` | `data/seeds/seed_registry.sqlite` | Track Story Seeds |
| Research Registry | (implied) | `data/research/registry.sqlite` | Track research cards |
| Job Manager | `job_manager.py` | `jobs/*.json` | Track API jobs |

---

### 5.2 Story Registry (`story_registry.py`)

**Initialization Pattern:**
```python
DEFAULT_DB_PATH = "./data/story_registry.db"

class StoryRegistry:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self._ensure_schema()
```

**Schema auto-creation on first connection.**

**Used By:**
- `horror_story_generator.py` - Add stories, query history
- `template_loader.py` - Get usage counts for weighting
- `similarity.py` - Load recent stories for comparison

---

### 5.3 Seed Registry (`seed_registry.py`)

**Purpose:** Track Story Seeds (distilled research cards)

**Schema:**
```sql
CREATE TABLE story_seeds (
    seed_id TEXT PRIMARY KEY,
    source_card_id TEXT NOT NULL,
    created_at TIMESTAMP,
    file_path TEXT,
    times_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    is_available INTEGER DEFAULT 1
);
```

**Key Methods:**
- `register()` - Add new seed
- `mark_used()` - Increment usage counter
- `get_least_used()` - Fair selection for story generation

---

### 5.4 Job Manager (`job_manager.py`)

**Purpose:** Track API-triggered background jobs

**Storage:** JSON files in `jobs/` directory (not SQLite)

**Job Lifecycle:**
```
created → running → (completed | failed | cancelled)
```

**Fields:**
- job_id, job_type, status, pid
- created_at, started_at, completed_at
- artifacts (output file paths)
- error (if failed)

**Pattern:** One JSON file per job, named `{job_id}.json`

---

## 6. Infrastructure and Glue Code

### 6.1 Path Management (`data_paths.py`)

**File:** `data_paths.py`

**Purpose:** Centralized path resolution for all data directories

**Key Functions:**
| Function | Returns |
|----------|---------|
| `get_project_root()` | Project root directory |
| `get_data_root()` | `data/` directory |
| `get_research_root()` | `data/research/` |
| `get_research_cards_dir()` | `data/research/cards/` |
| `get_faiss_index_path()` | `data/research/vectors/research.faiss` |
| `get_story_registry_path()` | `data/story_registry.db` |
| `get_seeds_root()` | `data/seeds/` |

**Auto-initialization:**
```python
# Auto-initialize when module is imported
initialize()
```

Creates directories if they don't exist on first import.

---

### 6.2 Logging (`logging_config.py`)

**File:** `logging_config.py`

**Key Feature:** Daily rotating file handler (Phase 3B)

**Log File Pattern:**
```
logs/horror_story_YYYYMMDD_HHMMSS.log
```
- `YYYYMMDD` = Current calendar date
- `HHMMSS` = Process start time (fixed for session)

**Rotation Trigger:** Date change (not file size)

---

### 6.3 Story Seed Module (`story_seed.py`)

**File:** `story_seed.py`

**Purpose:** Distill Research Cards into Story Seeds

**Seed Format:**
```json
{
    "seed_id": "SS-YYYY-MM-DD-XXX",
    "source_card_id": "RC-...",
    "key_themes": ["...", "..."],
    "atmosphere_tags": ["...", "..."],
    "suggested_hooks": ["...", "..."],
    "cultural_elements": ["...", "..."]
}
```

**Generation:** Uses Ollama to extract essential elements from research card

---

## 7. Dependency Map and Coupling Points

### 7.1 Module Dependency Graph

```
main.py
  ├── horror_story_generator.py
  │     ├── template_loader.py
  │     │     └── story_registry.py
  │     ├── prompt_builder.py
  │     ├── api_client.py
  │     ├── similarity.py
  │     ├── story_registry.py
  │     └── research_integration/
  │           ├── loader.py
  │           └── selector.py
  ├── story_registry.py
  ├── similarity.py
  └── logging_config.py

research_executor/
  ├── __main__.py
  │     └── cli.py
  │           ├── config.py
  │           ├── executor.py
  │           │     └── prompt_template.py
  │           ├── validator.py
  │           ├── output_writer.py
  │           ├── research_dedup/
  │           │     ├── embedder.py
  │           │     ├── index.py
  │           │     └── dedup.py
  │           ├── story_seed.py
  │           ├── seed_registry.py
  │           └── data_paths.py

research_api/
  ├── main.py
  │     └── routers/
  │           ├── jobs.py
  │           │     ├── job_manager.py
  │           │     └── subprocess (stdlib)
  │           └── dedup.py
  │                 └── research_dedup/
```

---

### 7.2 Cross-Module Dependencies

| Module | Depends On | Dependency Type |
|--------|------------|-----------------|
| `template_loader` | `story_registry` | Query usage counts |
| `horror_story_generator` | `research_integration` | Optional (try/except) |
| `research_dedup` | Ollama API | External service |
| `api_client` | Claude API | External service |
| `job_manager` | None | Standalone |
| `data_paths` | None | Standalone |

---

### 7.3 Identified Coupling Points

**High Coupling:**

1. **`horror_story_generator.py` ↔ multiple modules**
   - Imports 6+ internal modules
   - Central orchestration point
   - Changes here affect the entire story pipeline

2. **`template_loader.py` → `story_registry.py`**
   - Template selection requires DB query
   - Tight coupling for Phase 3B weighting

3. **`research_executor/cli.py` → many modules**
   - Imports 7+ modules for different subcommands
   - Single file handles diverse responsibilities

**Medium Coupling:**

4. **`research_integration/` → filesystem**
   - Scans `data/research/` directory structure
   - Expects specific file naming (RC-*.json)

5. **API → CLI subprocess**
   - API builds CLI command strings
   - Tightly coupled to CLI argument format

**Low Coupling:**

6. **`data_paths.py`**
   - Standalone, no internal dependencies
   - Good abstraction for path management

7. **`job_manager.py`**
   - Standalone JSON file storage
   - No database dependencies

---

### 7.4 External Dependencies

| Dependency | Used By | Type |
|------------|---------|------|
| Claude API | `api_client.py` | Story generation |
| Ollama API | `executor.py`, `embedder.py` | Research + embeddings |
| FAISS | `research_dedup/index.py` | Vector search |
| SQLite | `story_registry.py`, `seed_registry.py` | Persistence |

---

## 8. Risk Assessment for STEP 4-B

### 8.1 Safe to Modify

These areas have low coupling and clear boundaries:

- `data_paths.py` - Path constants can be updated safely
- `logging_config.py` - Independent of business logic
- `job_manager.py` - Standalone job tracking
- `research_executor/output_writer.py` - Output formatting only

### 8.2 Requires Careful Handling

These areas have medium coupling:

- `template_loader.py` - Fix path reference, but don't change selection logic
- `research_dedup/` - Modular but depends on Ollama availability
- `seed_registry.py` - Schema changes need migration strategy

### 8.3 High Risk Areas

These areas require comprehensive testing:

- `horror_story_generator.py` - Central orchestration, many integrations
- `research_executor/cli.py` - Multiple subcommands, diverse dependencies
- `research_api/routers/jobs.py` - CLI command string building

### 8.4 Known Issues

1. **Outdated Path Reference**
   - `template_loader.py:TEMPLATE_SKELETONS_PATH` references `phase1_foundation/03_templates/`
   - Should point to `assets/templates/` after STEP 4-A

2. **Legacy Path Support**
   - `data_paths.py:find_all_research_cards()` has legacy path fallback
   - May need cleanup after migration stabilizes

3. **Global State Patterns**
   - Several modules use `_global_instance` singletons
   - `_generation_memory` in `similarity.py` is process-scoped only
   - FAISS index singleton in `research_dedup/index.py`

---

## 9. Summary

### Entry Points
- **3 distinct entry points** with different responsibilities
- Story CLI (`main.py`), Research CLI (`research_executor`), API (`research_api`)
- API uses subprocess delegation (not direct execution)

### Pipelines
- **Story pipeline:** Claude-based with template selection and dedup
- **Research pipeline:** Ollama-based with FAISS indexing

### Deduplication
- **Two separate systems:** Story similarity (in-memory) and Research dedup (FAISS)
- Both are observation-only; neither blocks permanently

### State Management
- **4 registries:** Story, Seed, Research, Jobs
- Mix of SQLite and JSON file storage

### Coupling
- `horror_story_generator.py` is the highest coupling point
- `data_paths.py` and `job_manager.py` are well-isolated

### STEP 4-B Readiness
- Safe areas exist for incremental refactoring
- High-risk areas need comprehensive test coverage first
- One known path issue requires immediate fix

---

*This report is for diagnostic purposes only. No code modifications proposed.*
