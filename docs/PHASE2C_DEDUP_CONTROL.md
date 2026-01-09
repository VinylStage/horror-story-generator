# Phase 2C: Dedup Control (HIGH-only)

**Date:** 2026-01-09
**Status:** IMPLEMENTED
**Scope:** SQLite persistent registry + HIGH-only dedup control

**References:**
- [Phase 2A: Template Activation](./PHASE2A_TEMPLATE_ACTIVATION.md)
- [Phase 2B: Generation Memory](./PHASE2B_GENERATION_MEMORY.md)
- [Phase 2 Preparation Analysis](./PHASE2_PREPARATION_ANALYSIS.md)

---

## 1. Policy Summary

| Signal | Action |
|--------|--------|
| LOW | **ACCEPT** - save story immediately |
| MEDIUM | **ACCEPT** - save story immediately |
| HIGH | **RETRY** - up to 2 regeneration attempts |

**MEDIUM is NOT blocked.** Only HIGH triggers retry logic.

---

## 2. Retry Logic

When HIGH similarity is detected:

| Attempt | Template Selection | On HIGH |
|---------|-------------------|---------|
| 0 (initial) | Normal selection | → Attempt 1 |
| 1 | Normal selection | → Attempt 2 |
| 2 | **Forced template change** | → SKIP |

### Forced Template Change (Attempt 2 only)

On Attempt 2, previously used template IDs are excluded:

```python
skeleton = select_random_template(exclude_template_ids={template_from_attempt_0, template_from_attempt_1})
```

This ensures a different thematic direction for the final attempt.

### SKIP Behavior

When all attempts fail:
- Story file is **NOT saved** to `generated_stories/`
- Registry records the attempt with `accepted=0`
- Loop continues to next iteration
- No infinite loop

---

## 3. SQLite Schema

**File:** `./data/story_registry.db` (configurable via `STORY_REGISTRY_DB_PATH`)

### Tables

#### `meta`
```sql
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```
Stores `schema_version` for future migrations.

#### `stories`
```sql
CREATE TABLE stories (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT,
    template_id TEXT,
    template_name TEXT,
    semantic_summary TEXT NOT NULL,
    similarity_method TEXT NOT NULL,
    accepted INTEGER NOT NULL,  -- 1=accepted, 0=skipped
    decision_reason TEXT NOT NULL,
    source_run_id TEXT
);
```

#### `story_similarity_edges`
```sql
CREATE TABLE story_similarity_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    story_id TEXT NOT NULL,
    compared_story_id TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    signal TEXT NOT NULL,  -- LOW/MEDIUM/HIGH
    method TEXT NOT NULL
);
```

---

## 4. Persistence Bridge

On process start (when `--enable-dedup` is used):

1. Initialize SQLite registry
2. Load last N accepted stories (default: 200)
3. Convert to Phase 2B in-memory format
4. Use for similarity comparison

This bridges Phase 2B (in-memory) with Phase 2C (persistent).

```
Process Start
    ↓
init_registry(db_path)
    ↓
load_recent_accepted(limit=200)
    ↓
load_past_stories_into_memory(records)
    ↓
Generation loop with dedup control
    ↓
Process Exit → close_registry()
```

---

## 5. CLI Usage

```bash
# Enable dedup control
python main.py --enable-dedup --max-stories 10

# Custom DB path
python main.py --enable-dedup --db-path ./custom/path.db

# Load more history
python main.py --enable-dedup --load-history 500

# Research stub (testing)
python main.py --run-research-stub
```

---

## 6. Log Output Examples

### Normal Accept (LOW/MEDIUM)
```
[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase2C][CONTROL] 중복 제어 생성 시작
[Phase2C][CONTROL] 정책: HIGH만 거부, LOW/MEDIUM 수락
[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase2C][CONTROL] Attempt 0/2
[Phase2C][CONTROL]   템플릿: T-DOM-001 - Domestic Confinement
[Phase2B][OBSERVE] 유사도 관측 결과:
[Phase2B][OBSERVE]   신호 수준: MEDIUM
[Phase2C][CONTROL]   신호: MEDIUM
[Phase2C][CONTROL]   결정: ACCEPT
[Phase2C][CONTROL] 저장 완료: ./generated_stories/horror_story_20260109_123456.md
[Phase2C][CONTROL] Registry 저장: 20260109_123456 (ACCEPTED, accepted)
```

### HIGH → Retry → Accept
```
[Phase2C][CONTROL] Attempt 0/2
[Phase2C][CONTROL]   템플릿: T-SYS-001 - Systemic Erosion
[Phase2C][CONTROL]   신호: HIGH
[Phase2C][CONTROL]   결정: RETRY (HIGH 감지)
[Phase2C][CONTROL]   다음 시도로 진행...
[Phase2C][CONTROL] Attempt 1/2
[Phase2C][CONTROL]   템플릿: T-MED-001 - Medical Debt Spiral
[Phase2C][CONTROL]   신호: LOW
[Phase2C][CONTROL]   결정: ACCEPT
```

### HIGH → All Attempts Fail → SKIP
```
[Phase2C][CONTROL] Attempt 2/2
[Phase2C][CONTROL] 템플릿 강제 제외: {'T-SYS-001', 'T-DOM-001'}
[Phase2C][CONTROL]   템플릿: T-LIM-001 - Liminal Confinement
[Phase2C][CONTROL]   신호: HIGH
[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase2C][CONTROL] 모든 시도 실패 - SKIP
[Phase2C][CONTROL] 파일 저장 안함, 루프 계속
[Phase2C][CONTROL] Registry 저장: 20260109_123456 (SKIPPED, skipped_high_dup_after_2_attempts)
```

---

## 7. What Is Explicitly NOT Implemented

| Feature | Status |
|---------|--------|
| MEDIUM blocking | NOT IMPLEMENTED |
| Vector DB | NOT IMPLEMENTED |
| Docker/K8s integration | NOT IMPLEMENTED |
| Automatic scheduling | NOT IMPLEMENTED |
| Human approval flow | NOT IMPLEMENTED |
| KU/Canonical enrichment | NOT IMPLEMENTED |

---

## 8. How to Verify

### Quick Test
```bash
# Run with dedup and check logs
python main.py --enable-dedup --max-stories 3 2>&1 | grep -E "\[Phase2C\]"

# Check registry
sqlite3 ./data/story_registry.db "SELECT id, accepted, decision_reason FROM stories ORDER BY created_at DESC LIMIT 10"
```

### Verify Schema
```bash
sqlite3 ./data/story_registry.db ".schema"
```

### Count Statistics
```bash
sqlite3 ./data/story_registry.db "SELECT accepted, COUNT(*) FROM stories GROUP BY accepted"
```

---

## 9. Research Job Skeleton

### Card Schema (`./data/research_cards.jsonl`)
```json
{
  "card_id": "STUB-20260109_123456",
  "title": "[STUB] Placeholder Research Card",
  "summary": "...",
  "tags": ["stub", "test"],
  "source": "local_stub",
  "created_at": "2026-01-09T12:34:56",
  "used_count": 0,
  "last_used_at": null
}
```

### Execution (stub only)
```bash
python main.py --run-research-stub
```

### Weekly Execution (examples, not implemented)
```bash
# cron (every Sunday 3:00 AM)
0 3 * * 0 cd /path/to/project && python main.py --run-research-stub

# systemd timer (manual setup required)
# See Phase 2D for actual implementation
```

---

**Document created:** 2026-01-09
**Author:** Claude Code (Opus 4.5)
**Scope:** HIGH-only control, SQLite persistence, research skeleton
