# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.3](https://github.com/VinylStage/horror-story-generator/compare/v1.4.2...v1.4.3) (2026-01-15)


### Code Refactoring

* sync develop branch improvements ([e179aed](https://github.com/VinylStage/horror-story-generator/commit/e179aed990cf8140eea900d65d34e98b9e69e8db))

## [1.4.2](https://github.com/VinylStage/horror-story-generator/compare/v1.4.1...v1.4.2) (2026-01-15)


### Code Refactoring

* enforce canonical key constraints on story output ([#20](https://github.com/VinylStage/horror-story-generator/issues/20)) ([#67](https://github.com/VinylStage/horror-story-generator/issues/67)) ([463e742](https://github.com/VinylStage/horror-story-generator/commit/463e742ec94cce8b205c010b16b5c8bc7d590e1a))

## [1.4.1](https://github.com/VinylStage/horror-story-generator/compare/v1.4.0...v1.4.1) (2026-01-14)


### Bug Fixes

* disable draft releases for proper tag creation ([1462f8b](https://github.com/VinylStage/horror-story-generator/commit/1462f8bbbc76c41b17909b75f90de3f8c01b0aef))
* disable draft releases for proper tag creation ([f9ede6c](https://github.com/VinylStage/horror-story-generator/commit/f9ede6c5c56f34d9b62f5abb8e0e4598f5820148))

## [1.4.0](https://github.com/VinylStage/horror-story-generator/compare/v1.3.2...v1.4.0) (2026-01-14)


### Features

* add n8n API integration workflows and guide ([#39](https://github.com/VinylStage/horror-story-generator/issues/39)) ([4d33560](https://github.com/VinylStage/horror-story-generator/commit/4d33560981b62df870144c6b90df44b4ce34df9e)), closes [#9](https://github.com/VinylStage/horror-story-generator/issues/9)
* **api:** add batch job trigger API endpoints ([b2affdb](https://github.com/VinylStage/horror-story-generator/commit/b2affdb0a20a08db7869a1994451ceeb09e3c3c8))
* **api:** add batch job trigger API endpoints ([685f003](https://github.com/VinylStage/horror-story-generator/commit/685f00371e6a902272db13909c608ebd1296aabe))


### Bug Fixes

* add issues write permission for release-please ([596b659](https://github.com/VinylStage/horror-story-generator/commit/596b6597b16282248545e6724fd79c9ebb7d7893))
* add issues write permission for release-please ([a9bc8ed](https://github.com/VinylStage/horror-story-generator/commit/a9bc8edc69a1484b17fc37598b66ed4067ffd97b))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([c8eec66](https://github.com/VinylStage/horror-story-generator/commit/c8eec66626e4df4440ae5ca11a149b28562ec717))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([d9ac683](https://github.com/VinylStage/horror-story-generator/commit/d9ac6838cbc01ad35098a248b1b380e60e13e2d8))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([3712361](https://github.com/VinylStage/horror-story-generator/commit/371236113182d1fc6b99d3e3bc1215197452d762))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([b4e75ed](https://github.com/VinylStage/horror-story-generator/commit/b4e75ed7b29baa585770372d3fa68d4c1b9da613))
* reset all versions to 1.3.2 and clean invalid releases ([570c9f3](https://github.com/VinylStage/horror-story-generator/commit/570c9f3a488e364a9d1de7c50eb784f8888beb7c))
* reset all versions to 1.3.2 and clean invalid releases ([4a23c79](https://github.com/VinylStage/horror-story-generator/commit/4a23c796771b39010b1f94f6e13762ecb7470e31))
* **test:** update test_run_research_error to expect 502 ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([a941982](https://github.com/VinylStage/horror-story-generator/commit/a941982e8a4ca0671c17a7faaa0918dfc8d7c9cf))
* use token-based loop prevention for release-please ([24b90ea](https://github.com/VinylStage/horror-story-generator/commit/24b90ea31d84da6cf82ad4d2f317d54e231e9d10))
* use token-based loop prevention for release-please ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([45ffb6f](https://github.com/VinylStage/horror-story-generator/commit/45ffb6f0dad668b27d5f9e3c109614da02887a70))


### Documentation

* add release-please version annotations to all docs ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([7d2c563](https://github.com/VinylStage/horror-story-generator/commit/7d2c5635e400687390ea2edb1fcb4f9a8e0b4f1a))
* **api:** add missing endpoints and improve model selection docs ([756e90d](https://github.com/VinylStage/horror-story-generator/commit/756e90d354fee997f8ac076051c325050f402642))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([67bf55c](https://github.com/VinylStage/horror-story-generator/commit/67bf55c34a4b7debe6c18cbfa769ee9aa631f38e))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([bb10476](https://github.com/VinylStage/horror-story-generator/commit/bb10476ac34ba555e73dfa47588d398d5f0706fe))
* consolidate scattered documentation ([62372a5](https://github.com/VinylStage/horror-story-generator/commit/62372a53761f184a009a0b1cd7b4372d4ae34dd2))
* consolidate scattered documentation ([316a84d](https://github.com/VinylStage/horror-story-generator/commit/316a84d3069ec5fe6cdec484f8d5ac8818290230))
* document environment variable restart requirement ([bc20b47](https://github.com/VinylStage/horror-story-generator/commit/bc20b47490cfe82a256723dab81a1807900ad619))
* document environment variable restart requirement ([189e61d](https://github.com/VinylStage/horror-story-generator/commit/189e61dbcfe602bad0fd97f1ac18a1b804f13856))
* **readme:** update CLI reference with model options ([0cca187](https://github.com/VinylStage/horror-story-generator/commit/0cca187401f7f720c5cebaa9a91676b6a4815342))
* remove phase-based naming from directories and code ([6a2ae97](https://github.com/VinylStage/horror-story-generator/commit/6a2ae975488c662b0bb00b6dbb42f05943dbd198))
* remove phase-based naming from directories and code ([b31262d](https://github.com/VinylStage/horror-story-generator/commit/b31262d5087d3ffebb7a18a78f63bc5e3d85da02))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([d979938](https://github.com/VinylStage/horror-story-generator/commit/d97993833414f1f54c8b2bb459c500534a527756))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([aba554b](https://github.com/VinylStage/horror-story-generator/commit/aba554ba930445b7a6f8a4994bd598d5daa3840e))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([fb3c048](https://github.com/VinylStage/horror-story-generator/commit/fb3c04827cd58c79252eaa018959d92bc911c9a7))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([c6c4237](https://github.com/VinylStage/horror-story-generator/commit/c6c42374f9742e9fa2107abb010f1f003210e43d))
* **todo:** add TODO-029 for GEMINI_MODEL env var rename ([303a9a5](https://github.com/VinylStage/horror-story-generator/commit/303a9a51fe91be123e1f1b6258325ff8a78e7980))
* **todo:** add TODO-030 for Research API error propagation (P1) ([f4ed308](https://github.com/VinylStage/horror-story-generator/commit/f4ed3089694f9195d261f9dddfeab9c716ebab32))
* **todo:** add TODO-031 and detailed descriptions for API issues ([d218079](https://github.com/VinylStage/horror-story-generator/commit/d21807911c582179f53f3282641a372ed2bf33b7))
* **todo:** add TODO-032 for webhook support on sync endpoints ([190b528](https://github.com/VinylStage/horror-story-generator/commit/190b52872be17d1373c9e4ad2b615dd0ba05c762))
* update all document version headers to v1.3.2 ([f0ce1fd](https://github.com/VinylStage/horror-story-generator/commit/f0ce1fd8e28dcf890d24ce5ba2225f566569c86c))
* update version references to v1.3.2 ([a15c4b7](https://github.com/VinylStage/horror-story-generator/commit/a15c4b7f0a09cf906a2cfb99d9f71f18a0b1a7b2))


### Technical Improvements

* add CI workflow for PR validation ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([4ee1103](https://github.com/VinylStage/horror-story-generator/commit/4ee1103f9a0c71882eece61144f448d99ec1c64d))
* configure release-please for automatic versioning ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([684febd](https://github.com/VinylStage/horror-story-generator/commit/684febdd10765cca4506c205526a0b07aa290b71))
* migrate TODOs to GitHub Issues ([#1](https://github.com/VinylStage/horror-story-generator/issues/1)) ([f031078](https://github.com/VinylStage/horror-story-generator/commit/f031078d95cb11343b53f0eacdc522b33fbcedda))

## [1.3.2] - 2026-01-13

### Security

- **CVE-2025-27600** (High): Starlette DoS via Range header merging - Fixed
- **CVE-2024-47874** (Medium): Starlette DoS in multipart forms - Fixed

### Dependencies

- FastAPI: ^0.115.0 → ^0.128.0
- Starlette: 0.46.2 → 0.50.0

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
