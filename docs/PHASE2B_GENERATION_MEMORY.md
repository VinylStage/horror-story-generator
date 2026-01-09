# Phase 2B: Generation Memory (Observation Only)

**Date:** 2026-01-09
**Status:** IMPLEMENTED
**Scope:** In-process similarity observation without prevention

**References:**
- [Phase 2A: Template Activation](./PHASE2A_TEMPLATE_ACTIVATION.md)
- [Phase 2 Preparation Analysis](./PHASE2_PREPARATION_ANALYSIS.md)

---

## 1. Purpose of Generation Memory

Phase 2B introduces an **in-memory generation registry** that:

- Records metadata about each generated story
- Computes semantic similarity between stories
- Logs observations about potential duplication

**Critical constraint:** This memory is for **observation only**. It does NOT:
- Prevent generation
- Block output
- Alter prompts
- Influence template selection

---

## 2. What Is Recorded

For each generated story, the following is stored in memory:

| Field | Description |
|-------|-------------|
| `story_id` | Timestamp-based unique identifier |
| `template_id` | Template used (from Phase 2A) |
| `title` | Extracted story title |
| `semantic_summary` | 1-3 sentence LLM-generated summary |
| `canonical_keys` | Canonical dimensions (setting, primary_fear, etc.) |
| `generated_at` | ISO timestamp |

### Data Structure

```python
@dataclass
class GenerationRecord:
    story_id: str
    template_id: Optional[str]
    title: str
    semantic_summary: str
    canonical_keys: Dict[str, str]
    generated_at: str
```

---

## 3. What Is Explicitly NOT Done

| Action | Status |
|--------|--------|
| Prevent duplicate generation | **NOT IMPLEMENTED** |
| Block similar stories | **NOT IMPLEMENTED** |
| Modify template selection | **NOT IMPLEMENTED** |
| Persist memory to disk | **NOT IMPLEMENTED** |
| Use external databases | **NOT IMPLEMENTED** |
| Influence prompt construction | **NOT IMPLEMENTED** |

**Phase 2B is observation-only. Control mechanisms are Phase 2C+ concerns.**

---

## 4. How Similarity Is Observed

### 4.1 Semantic Summary Generation

After each story is generated, an LLM call creates a 1-3 sentence summary:

```python
generate_semantic_summary(story_text, title, config)
```

This summary captures:
- Setting
- Protagonist situation
- Type of horror
- Ending pattern

### 4.2 Similarity Computation

Two signals are computed:

1. **Text Similarity:** Jaccard similarity on word sets (no external deps)
2. **Canonical Key Matching:** Count of matching dimensions (setting, primary_fear, etc.)

```python
compute_text_similarity(text1, text2) -> float  # 0.0 - 1.0
```

### 4.3 Signal Levels

| Similarity | Signal |
|------------|--------|
| >= 50% | HIGH |
| >= 30% | MEDIUM |
| < 30% | LOW |

---

## 5. Log Output Format

All Phase 2B logs use the `[Phase2B][OBSERVE]` prefix:

```
[Phase2B][OBSERVE] 의미적 요약 생성 시작
[Phase2B][OBSERVE] 의미적 요약 생성 완료: 아파트에서 발생하는...
[Phase2B][OBSERVE] 유사도 관측 시작 (기존 3개 스토리와 비교)
[Phase2B][OBSERVE] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase2B][OBSERVE] 유사도 관측 결과:
[Phase2B][OBSERVE]   현재: "층간소음"
[Phase2B][OBSERVE]   가장 유사: "퇴근길의 반복" (ID: 20260109_001234)
[Phase2B][OBSERVE]   텍스트 유사도: 35.21%
[Phase2B][OBSERVE]   정규화 키 일치: 2/5
[Phase2B][OBSERVE]   신호 수준: MEDIUM
[Phase2B][OBSERVE] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase2B][OBSERVE] ⚠️ 이 관측은 생성에 영향을 주지 않습니다
[Phase2B][OBSERVE] 생성 메모리에 추가: 20260109_001500 (총 4개)
```

---

## 6. Metadata Output (Optional)

If similarity is observed, metadata MAY include:

```json
{
  "similarity_observation": {
    "closest_story_id": "20260109_001234",
    "closest_title": "퇴근길의 반복",
    "text_similarity": 0.352,
    "canonical_matches": 2,
    "signal": "MEDIUM"
  }
}
```

This field is:
- Clearly marked as observational
- Non-breaking for existing consumers
- NOT used for any control logic

---

## 7. Why This Phase Exists Before Phase 2C

From the Phase 2 Preparation Analysis:

> "The system uses a static, single prompt for all generations with zero memory of previous outputs."

Phase 2B addresses this by:

1. **Making the system aware** of what it has generated
2. **Surfacing similarity signals** that were previously invisible
3. **Providing evidence** for Phase 2C design decisions

Without Phase 2B observation data, Phase 2C would be designing prevention mechanisms blindly.

---

## 8. Memory Lifecycle

```
Process Start
    ↓
_generation_memory = []  (empty)
    ↓
Generate Story #1
    ↓
Add to memory (1 record)
    ↓
Generate Story #2
    ↓
Observe similarity vs Story #1
    ↓
Add to memory (2 records)
    ↓
...
    ↓
Process Exit
    ↓
Memory discarded (no persistence)
```

---

## 9. Verification

To verify Phase 2B is working:

```bash
# Run multiple generations and check logs
python main.py --max-stories 3 2>&1 | grep -E "\[Phase2B\]"

# Check metadata for similarity_observation field
cat generated_stories/horror_story_*_metadata.json | jq '.similarity_observation'
```

---

## 10. Limitations

| Limitation | Reason |
|------------|--------|
| No embedding-based similarity | No external dependencies allowed |
| Summary-based comparison only | Jaccard similarity is lightweight but imprecise |
| Memory limited to process lifetime | No disk persistence by design |
| Additional API call per generation | Summary generation costs ~200 tokens |

These limitations are intentional. Phase 2B is a minimal observation layer.

---

## 11. Next Phase (2C+)

Phase 2C may introduce:
- Threshold-based warnings
- Template exclusion based on similarity
- More sophisticated comparison methods

But these require Phase 2B observation data to calibrate properly.

---

**Document created:** 2026-01-09
**Author:** Claude Code (Opus 4.5)
**Scope:** Observation Only - No Control
