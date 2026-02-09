# Release v1.2.1 Summary

**Version:** v1.2.1
**Release Date:** 2026-01-13
**Verdict:** GO

---

## Included Commits

| Commit | Description |
|--------|-------------|
| `fd42359` | feat(story): add topic-based story generation and API expansion |
| `f39b54f` | docs: update API and architecture docs for v1.2.x story generation |
| `6119d7b` | fix(api): correct story router method name + add CLI + E2E test report |
| `eeb9b48` | chore(release): bump version to v1.2.1 |
| `ae7e1fe` | docs: add v1.2.1 operational notes and verification status |

---

## Test Status

**Result:** 11/11 PASS

| Category | Tests | Status |
|----------|-------|--------|
| CLI Tests | 5 | ALL PASS |
| API Tests | 4 | ALL PASS |
| E2E Integrity | 2 | ALL PASS |

### Test Details

- A-1: Story generation (no input) - PASS
- A-2: Story with topic (research exists) - PASS
- A-3: Story with topic (research NOT exists) - PASS
- A-4: Story-level dedup verification - PASS
- A-5: Model selection (Ollama) - PASS
- B-1: POST /story/generate (no topic) - PASS
- B-2: POST /story/generate (with topic) - PASS
- B-3: GET /story/list - PASS
- B-4: CLI vs API signatures - PASS
- C-1: E2E Pipeline integrity - PASS
- C-2: Metadata traceability - PASS

---

## Bug Fixed

**Issue:** API story router used non-existent method `get_recent_stories()`
**Fix:** Changed to `load_recent_accepted()` in `src/api/routers/story.py`
**Commit:** `6119d7b`

---

## Known Limitations

None blocking.

**Operational Note:** API server may fail on initial startup due to port conflicts or missing ENV. Resolution: restart after killing existing process or verifying `.env`.

---

## Release Artifacts

| Artifact | Location |
|----------|----------|
| Tag | `v1.2.1` |
| Changelog | `CHANGELOG.md` |
| E2E Test Report | `docs/verification/STORY_GENERATION_E2E_TEST.md` |
| Operational Status | `docs/OPERATIONAL_STATUS.md` |

---

## Verification

- Full E2E test execution completed
- All CLI and API endpoints verified
- Metadata traceability confirmed
- Story-level deduplication functional
- Model selection (Claude/Ollama) verified

---

**Release Verdict:** GO

**Sealed by:** Claude Opus 4.5
**Date:** 2026-01-13
