# Phase 2C: Research Job Skeleton

**Date:** 2026-01-09
**Status:** SKELETON ONLY (No web requests)
**Scope:** Design + storage format + CLI stub

---

## 1. Purpose

The research job is designed to periodically gather new horror-related concepts, tropes, and ideas from external sources to enrich story generation.

**Phase 2C provides only the skeleton:**
- Storage format definition
- CLI stub for testing
- Execution plan examples

**Actual web requests are NOT implemented in Phase 2C.**

---

## 2. Research Card Schema

### JSON Format
```json
{
  "card_id": "string",       // Unique identifier (e.g., "STUB-20260109_123456")
  "title": "string",         // Card title
  "summary": "string",       // Brief summary of the concept
  "tags": ["string"],        // Classification tags
  "source": "string",        // Source identifier (e.g., "web_article", "local_stub")
  "created_at": "ISO8601",   // Creation timestamp
  "used_count": 0,           // Number of times used in generation
  "last_used_at": null       // Last usage timestamp (nullable)
}
```

### Storage Location
```
./data/research_cards.jsonl
```

Uses JSONL format (one JSON object per line) for append-friendly operations.

---

## 3. CLI Stub

### Command
```bash
python main.py --run-research-stub
```

### Behavior
1. Creates `./data/` directory if missing
2. Appends a placeholder card to `research_cards.jsonl`
3. Logs the card ID and file path
4. Exits immediately (no story generation)

### Example Output
```
[Phase2C] 연구 카드 스텁 생성 완료: STUB-20260109_123456
[Phase2C] 저장 위치: ./data/research_cards.jsonl
```

---

## 4. Weekly Execution Plan

### Cron Example
```bash
# Run every Sunday at 3:00 AM
0 3 * * 0 cd /path/to/horror-story-generator && python main.py --run-research-stub
```

### Systemd Timer Example (reference only)

**`/etc/systemd/system/horror-research.timer`**
```ini
[Unit]
Description=Weekly Horror Research Job

[Timer]
OnCalendar=Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**`/etc/systemd/system/horror-research.service`**
```ini
[Unit]
Description=Horror Research Job

[Service]
Type=oneshot
WorkingDirectory=/path/to/horror-story-generator
ExecStart=/usr/bin/python3 main.py --run-research-stub
User=youruser
```

**Note:** These are examples only. Actual unit files are NOT created in Phase 2C.

---

## 5. Future Integration (Phase 2D+)

When the research job is fully implemented, it will:

1. **Fetch** horror-related content from configured sources
2. **Parse** and extract relevant concepts
3. **Generate** semantic summaries
4. **Store** as research cards
5. **Integrate** with prompt construction (inject cards into prompts)

### Potential Sources
- Horror literature databases
- Film review aggregators
- Academic papers on horror psychology
- Community forums (curated)

### Integration with Generation
Research cards may be selected and injected into prompts to provide:
- New horror concepts not in the base templates
- Contemporary references
- Cross-cultural horror elements

---

## 6. Limitations (Phase 2C)

| Feature | Status |
|---------|--------|
| Actual web requests | NOT IMPLEMENTED |
| Source configuration | NOT IMPLEMENTED |
| Automatic scheduling | NOT IMPLEMENTED (examples only) |
| Card-to-prompt integration | NOT IMPLEMENTED |

---

**Document created:** 2026-01-09
**Author:** Claude Code (Opus 4.5)
**Scope:** Skeleton design only
