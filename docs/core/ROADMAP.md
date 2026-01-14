# Development Roadmap

**Status:** Active
**Version:** v1.6.0 <!-- x-release-please-version -->

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

---

## Planned Features

### Near-Term (Next Release)

#### Webhook Notifications

Enable callback notifications on job completion.

**Scope:**
- POST to user-specified URL on job status change
- Configurable events (succeeded, failed, cancelled)
- Retry logic for failed callbacks

**Proposed API:**
```json
{
  "topic": "...",
  "webhook_url": "https://example.com/callback",
  "events": ["succeeded", "failed"]
}
```

---

#### Batch Job Trigger

Trigger multiple jobs in a single request.

**Scope:**
- POST /jobs/batch/trigger
- Accept array of job specifications
- Return batch_id for status tracking
- GET /jobs/batch/{batch_id} for aggregate status

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

**Scope:**
- Parse story for structural elements
- Check alignment with template canonical_core
- Flag deviations for review

**Uncertainty:**
- Validation strictness level unclear
- May require LLM-based analysis

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
