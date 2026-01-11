# System Architecture

**Status:** Draft
**Last Updated:** 2026-01-12

---

## Overview

The Horror Story Generator is a multi-pipeline content generation system with three execution paths:

1. **Story Generation** - Claude API-based horror story creation
2. **Research Generation** - Ollama-based research card creation
3. **Trigger API** - Non-blocking job execution via HTTP

All pipelines share common infrastructure for deduplication, storage, and monitoring.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Entry Points                                │
├─────────────────────┬──────────────────────┬────────────────────────────┤
│  python main.py     │  python -m research  │  uvicorn research_api...   │
│  (Story CLI)        │  _executor run       │  (Trigger API)             │
└─────────┬───────────┴──────────┬───────────┴──────────────┬─────────────┘
          │                      │                          │
          ▼                      ▼                          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐
│ HorrorStory     │    │ Research        │    │ FastAPI Router          │
│ Generator       │    │ Generator       │    │ (jobs.py)               │
└────────┬────────┘    └────────┬────────┘    └───────────┬─────────────┘
         │                      │                         │
         ▼                      ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐
│ Claude API      │    │ Ollama API      │    │ subprocess.Popen        │
│ (api_client)    │    │ (ollama_client) │    │ (CLI execution)         │
└────────┬────────┘    └────────┬────────┘    └───────────┬─────────────┘
         │                      │                         │
         ▼                      ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Shared Infrastructure                             │
├─────────────────┬──────────────────────┬────────────────────────────────┤
│ Story Registry  │ Research Dedup       │ Job Manager                    │
│ (SQLite)        │ (FAISS + SQLite)     │ (File-based JSON)              │
└─────────────────┴──────────────────────┴────────────────────────────────┘
         │                      │                         │
         ▼                      ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Storage Layer                                  │
├─────────────────┬──────────────────────┬────────────────────────────────┤
│ data/stories/   │ data/research/       │ jobs/                          │
│ stories.db      │ research_registry.db │ logs/                          │
└─────────────────┴──────────────────────┴────────────────────────────────┘
```

---

## Pipeline 1: Story Generation

### Flow

```
1. Template Selection
   └─> template_manager.py loads from phase1_foundation/03_templates/

2. Knowledge Unit Selection
   └─> ku_selector.py selects from phase1_foundation/01_knowledge_units/

3. Prompt Construction
   └─> prompt_builder.py combines template + KUs into system/user prompts

4. API Call
   └─> api_client.py calls Claude API (claude-sonnet-4-5)

5. Deduplication Check (if enabled)
   └─> story_registry.py computes canonical fingerprint similarity
   └─> HIGH signal triggers regeneration (max 2 retries)

6. Storage
   └─> story_saver.py saves to generated_stories/ or data/stories/
   └─> story_registry.py records in SQLite
```

### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Generator | `horror_story_generator.py` | Orchestrates generation pipeline |
| Template Manager | `template_manager.py` | Loads/selects templates |
| KU Selector | `ku_selector.py` | Selects compatible Knowledge Units |
| Prompt Builder | `prompt_builder.py` | Constructs LLM prompts |
| API Client | `api_client.py` | Claude API communication |
| Story Saver | `story_saver.py` | File persistence |
| Story Registry | `story_registry.py` | Deduplication database |

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

```
1. Topic Input
   └─> CLI receives topic and tags

2. Prompt Construction
   └─> research_generator.py builds research prompt

3. LLM Generation
   └─> ollama_client.py calls local Ollama (qwen3:30b)

4. Validation
   └─> validator.py parses JSON, checks required fields

5. FAISS Indexing
   └─> faiss_index.py creates embedding, adds to index

6. Deduplication Check
   └─> research_dedup_manager.py computes vector similarity

7. Storage
   └─> Research card saved to data/research/
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
| CLI | `research_executor/cli.py` | Command-line interface |
| Generator | `research_executor/research_generator.py` | Prompt + generation |
| Ollama Client | `research_executor/ollama_client.py` | Ollama API communication |
| Validator | `research_executor/validator.py` | Output parsing/validation |
| FAISS Index | `research_integration/faiss_index.py` | Vector storage |
| Dedup Manager | `research_integration/research_dedup_manager.py` | Similarity checking |

---

## Pipeline 3: Trigger API

### Design Principle

> **CLI = Source of Truth**

The API does not contain business logic. It triggers CLI commands via subprocess and monitors their execution.

### Flow

```
1. HTTP Request
   └─> POST /jobs/story/trigger or /jobs/research/trigger

2. Job Creation
   └─> job_manager.py creates Job record (JSON file)

3. CLI Launch
   └─> subprocess.Popen executes main.py or research_executor

4. Immediate Response
   └─> 202 Accepted with job_id

5. Background Monitoring
   └─> job_monitor.py polls PID status

6. Completion Detection
   └─> Process exit triggers status update
   └─> Artifacts collected from data/ directory
```

### Job Lifecycle

```
queued → running → succeeded
                 → failed
                 → cancelled
```

### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Router | `research_api/routers/jobs.py` | HTTP endpoints |
| Schemas | `research_api/schemas/jobs.py` | Pydantic models |
| Job Manager | `job_manager.py` | Job CRUD operations |
| Job Monitor | `job_monitor.py` | PID polling, status updates |

### Job Storage

Jobs are stored as JSON files:

```
jobs/
└── {job_id}.json

{
  "job_id": "abc-123-def",
  "type": "story_generation",
  "status": "running",
  "pid": 12345,
  "log_path": "logs/story_abc-123-def.log",
  "artifacts": [],
  "created_at": "2026-01-12T10:00:00",
  "started_at": "2026-01-12T10:00:01"
}
```

---

## Foundation Assets

### Knowledge Units (52 total)

Located in `phase1_foundation/01_knowledge_units/`

| Category | Count | Description |
|----------|-------|-------------|
| horror_concept | 14 | Theoretical foundations |
| horror_theme | 15 | Specific motifs/scenarios |
| social_fear | 17 | Real-world systemic threats |
| writing_technique | 6 | Craft techniques |

### Templates (15 total)

Located in `phase1_foundation/03_templates/`

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
| Story Registry | `data/stories.db` | Story dedup fingerprints |
| Research Registry | `data/research_registry.db` | Research card metadata |

### File Storage

| Directory | Contents |
|-----------|----------|
| `data/stories/` | Generated story JSON files |
| `data/research/` | Research card JSON files |
| `generated_stories/` | Legacy story output (Markdown) |
| `jobs/` | Job metadata JSON files |
| `logs/` | Execution logs |

---

## External Dependencies

| Service | Purpose | Required |
|---------|---------|----------|
| Claude API | Story generation | Yes |
| Ollama | Research generation | Optional |

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

## Design Decisions

Key architectural decisions are documented in `docs/decision_log.md`:

- **D-001**: CLI as source of truth for business logic
- **D-002**: Hybrid KU selection (category + canonical matching)
- **D-003**: Assisted manual generation (not fully automated)
- **D-004**: HIGH-only blocking policy for deduplication
- **D-005**: File-based job storage for simplicity

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

**Note:** This is a draft document consolidating information from multiple sources. See `docs/DOCUMENT_MAP.md` for source references.
