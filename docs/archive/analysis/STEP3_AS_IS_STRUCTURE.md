# STEP 3: As-Is Structure Analysis

**Status:** Analysis Complete
**Date:** 2026-01-12
**Purpose:** Document current repository structure, runtime dependencies, and data flow

---

## 1. Runtime Entry Points

The system has three primary entry points:

| Entry Point | Command | Purpose |
|-------------|---------|---------|
| Story Generation CLI | `python main.py` | Generate horror stories via Claude API |
| Research CLI | `python -m research_executor run <topic>` | Generate research cards via Ollama |
| Trigger API | `uvicorn research_api.main:app` | HTTP API for non-blocking job execution |

---

## 2. Core Execution Paths

### 2.1 Story Generation Pipeline

```
main.py
├── horror_story_generator.py     # Core generation logic
├── template_loader.py            # Load templates from phase1_foundation/03_templates/
├── prompt_builder.py             # Construct prompts with KUs
├── api_client.py                 # Claude API communication
├── story_registry.py             # SQLite deduplication
├── similarity.py                 # Fingerprint comparison
└── logging_config.py             # Logging setup
```

**Data Dependencies:**
- `phase1_foundation/01_knowledge_units/knowledge_units.json`
- `phase1_foundation/03_templates/template_skeletons_v1.json`
- `phase1_foundation/02_canonical_abstraction/*.json`

### 2.2 Research Generation Pipeline

```
research_executor/
├── cli.py                        # CLI entry point
├── executor.py                   # Ollama execution
├── prompt_template.py            # Research prompts
├── validator.py                  # Output validation
├── output_writer.py              # File persistence
└── config.py                     # Configuration

research_dedup/
├── dedup.py                      # Similarity checking
├── embedder.py                   # Text embedding
└── index.py                      # FAISS vector index

research_integration/
├── loader.py                     # Load research cards
├── selector.py                   # Select cards for prompts
└── phase_b_hooks.py              # Integration hooks
```

### 2.3 Trigger API Pipeline

```
research_api/
├── main.py                       # FastAPI app
├── routers/
│   ├── jobs.py                   # Job trigger/monitor endpoints
│   ├── research.py               # Research endpoints
│   └── dedup.py                  # Dedup check endpoints
├── schemas/                      # Pydantic models
│   ├── jobs.py
│   ├── research.py
│   └── dedup.py
└── services/
    ├── dedup_service.py          # Dedup logic
    ├── research_service.py       # Research logic
    └── ollama_resource.py        # Ollama connection

Root-level support:
├── job_manager.py                # Job CRUD operations
├── job_monitor.py                # PID monitoring
├── seed_integration.py           # Seed data handling
├── seed_registry.py              # Seed database
├── story_seed.py                 # Seed generation
└── research_registry.py          # Research card registry
```

---

## 3. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Knowledge Units                Templates              User Request          │
│  (01_knowledge_units/)          (03_templates/)        (CLI/API)            │
└────────────┬────────────────────────┬─────────────────────┬─────────────────┘
             │                        │                     │
             ▼                        ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROMPT CONSTRUCTION                                │
│                          (prompt_builder.py)                                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
┌─────────────────────────────┐             ┌─────────────────────────────────┐
│     STORY GENERATION        │             │      RESEARCH GENERATION        │
│     (Claude API)            │             │      (Ollama)                   │
│     api_client.py           │             │      research_executor/         │
└──────────────┬──────────────┘             └──────────────┬──────────────────┘
               │                                           │
               ▼                                           ▼
┌─────────────────────────────┐             ┌─────────────────────────────────┐
│   DEDUPLICATION CHECK       │             │   DEDUPLICATION CHECK           │
│   (SQLite fingerprints)     │             │   (FAISS vectors)               │
│   story_registry.py         │             │   research_dedup/               │
│   similarity.py             │             └──────────────┬──────────────────┘
└──────────────┬──────────────┘                            │
               │                                           │
               ▼                                           ▼
┌─────────────────────────────┐             ┌─────────────────────────────────┐
│       OUTPUT STORAGE        │             │       OUTPUT STORAGE            │
│   generated_stories/        │             │   data/research/YYYY/MM/        │
│   data/stories/             │             │   data/research/vectors/        │
└─────────────────────────────┘             └─────────────────────────────────┘
```

---

## 4. Directory Analysis

### 4.1 Runtime-Critical Directories

| Directory | Purpose | Required at Runtime |
|-----------|---------|---------------------|
| `.` (root) | Python modules | YES - all core modules |
| `research_api/` | FastAPI application | YES - for API mode |
| `research_executor/` | Research CLI | YES - for research mode |
| `research_dedup/` | Vector deduplication | YES - if dedup enabled |
| `research_integration/` | Research card integration | YES - for story+research |
| `phase1_foundation/01_knowledge_units/` | KU data | YES - required for prompts |
| `phase1_foundation/03_templates/` | Template data | YES - required for prompts |
| `phase1_foundation/02_canonical_abstraction/` | Canonical mappings | YES - for KU selection |

### 4.2 Generated Data Directories

| Directory | Purpose | Created at Runtime |
|-----------|---------|-------------------|
| `data/` | All generated data root | YES |
| `data/research/` | Research cards | YES |
| `data/research/vectors/` | FAISS indices | YES |
| `data/seeds/` | Seed registry | YES |
| `generated_stories/` | Story outputs | YES |
| `jobs/` | Job metadata | YES |
| `logs/` | Execution logs | YES |

### 4.3 Documentation/Reference Directories

| Directory | Purpose | Required at Runtime |
|-----------|---------|---------------------|
| `docs/` | Documentation | NO |
| `docs/analysis/` | Analysis documents | NO |
| `docs/phase_b/` | Phase B specs | NO |
| `tests/` | Test suite | NO (dev only) |
| `n8n_workflows/` | Workflow examples | NO |
| `archive/` | Legacy files | NO |

### 4.4 Historical/Phase Directories

| Directory | Purpose | Status |
|-----------|---------|--------|
| `phase1_foundation/` | Foundation assets | ACTIVE but poorly named |
| `phase1_foundation/00_raw_research/` | Initial research | ARCHIVE candidate |
| `phase2_execution/` | Specs only, no code | ARCHIVE candidate |

---

## 5. File Inventory Summary

### 5.1 Python Modules (Root Level)

| File | Lines | Purpose | Dependencies |
|------|-------|---------|--------------|
| `main.py` | 350 | Story CLI entry | horror_story_generator, template_loader, etc. |
| `horror_story_generator.py` | 750 | Core generation | api_client, prompt_builder |
| `prompt_builder.py` | 400 | Prompt construction | template_loader |
| `api_client.py` | 130 | Claude API | anthropic |
| `template_loader.py` | 200 | Template loading | - |
| `story_registry.py` | 300 | Story dedup DB | sqlite3 |
| `similarity.py` | 200 | Fingerprint compare | - |
| `logging_config.py` | 100 | Logging setup | logging |
| `data_paths.py` | 200 | Path constants | pathlib |
| `job_manager.py` | 150 | Job CRUD | json |
| `job_monitor.py` | 200 | PID monitoring | subprocess |
| `seed_integration.py` | 220 | Seed handling | seed_registry |
| `seed_registry.py` | 320 | Seed DB | sqlite3 |
| `story_seed.py` | 280 | Seed generation | - |
| `research_registry.py` | 350 | Research DB | sqlite3 |

### 5.2 Test Files

| File | Covers |
|------|--------|
| `tests/test_api_client.py` | api_client.py |
| `tests/test_api_endpoints.py` | research_api endpoints |
| `tests/test_data_paths.py` | data_paths.py |
| `tests/test_dedup_service.py` | dedup_service.py |
| `tests/test_embedder_mock.py` | embedder.py |
| `tests/test_faiss_index.py` | index.py |
| `tests/test_horror_story_generator.py` | horror_story_generator.py |
| `tests/test_job_manager.py` | job_manager.py |
| `tests/test_job_monitor.py` | job_monitor.py |
| `tests/test_jobs_router.py` | jobs.py router |
| `tests/test_logging_config.py` | logging_config.py |
| `tests/test_ollama_resource.py` | ollama_resource.py |
| `tests/test_prompt_builder.py` | prompt_builder.py |
| `tests/test_research_dedup.py` | research_dedup/ |
| `tests/test_research_registry.py` | research_registry.py |
| `tests/test_research_service.py` | research_service.py |
| `tests/test_seed_integration.py` | seed_integration.py |
| `tests/test_seed_registry.py` | seed_registry.py |
| `tests/test_similarity.py` | similarity.py |
| `tests/test_story_seed.py` | story_seed.py |
| `tests/test_story_seed_mock.py` | story_seed.py (mocked) |
| `tests/test_template_loader.py` | template_loader.py |

---

## 6. Current Problems

### 6.1 Structural Issues

1. **Flat Root Directory**
   - 15 Python modules at root level
   - No clear separation between generation, dedup, registry
   - Difficult to understand module relationships

2. **Phase-Based Naming**
   - `phase1_foundation/` and `phase2_execution/` are confusing
   - Names reflect historical development, not function
   - `phase2_execution/` contains only specs, no code

3. **Duplicate Output Locations**
   - Stories go to `generated_stories/` (legacy) or `data/stories/`
   - Unclear which is canonical

4. **Scattered Documentation**
   - 25+ markdown files in `docs/`
   - Mix of current and historical docs
   - No clear organization

### 6.2 Import Dependencies

Current import patterns are flat:
```python
from horror_story_generator import ...
from story_registry import ...
from similarity import ...
```

This works but:
- No namespace separation
- All modules must be in PYTHONPATH
- Difficult to extract components

---

## 7. Key Findings

1. **True Runtime Requirements:**
   - Root Python modules (15 files)
   - `research_api/` (FastAPI app)
   - `research_executor/` (Research CLI)
   - `research_dedup/` (FAISS dedup)
   - `research_integration/` (Card integration)
   - Foundation data files (KUs, templates, canonical)

2. **Safely Movable:**
   - All documentation
   - Test files (already in `tests/`)
   - Archive content
   - n8n workflows

3. **Requires Careful Migration:**
   - Root Python modules (import changes needed)
   - Foundation data (path references in code)

4. **Generated/Ephemeral:**
   - `data/` subdirectories
   - `generated_stories/`
   - `jobs/`
   - `logs/`

---

## 8. Conclusion

The current structure is functional but:
- Lacks clear organization
- Uses confusing phase-based naming
- Has flat module layout making extraction difficult
- Mixes runtime and documentation concerns

A restructuring should:
1. Group related Python modules
2. Rename phase directories to functional names
3. Consolidate documentation
4. Maintain backward compatibility during transition
