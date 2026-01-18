# Development Roadmap

**Status:** Active
**Version:** v1.5.0 <!-- x-release-please-version -->

---

## Current State Summary

The system currently supports:
- Story generation via Claude API with deduplication control
- Research generation via Ollama with FAISS-based similarity
- Trigger API for non-blocking job execution
- 24-hour continuous operation with graceful shutdown

---

## Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| Story Generation (Claude API) | Implemented | main.py CLI |
| Template System (15 templates) | Implemented | assets/templates/ |
| Knowledge Units (52 KUs) | Implemented | assets/knowledge_units/ |
| Story Deduplication (SQLite) | Implemented | src/registry/story_registry.py |
| Research Generation (Ollama) | Implemented | src/research/executor/ |
| Research Deduplication (FAISS) | Implemented | src/dedup/research/ |
| Trigger API | Implemented | src/api/ |
| Job Monitoring | Implemented | src/infra/job_monitor.py |
| Graceful Shutdown | Implemented | SIGINT/SIGTERM handling |
| **Job Scheduler Engine** | **Implemented** | src/scheduler/ (Phase 0-2) |
| **Scheduler API** | **Implemented** | /scheduler/*, /jobs CRUD (Phase 3) |

---

## Recently Implemented Features

### Job Scheduler System (v1.5.0)

스케줄러 기반 Job 실행 모델 구현.

**구현 범위:**
- Scheduler Engine (Phase 0-2)
  - SQLite 기반 Job persistence
  - Priority queue 및 position 기반 정렬
  - JobGroup sequential/parallel 실행
  - Crash recovery
- Scheduler API Integration (Phase 3)
  - `/scheduler/start`, `/stop`, `/status`
  - `/jobs` CRUD (POST, GET, PATCH, DELETE)
  - `/jobs/{id}/runs` 실행 이력
  - Legacy trigger endpoints deprecated

**Documentation:**
- [Job Scheduler Design](../technical/JOB_SCHEDULER_DESIGN.md)
- [API Contract](../job-scheduler/API_CONTRACT.md)
- [As-Is/To-Be API Design](../technical/job-scheduler-AS_IS_TO_BE_API_DESIGN-v1.md)

---

## Planned Features

### Near-Term (Next Release)

#### ~~Webhook Notifications~~ (IMPLEMENTED v1.3.0)

~~Enable callback notifications on job completion.~~

**Status:** ✅ Implemented in v1.3.0

---

#### ~~Batch Job Trigger~~ (IMPLEMENTED v1.4.0)

~~Trigger multiple jobs in a single request.~~

**Status:** ✅ Implemented in v1.4.0

---

#### Job Scheduler Templates & Cron (Phase 4)

JobTemplate 및 Cron 스케줄링 기능.

**Scope:**
- JobTemplate CRUD APIs
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
| Multimodal content (images) | Beyond current project goals |
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
| Test coverage gaps | Low | ~93% but some edge cases |

### Data

| Item | Priority | Notes |
|------|----------|-------|
| ~~Legacy research_cards.jsonl~~ | ~~Low~~ | **DONE (v1.3.1)** - Deprecated with warning |
| ~~Job history cleanup~~ | ~~Low~~ | **DONE (v1.3.1)** - Optional pruning via env vars |

---

## Version Milestones

### v0.3.x (Current)

- Story generation with dedup
- Research generation with FAISS
- Trigger API
- Job monitoring

### v0.4.0 (Next)

- Webhook notifications
- Batch job support
- n8n integration examples
- Documentation cleanup complete

### v0.5.0 (Future)

- Story embedding dedup
- Cultural weighting
- Improved CLI experience

### v1.0.0 (Stable)

- API schema frozen
- Full test coverage
- Production deployment guide
- Breaking changes resolved

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
| Job storage scalability? | File-based may not scale |
| Authentication approach? | API keys vs OAuth |

---

**Note:** All documentation reflects the current `src/` package structure (Post STEP 4-B). Priorities and scope may change based on user feedback.
