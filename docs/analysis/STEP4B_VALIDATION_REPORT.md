# STEP 4-B Validation Report

**Date:** 2026-01-12
**Status:** COMPLETED

---

## Summary

This report documents the validation phase following STEP 4-B (Execution Code Refactoring). All code structure tests pass. **Note: This validation focused on code structure and imports, not actual API calls.**

---

## Validation Scope

### What Was Tested

| Category | Description | Result |
|----------|-------------|--------|
| Static Checks | Import validation, syntax | ✅ PASS |
| Story Pipeline | Template loading, prompt building, seed selection | ✅ PASS |
| Research Pipeline | CLI help, card loading, research integration | ✅ PASS |
| API Server | Server startup, health endpoint, route listing | ✅ PASS |
| Unit Tests | All 472 test cases | ✅ PASS |
| Documentation | Core README updated | ✅ PASS |

### What Was NOT Tested

| Category | Reason |
|----------|--------|
| Actual Story Generation | Requires Claude API call (costs money) |
| Actual Research Generation | Requires Ollama running with qwen3:30b model |
| End-to-End Integration | Requires both Claude and Ollama available |

---

## Bugs Found and Fixed

### 1. `src/story/__init__.py` - Incorrect Export Names

**Error:**
```
ImportError: cannot import name 'select_seed_for_story' from 'src.story.seed_integration'
```

**Cause:** Export names didn't match actual function names in `seed_integration.py`

**Fix:** Updated to correct names:
- `select_seed_for_story` → `select_seed_for_generation`
- `format_seed_for_prompt` → `format_seed_for_system_prompt`

**Commit:** `3f5f00b`

---

### 2. `src/story/prompt_builder.py` - Type Error on Slicing

**Error:**
```
TypeError: unhashable type: 'slice' at line 341
```

**Cause:** `custom_request[:50]` failed when `custom_request` was a dict instead of string

**Fix:** Added type check before slicing:
```python
if not isinstance(custom_request, str):
    custom_request = str(custom_request)
```

**Commit:** `8adf1ff`

---

### 3. Test Files - Old Module Paths in Mock Patches

**Error:**
```
ModuleNotFoundError: No module named 'api_client'
ModuleNotFoundError: No module named 'research_api'
ModuleNotFoundError: No module named 'job_manager'
... (121 test failures)
```

**Cause:** Test files used old root-level module paths for mock patches

**Fix:** Updated all test files to use new `src.*` prefixed paths:
- `api_client` → `src.story.api_client`
- `research_api` → `src.api`
- `job_manager` → `src.infra.job_manager`
- `job_monitor` → `src.infra.job_monitor`
- `research_dedup` → `src.dedup.research`
- `seed_integration` → `src.story.seed_integration`
- `data_paths` → `src.infra.data_paths`

**Commit:** `cf38847`

---

### 4. `tests/test_jobs_router.py` - Incorrect Command Assertion

**Error:**
```
AssertionError: assert 'research_executor' in cmd
```

**Cause:** Test expected old `research_executor` module name

**Fix:** Changed assertion to expect `src.research.executor`

**Commit:** `cf38847`

---

### 5. `tests/test_data_paths.py` - Incorrect Project Root Test

**Error:**
```
AssertionError: assert (result / "data_paths.py").exists()
```

**Cause:** Test expected `data_paths.py` at project root (now in `src/infra/`)

**Fix:** Changed test to check for `main.py` at project root instead

**Commit:** `cf38847`

---

## Test Results Summary

```
======================= 472 passed, 7 warnings in 0.85s ========================
```

All tests pass. Warnings are related to async mock coroutines (not critical).

---

## Documentation Updates

### Updated Files

| File | Changes |
|------|---------|
| `docs/core/README.md` | Project structure, CLI reference paths |

### Pending Updates (Archive/Historical)

The following docs contain historical references and were intentionally NOT updated:
- `docs/analysis/EXECUTION_STRUCTURE_ANALYSIS.md` - Analysis document
- `docs/archive/*` - Historical work logs and proposals
- `docs/core/ARCHITECTURE.md` - May need future update
- `docs/core/CONTRIBUTING.md` - May need future update

---

## Commits Made During Validation

| Commit | Description |
|--------|-------------|
| `3f5f00b` | fix(story): correct function names in src/story/__init__.py |
| `8adf1ff` | fix(story): add type safety to build_user_prompt |
| `cf38847` | fix(tests): update mock paths for src/ package structure |
| `881efbe` | docs: update README.md with new src/ package structure |

---

## Entry Points Verified

### Story CLI
```bash
python main.py --help  # ✅ Works
```

### Research CLI
```bash
python -m src.research.executor --help  # ✅ Works
python -m src.research.executor list    # ✅ Works (13 cards found)
```

### API Server
```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8765
# ✅ Starts and responds to /health endpoint
```

---

## Recommendations

1. **Run actual generation test** when ready:
   ```bash
   # Story (requires ANTHROPIC_API_KEY)
   python main.py --max-stories 1

   # Research (requires Ollama with qwen3:30b)
   python -m src.research.executor run "test topic"
   ```

2. **Update remaining docs** if needed for external users:
   - `docs/core/ARCHITECTURE.md`
   - `docs/core/CONTRIBUTING.md`

3. **Consider CI/CD updates** if any pipelines reference old module paths

---

## Actual Generation Tests (Added 2026-01-12 01:41 KST)

### Story Generation Test ✅ PASS

```
python main.py --max-stories 1
```

| Metric | Value |
|--------|-------|
| Template | T-ECO-001 - Economic Annihilation |
| Model | claude-sonnet-4-5-20250929 |
| Story Length | 3,041 characters |
| Total Tokens | 4,098 |
| Generation Time | 67.8 seconds |
| Output File | `generated_stories/horror_story_20260112_014041.md` |
| Title | 잔액 (Balance) |

**Story Theme:** A man's bank balance mysteriously decreases through unexplained "system adjustments" - a horror exploration of economic anxiety.

---

### Research Generation Test ✅ PASS

```
python -m src.research.executor run "현대 한국 오피스텔의 고립과 공포" --tags horror korean urban
```

| Metric | Value |
|--------|-------|
| Model | qwen3:30b |
| Card ID | RC-20260112-014153 |
| Title | Concrete Cell: The Office Apartment Trap |
| Quality | good |
| Generation Time | 20 seconds |
| Output File | `data/research/2026/01/RC-20260112-014153.json` |

**Research Topic:** Modern Korean office apartments that trap residents in economic precarity and social isolation.

---

## Deduplication System Test (Added 2026-01-12 02:00 KST)

### Story Dedup Test ✅ PASS

Generated 5 stories with `--enable-dedup` flag:

| Story | Template | Dedup Signal | Similarity |
|-------|----------|--------------|------------|
| 계정 복구 | T-SYS-001 | LOW | - |
| 마지막 칸 | T-LIM-001 | LOW | - |
| 주민 평가 | T-APT-001 | LOW | - |
| 층간소음 | T-DOM-001 | LOW | - |
| 스마트홈 | T-DOM-002 | LOW | - |

All stories were correctly classified as unique (LOW similarity signal).

---

### Research Dedup Test ✅ PASS

**Bug Found & Fixed:**
- **Issue:** Research dedup used `qwen3:30b` model for embeddings, but this model doesn't support the `/api/embed` endpoint (HTTP 501)
- **Fix:** Changed default embedding model to `nomic-embed-text` (768 dimensions)
- **Commit:** `ea2bc13`

**Test Procedure:**
1. Generated 2 unique research cards (different topics)
2. Generated 3 duplicate research cards (similar Korean apartment/officetel isolation topics)
3. Rebuilt FAISS index with all 19 cards
4. Ran similarity check on duplicate cards

**Duplicate Detection Results:**

| Card ID | Topic | Nearest Card | Similarity | Signal |
|---------|-------|--------------|------------|--------|
| RC-20260112-014153 | 현대 한국 오피스텔의 고립과 공포 | RC-015248 | **0.9019** | HIGH |
| RC-20260112-015216 | 원룸 오피스텔에서의 고립감과 공포 | RC-015248 | **0.8934** | HIGH |
| RC-20260112-015233 | 한국 1인가구 아파트에서의 사회적 고립과 공포 | RC-014153 | **0.8749** | HIGH |
| RC-20260112-015248 | 서울 오피스텔의 고립과 공포 | RC-014153 | **0.9019** | HIGH |

All intentional duplicate cards were correctly detected with HIGH similarity signals (≥ 0.85).

---

## Conclusion

STEP 4-B refactoring validation is **COMPLETE**:

- ✅ All imports work with new `src/` structure
- ✅ All 472 unit tests pass
- ✅ CLI entry points work correctly
- ✅ API server starts and responds
- ✅ Core documentation updated
- ✅ **Actual story generation works** (Claude API)
- ✅ **Actual research generation works** (Ollama)
- ✅ **Story dedup system works** (SQLite + in-memory)
- ✅ **Research dedup system works** (FAISS + nomic-embed-text)

The codebase is fully functional after STEP 4-B refactoring. Both story and research generation pipelines work correctly with real API calls.
