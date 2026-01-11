# STEP 3: Target Structure Proposal

**Status:** Proposal (Not Executed)
**Date:** 2026-01-12
**Purpose:** Define clean, versioned repository structure

---

## 1. Proposed Directory Structure

```
horror-story-generator/
│
├── src/                          # All Python source code
│   ├── generator/                # Story generation modules
│   │   ├── __init__.py
│   │   ├── horror_story_generator.py
│   │   ├── api_client.py
│   │   ├── prompt_builder.py
│   │   ├── template_loader.py
│   │   └── logging_config.py
│   │
│   ├── research/                 # Research generation
│   │   ├── __init__.py
│   │   ├── cli.py               # (from research_executor/)
│   │   ├── executor.py
│   │   ├── prompt_template.py
│   │   ├── validator.py
│   │   ├── output_writer.py
│   │   ├── config.py
│   │   ├── loader.py            # (from research_integration/)
│   │   ├── selector.py
│   │   └── hooks.py
│   │
│   ├── api/                      # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── jobs.py
│   │   │   ├── research.py
│   │   │   └── dedup.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── jobs.py
│   │   │   ├── research.py
│   │   │   └── dedup.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── dedup_service.py
│   │       ├── research_service.py
│   │       └── ollama_resource.py
│   │
│   ├── dedup/                    # Deduplication logic
│   │   ├── __init__.py
│   │   ├── story_registry.py
│   │   ├── similarity.py
│   │   ├── research_dedup.py    # (from research_dedup/)
│   │   ├── embedder.py
│   │   └── faiss_index.py
│   │
│   ├── registry/                 # Data registries
│   │   ├── __init__.py
│   │   ├── research_registry.py
│   │   ├── seed_registry.py
│   │   └── seed_integration.py
│   │
│   ├── jobs/                     # Job management
│   │   ├── __init__.py
│   │   ├── manager.py           # (job_manager.py)
│   │   └── monitor.py           # (job_monitor.py)
│   │
│   └── common/                   # Shared utilities
│       ├── __init__.py
│       ├── data_paths.py
│       └── story_seed.py
│
├── assets/                       # Static content assets
│   ├── knowledge_units/
│   │   └── knowledge_units.json
│   ├── templates/
│   │   └── template_skeletons_v1.json
│   └── canonical/
│       ├── canonical_enum.md
│       ├── ku_canonical_features.json
│       └── resolved_canonical_keys.json
│
├── data/                         # Generated data (gitignored mostly)
│   ├── research/
│   │   ├── YYYY/MM/             # Research cards by date
│   │   ├── cards/
│   │   ├── vectors/
│   │   └── logs/
│   ├── stories/
│   ├── seeds/
│   └── jobs/
│
├── docs/                         # Documentation
│   ├── core/                     # Essential documentation
│   │   ├── README.md
│   │   ├── ARCHITECTURE.md
│   │   ├── API.md
│   │   └── CONTRIBUTING.md
│   │
│   ├── technical/                # Technical details
│   │   ├── canonical_enum.md
│   │   ├── decision_log.md
│   │   ├── runbook_24h_test.md
│   │   └── TRIGGER_API.md
│   │
│   └── archive/                  # Historical documents
│       ├── phase_docs/           # Old phase-based docs
│       ├── n8n_guides/           # n8n integration guides
│       ├── work_logs/            # Development logs
│       └── proposals/            # Old proposals
│
├── scripts/                      # Utility scripts
│   ├── run_story.sh
│   ├── run_research.sh
│   └── run_api.sh
│
├── tests/                        # Test suite (unchanged)
│   ├── __init__.py
│   ├── test_*.py
│   └── conftest.py
│
├── archive/                      # Legacy/deprecated files
│   └── templates_legacy/
│
├── logs/                         # Runtime logs
│
├── .github/                      # GitHub configuration
│   └── workflows/
│       └── release-please.yml
│
├── main.py                       # CLI entry point (thin wrapper)
├── pyproject.toml
├── .release-please-manifest.json
├── release-please-config.json
├── .env.example
├── .gitignore
├── LICENSE
└── README.md                     # Project README
```

---

## 2. Directory Purpose Definitions

### 2.1 `src/` - Source Code

All Python source code lives here, organized by domain.

| Subdirectory | Purpose | What Moves Here |
|--------------|---------|-----------------|
| `src/generator/` | Story generation | horror_story_generator.py, api_client.py, prompt_builder.py, template_loader.py, logging_config.py |
| `src/research/` | Research generation | research_executor/*, research_integration/* |
| `src/api/` | HTTP API | research_api/* |
| `src/dedup/` | Deduplication | story_registry.py, similarity.py, research_dedup/* |
| `src/registry/` | Data registries | research_registry.py, seed_registry.py, seed_integration.py |
| `src/jobs/` | Job management | job_manager.py, job_monitor.py |
| `src/common/` | Shared utilities | data_paths.py, story_seed.py |

**What Stays Out:**
- Test files (stay in `tests/`)
- Configuration files (stay at root)
- Data files (stay in `data/` or `assets/`)

### 2.2 `assets/` - Static Content

Static content required at runtime but not code.

| Subdirectory | Purpose | What Moves Here |
|--------------|---------|-----------------|
| `assets/knowledge_units/` | Knowledge unit data | phase1_foundation/01_knowledge_units/* |
| `assets/templates/` | Story templates | phase1_foundation/03_templates/* |
| `assets/canonical/` | Canonical mappings | phase1_foundation/02_canonical_abstraction/* |

**What Stays Out:**
- Raw research (archive)
- Legacy templates (archive)

### 2.3 `data/` - Generated Data

All runtime-generated data. Mostly gitignored.

| Subdirectory | Purpose | Generated By |
|--------------|---------|--------------|
| `data/research/` | Research cards | research_executor |
| `data/stories/` | Story outputs | main.py |
| `data/seeds/` | Seed registry | seed_registry.py |
| `data/jobs/` | Job metadata | job_manager.py |

**Note:** `generated_stories/` consolidates into `data/stories/`

### 2.4 `docs/` - Documentation

Three-tier documentation structure.

| Subdirectory | Purpose | What Goes Here |
|--------------|---------|----------------|
| `docs/core/` | Essential docs | README, ARCHITECTURE, API, CONTRIBUTING |
| `docs/technical/` | Deep-dive docs | canonical_enum, decision_log, runbook |
| `docs/archive/` | Historical | All phase docs, work logs, old proposals |

### 2.5 `scripts/` - Utility Scripts

Shell scripts for common operations.

| Script | Purpose |
|--------|---------|
| `run_story.sh` | Start story generation |
| `run_research.sh` | Run research executor |
| `run_api.sh` | Start API server |

### 2.6 `tests/` - Test Suite

Unchanged structure. Tests already well-organized.

### 2.7 `archive/` - Legacy Files

Files kept for reference but not used.

---

## 3. Migration Mapping

### 3.1 Root Python Files

| Current | Proposed | Notes |
|---------|----------|-------|
| `horror_story_generator.py` | `src/generator/horror_story_generator.py` | Core module |
| `api_client.py` | `src/generator/api_client.py` | Claude API |
| `prompt_builder.py` | `src/generator/prompt_builder.py` | Prompt construction |
| `template_loader.py` | `src/generator/template_loader.py` | Template loading |
| `logging_config.py` | `src/generator/logging_config.py` | Logging setup |
| `story_registry.py` | `src/dedup/story_registry.py` | Story dedup |
| `similarity.py` | `src/dedup/similarity.py` | Fingerprint compare |
| `data_paths.py` | `src/common/data_paths.py` | Path constants |
| `job_manager.py` | `src/jobs/manager.py` | Job CRUD |
| `job_monitor.py` | `src/jobs/monitor.py` | PID monitoring |
| `seed_integration.py` | `src/registry/seed_integration.py` | Seed handling |
| `seed_registry.py` | `src/registry/seed_registry.py` | Seed DB |
| `story_seed.py` | `src/common/story_seed.py` | Seed generation |
| `research_registry.py` | `src/registry/research_registry.py` | Research DB |
| `main.py` | `main.py` (stays) | Entry point |

### 3.2 Package Directories

| Current | Proposed | Notes |
|---------|----------|-------|
| `research_api/*` | `src/api/*` | FastAPI app |
| `research_executor/*` | `src/research/*` (merged) | Research CLI |
| `research_dedup/*` | `src/dedup/*` (merged) | Vector dedup |
| `research_integration/*` | `src/research/*` (merged) | Integration hooks |

### 3.3 Foundation Assets

| Current | Proposed | Notes |
|---------|----------|-------|
| `phase1_foundation/01_knowledge_units/` | `assets/knowledge_units/` | KU data |
| `phase1_foundation/03_templates/` | `assets/templates/` | Templates |
| `phase1_foundation/02_canonical_abstraction/` | `assets/canonical/` | Canonical maps |
| `phase1_foundation/00_raw_research/` | `docs/archive/raw_research/` | Historical |

### 3.4 Documentation

| Current | Proposed |
|---------|----------|
| `docs/README.md` | `docs/core/README.md` |
| `docs/system_architecture.md` | `docs/core/ARCHITECTURE.md` (merge with draft) |
| `docs/canonical_enum.md` | `docs/technical/canonical_enum.md` |
| `docs/decision_log.md` | `docs/technical/decision_log.md` |
| `docs/PHASE*.md` | `docs/archive/phase_docs/` |
| `docs/n8n_*.md` | `docs/archive/n8n_guides/` |
| `docs/work_log_*.md` | `docs/archive/work_logs/` |

---

## 4. Package Configuration

### 4.1 Updated pyproject.toml

```toml
[tool.poetry]
name = "horror-story-generator"
version = "0.3.0"
packages = [
    { include = "src" }
]

[tool.poetry.scripts]
horror-story = "src.generator.main:main"
research = "src.research.cli:main"
```

### 4.2 Import Style Changes

**Before:**
```python
from horror_story_generator import HorrorStoryGenerator
from story_registry import init_registry
```

**After:**
```python
from src.generator import HorrorStoryGenerator
from src.dedup import init_registry
```

---

## 5. Backward Compatibility

### 5.1 Transition Period

During migration:
1. Keep original files with deprecation warnings
2. Use symlinks or re-exports where possible
3. Update imports incrementally

### 5.2 Entry Points

`main.py` at root stays as thin wrapper:
```python
#!/usr/bin/env python
"""Entry point for backward compatibility."""
from src.generator.main import main

if __name__ == "__main__":
    main()
```

---

## 6. What This Structure Achieves

### 6.1 Benefits

1. **Clear Organization** - Related code grouped by domain
2. **No Phase Naming** - Functional names instead of historical
3. **Separable Components** - Each `src/` subdirectory could become a package
4. **Documentation Tiers** - Core, technical, archive separation
5. **Clean Data Separation** - Assets vs generated data vs code

### 6.2 Trade-offs

1. **Import Changes** - All imports need updating
2. **Path Updates** - data_paths.py needs revision
3. **Test Updates** - Test imports need updating
4. **Learning Curve** - Contributors must learn new structure

---

## 7. Open Questions for Human Review

1. **Keep `main.py` at root or move to `src/`?**
   - Proposal: Keep at root for ease of use

2. **Merge `research_executor` + `research_integration` into single `src/research/`?**
   - Proposal: Yes, they're tightly coupled

3. **Should `assets/` be `content/` or `resources/`?**
   - Proposal: `assets/` is clear and common

4. **Consolidate `generated_stories/` into `data/stories/`?**
   - Proposal: Yes, single output location

5. **Keep `logs/` at root or move to `data/logs/`?**
   - Proposal: Keep at root for visibility

---

## 8. Execution Status

**THIS IS A PROPOSAL ONLY.**

No files have been moved, deleted, or renamed.

Execution will occur in a later step after human approval.
