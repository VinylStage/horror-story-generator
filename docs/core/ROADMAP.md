# Development Roadmap

**Status:** Active
**Version:** v1.7.0 <!-- x-release-please-version -->

---

## Current State Summary

The system currently supports:
- Story generation via Claude API with deduplication control
- Research generation via Ollama/Gemini with FAISS-based similarity
- Task Scheduler for queue-based task execution via HTTP API
- Thumbnail generation for stories (multi-provider)
- 24-hour continuous operation with graceful shutdown

---

## Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| Story Generation (Claude API) | Implemented | API + programmatic |
| Template System (15 templates) | Implemented | assets/templates/ |
| Knowledge Units (52 KUs) | Implemented | assets/knowledge_units/ |
| Story Deduplication (SQLite) | Implemented | src/registry/story_registry.py |
| Research Generation (Ollama/Gemini) | Implemented | src/research/executor/ |
| Research Deduplication (FAISS) | Implemented | src/dedup/research/ |
| Graceful Shutdown | Implemented | SIGINT/SIGTERM handling |
| **Task Scheduler Engine** | **Implemented** | src/scheduler/ (Phase 0-2) |
| **Scheduler API** | **Implemented** | /scheduler/*, /tasks CRUD (Phase 3) |
| **Thumbnail Generation** | **Implemented** | src/image/ (v1.6.1) |
| **Multimodal (images)** | **Implemented** | Multi-provider thumbnail support |

---

## Recently Implemented Features

### Task Scheduler System (v1.5.0)

스케줄러 기반 Task 실행 모델 구현.

**구현 범위:**
- Scheduler Engine (Phase 0-2)
  - SQLite 기반 Task persistence
  - Priority queue 및 position 기반 정렬
  - TaskGroup sequential/parallel 실행
  - Crash recovery
- Scheduler API Integration (Phase 3)
  - `/scheduler/start`, `/stop`, `/status`
  - `/tasks` CRUD (POST, GET, PATCH, DELETE)
  - `/tasks/{id}/runs` 실행 이력

**Documentation:**
- [Task Scheduler Design](../technical/TASK_SCHEDULER_DESIGN.md)
- [API Contract](../task-scheduler/API_CONTRACT.md)
- [Design Guards](../task-scheduler/DESIGN_GUARDS.md)

---

## Planned Features

### Near-Term (Next Release)

#### ~~Webhook Notifications~~ (IMPLEMENTED v1.3.0)

~~Enable callback notifications on task completion.~~

**Status:** ✅ Implemented in v1.3.0

---

#### ~~Batch Task Creation~~ (IMPLEMENTED v1.4.0)

~~Create multiple tasks in a single request.~~

**Status:** ✅ Implemented in v1.4.0 (via `POST /tasks` array input)

---

#### Task Scheduler Templates & Cron (Phase 4)

TaskTemplate 및 Cron 스케줄링 기능.

**Scope:**
- TaskTemplate CRUD APIs
- Cron Schedule APIs
- APScheduler 통합

---

#### n8n Integration Examples

Complete n8n workflow templates for common patterns.

**Scope:**
- Polling-based story generation workflow
- Research-then-story pipeline workflow
- Scheduled batch generation workflow

---

### Medium-Term

#### Story Embedding-Based Deduplication

Replace canonical fingerprint matching with semantic embeddings.

**Current State:**
- Stories compared by canonical dimension matching (5 dimensions)
- Binary match counting (matches / 5)

**Proposed:**
- Embed story text using sentence-transformers
- FAISS vector similarity (same as research)
- Hybrid scoring (canonical + semantic)

**Dependencies:**
- sentence-transformers library
- FAISS-cpu already in use

---

#### Cultural Weighting System

Prioritize Korean-specific content in KU/template selection.

**Current State:**
- Cultural context noted in KU metadata
- No weighting applied

**Proposed:**
- Cultural weight scoring function
- CLI flag: `--cultural-mode korean|universal`
- Weighted random selection

**Note:** Design exists in archived docs, not implemented.

---

#### Prompt Compiler

Automated prompt construction from template + KUs.

**Current State:**
- Manual/assisted KU selection
- prompt_builder.py constructs prompts

**Proposed:**
- Rule engine selects compatible KUs
- Structured prompt assembly with constraints
- Variation engine for parameter tweaking

**Dependencies:**
- Requires validation of current manual workflow
- May need updated prompt format

---

### Long-Term / Exploratory

#### Output Validation

Validate generated stories against canonical constraints.

**Status:** Partially Implemented (v1.4.1)

**Implemented (Issue #19, #20):**
- LLM-based extraction of canonical dimensions from story text
- Alignment scoring (story CK vs template CK)
- Configurable enforcement policies (none/warn/retry/strict)
- Retry and rejection based on alignment threshold

**Remaining Scope:**
- Structural element parsing (non-LLM based)
- Quality scoring beyond canonical alignment
- Human review interface for flagged stories

**Configuration:**
- `STORY_CK_ENFORCEMENT`: Policy level (default: warn)
- `STORY_CK_MIN_ALIGNMENT`: Threshold (default: 0.6)

---

#### Multi-Model Support

Support alternative LLMs for story generation.

**Candidates:**
- GPT-4 (OpenAI)
- Local models via Ollama
- Anthropic Claude variations

**Considerations:**
- Prompt format may need adaptation
- Quality comparison needed

---

#### Web UI

Browser-based interface for story generation.

**Scope:**
- Template browser and selection
- KU browser and selection
- Generation trigger and monitoring
- Story review and editing

**Dependencies:**
- API must be stable
- Authentication required

---

## Not Planned

The following are explicitly out of scope:

| Feature | Reason |
|---------|--------|
| ~~Multimodal content (images)~~ | **Implemented** (v1.6.1 thumbnail generation) |
| Distributed execution | Complexity vs. benefit |
| Real-time collaboration | Single-user design |
| Commercial API hosting | Local-first architecture |

---

## Technical Debt

### Documentation

| Item | Priority | Notes |
|------|----------|-------|
| Remove phase-based naming | High | All docs and directories |
| Consolidate scattered docs | High | This effort underway |
| Update outdated README | High | README_DRAFT.md created |
| Archive historical docs | Medium | DOCUMENT_MAP.md identifies targets |

### Code

| Item | Priority | Notes |
|------|----------|-------|
| ~~Unify output directories~~ | ~~Medium~~ | **DONE (v1.3.1)** - Now `data/novel/` |
| ~~Path constant centralization~~ | ~~Low~~ | **DONE (v1.3.1)** - `src/infra/data_paths.py` |
| Test coverage gaps | Low | ~76% with some edge cases |

### Data

| Item | Priority | Notes |
|------|----------|-------|
| ~~Legacy research_cards.jsonl~~ | ~~Low~~ | **DONE (v1.3.1)** - Deprecated with warning |
| ~~Task history cleanup~~ | ~~Low~~ | **DONE (v1.3.1)** - Optional pruning via env vars |

---

## Version Milestones

### v1.7.0 (Current)

- Task Scheduler with full CRUD API
- Thumbnail generation (multi-provider)
- Legacy trigger endpoints removed
- Webhook notifications for scheduler tasks

### v2.0.0 (Next Major)

- TaskTemplate & Cron scheduling (Phase 4)
- n8n integration examples
- Web UI (exploratory)
- Full test coverage improvements

---

## Contributing

See `CONTRIBUTING.md` for development guidelines.

To propose a new feature:
1. Open an issue with the proposal
2. Reference this roadmap
3. Discuss approach before implementation

---

## Open Questions

| Question | Context |
|----------|---------|
| Optimal KU count per template? | Currently 2-5, needs validation |
| Embedding model choice? | multilingual-MiniLM vs ko-sroberta |
| Task storage scalability? | SQLite-based may not scale |
| Authentication approach? | API keys vs OAuth |

---

**Note:** All documentation reflects the current `src/` package structure (Post STEP 4-B). Priorities and scope may change based on user feedback.
