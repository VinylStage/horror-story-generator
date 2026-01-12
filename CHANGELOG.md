# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
