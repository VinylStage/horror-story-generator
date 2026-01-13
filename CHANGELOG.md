# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.1] - 2026-01-13

### Changed

- **Path Centralization (TODO-017)**
  - All path management centralized in `src/infra/data_paths.py`
  - Consistent path resolution across all modules
  - Environment variable overrides for all major paths

- **Output Directory Unification (TODO-016)**
  - Default novel output: `data/novel` (previously `generated_stories/`)
  - New env var: `NOVEL_OUTPUT_DIR` for custom path
  - Backward compatible with existing `OUTPUT_DIR` env var

- **Job Pruning (TODO-019)**
  - Optional automatic job history cleanup
  - Age-based pruning: `JOB_PRUNE_DAYS` (default: 30)
  - Count-based pruning: `JOB_PRUNE_MAX_COUNT` (default: 1000)
  - Disabled by default: `JOB_PRUNE_ENABLED=false`

### Deprecated

- **Legacy research_cards.jsonl (TODO-018)**
  - Accessing legacy path now emits `DeprecationWarning`
  - Read-only support maintained for backward compatibility
  - Use `data/research/` directory structure instead

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NOVEL_OUTPUT_DIR` | `data/novel` | Story output directory |
| `JOB_DIR` | `jobs/` | Job files directory |
| `JOB_PRUNE_ENABLED` | `false` | Enable automatic job pruning |
| `JOB_PRUNE_DAYS` | `30` | Prune jobs older than N days |
| `JOB_PRUNE_MAX_COUNT` | `1000` | Keep at most N recent jobs |

### Files Modified

- `src/infra/data_paths.py` - Extended with novel, jobs, and legacy path functions
- `src/infra/job_manager.py` - Centralized paths, added pruning functions
- `src/infra/job_monitor.py` - Centralized paths
- `src/story/generator.py` - Centralized paths
- `main.py` - Deprecated `run_research_stub()`

---

## [1.3.0] - 2026-01-13

### Added

- **Webhook Notifications (TODO-020)**
  - HTTP POST callbacks on job completion
  - Configurable events: `succeeded`, `failed`, `skipped`
  - Retry logic with exponential backoff (3 attempts)
  - New fields: `webhook_url`, `webhook_events` in trigger requests
  - New response fields: `webhook_sent`, `webhook_error`

- **"Skipped" Job Status**
  - New status for expected skip scenarios (e.g., duplicate detection)
  - Semantically distinct from failure - represents expected behavior
  - Webhook-triggerable like succeeded/failed

### Changed

- `StoryTriggerRequest` and `ResearchTriggerRequest` schemas extended with webhook fields
- `JobStatusResponse` includes webhook delivery status
- `JobMonitorResult` includes `reason` and `webhook_processed` fields
- Job monitor now detects and reports duplicate detection as "skipped"

### Files Added

- `src/infra/webhook.py` - Webhook notification service

### Files Modified

- `src/infra/job_manager.py` - JobStatus extended, Job dataclass with webhook fields
- `src/infra/job_monitor.py` - Webhook integration, skip detection
- `src/api/schemas/jobs.py` - Request/response schemas with webhook support
- `src/api/routers/jobs.py` - Webhook configuration in triggers

---

## [1.2.1] - 2026-01-13

### Fixed

- API story router method name mismatch (`get_recent_stories` → `load_recent_accepted`)

### Added

- Story CLI module (`src/story/cli.py`) for topic-based generation testing

### Verified

- CLI topic-based story generation (with/without existing research)
- API story generation endpoints (`POST /story/generate`, `GET /story/list`)
- Auto research → story injection pipeline
- Story-level deduplication (signature-based)
- Model selection (Claude / Ollama)
- Full E2E pipeline integrity (11/11 tests PASS)

### Reference

- Bug fix commit: `6119d7b`
- Test report: `docs/verification/STORY_GENERATION_E2E_TEST.md`

---

## [1.2.0] - 2026-01-13

### Added

- **Model Selection**
  - Story generation: Claude Sonnet (default) or Ollama models
  - Research generation: Ollama (default) or Gemini models
  - CLI flag: `--model ollama:qwen3:30b` for story, `--model gemini` for research

- **Gemini Deep Research Agent**
  - Optional research execution mode using `deep-research-pro-preview-12-2025`
  - Google AI Studio integration (standard generate_content API)
  - CLI flag: `--model deep-research`
  - Environment: `GEMINI_ENABLED=true`, `GEMINI_API_KEY`

- **Full Pipeline Verification**
  - Comprehensive real-world execution tests (CLI + API)
  - Automated pipeline integrity checks
  - Verification reports in `docs/verification/`

### Changed

- Research executor now loads dotenv before module imports
- Simplified GeminiDeepResearchProvider to use standard API

### Verified

- CLI: Local research (Ollama), Story generation (Claude/Ollama)
- API: Health, research endpoints, story job triggers
- Pipeline: Research auto-injection, dedup modules, unit tests (21/21)

---

## [1.1.0] - 2026-01-12

**This release is operationally sealed.**

### Added

- **Unified Research→Story Pipeline**
  - Automatic research card selection based on template affinity
  - Research context injection into story prompts
  - Full traceability in story metadata (`research_used`, `research_injection_mode`)

- **Research-Level Deduplication**
  - FAISS-based semantic similarity using `nomic-embed-text`
  - Dedup levels: LOW (<0.70), MEDIUM (0.70-0.85), HIGH (≥0.85)
  - HIGH cards excluded from story injection by default

- **Story-Level Deduplication**
  - SHA256 signature based on `canonical_core + research_used`
  - Pre-generation duplicate check (before API call)
  - WARN mode (default): continues with alternate template
  - STRICT mode: aborts generation

- **Registry Backup Mechanism**
  - Automatic backup before schema migration
  - Backup naming: `{db}.backup.{version}.{timestamp}.db`
  - Non-destructive, stdlib-only implementation

- **CLI Resource Cleanup**
  - Research executor automatically unloads Ollama models after execution
  - Signal handlers (SIGINT/SIGTERM) for graceful shutdown
  - Prevents VRAM leakage during batch operations

- **Canonical Core Normalization**
  - 5-dimension fingerprinting (setting, fear, antagonist, mechanism, twist)
  - Consistent normalization across templates and research cards

### Changed

- Story registry schema upgraded to v1.1.0
  - Added `story_signature` column
  - Added `canonical_core_json` column
  - Added `research_used_json` column
  - Added signature index for fast lookups

- Unified version management
  - Single source of truth in `src/__init__.py`
  - All submodules import version from parent
  - Package version synced: pyproject.toml, API, health endpoint

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_INJECT_RESEARCH` | `true` | Enable research auto-injection |
| `RESEARCH_INJECT_TOP_K` | `1` | Number of cards to inject |
| `ENABLE_STORY_DEDUP` | `true` | Enable story-level dedup |
| `STORY_DEDUP_STRICT` | `false` | Abort on duplicate |

### Verified

- All verification axes passed
- Full pipeline smoke test passed
- No known blocking issues

---

## [1.0.0] - 2026-01-08

Initial release with basic story generation pipeline.

### Added

- Claude API-based horror story generation
- 15 template skeletons with canonical fingerprints
- 52 knowledge units across 4 categories
- SQLite-based story registry
- 24-hour continuous operation support
- Graceful shutdown handling
