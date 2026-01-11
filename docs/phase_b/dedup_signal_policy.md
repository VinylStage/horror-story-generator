# Dedup Signal Policy

## Overview

Deduplication signals provide advisory information about story similarity to help users make informed decisions. Signals are **displayed only**; they never block generation.

## Signal Levels

| Signal | Similarity Score | Meaning | Suggested Action |
|--------|-----------------|---------|------------------|
| `LOW` | < 0.3 | Story appears sufficiently unique | Proceed normally |
| `MEDIUM` | 0.3 - 0.6 | Some overlap with existing stories | Review or proceed at discretion |
| `HIGH` | > 0.6 | Significant similarity detected | Consider regenerating or modifying |

## Computation Method

### Current Implementation (Phase 2C)
Similarity is computed using canonical dimension matching:

```python
def compute_similarity(new_story, existing_stories):
    """
    Compare canonical_core dimensions:
    - setting
    - primary_fear
    - antagonist
    - mechanism
    - twist

    Returns: float between 0.0 and 1.0
    """
```

### Future Enhancement (Vector Backend)
When embedding-based retrieval is implemented, similarity will use cosine distance on story embeddings.

## User Control

### CLI Flags (Planned)

```bash
# Show dedup signal before generation
python main.py --show-dedup-signal

# Skip dedup check entirely
python main.py --no-dedup

# Only show HIGH signals
python main.py --dedup-threshold high
```

### Display Format

```
[Dedup Signal: MEDIUM (0.45)]
Similar to: story_20260110_143052 (T-SYS-001)
Proceed with generation? [Y/n]
```

## Policy Decisions

### What Triggers a Signal
- Matching 3+ canonical dimensions with existing story
- Same template used within last 5 generations
- Title/opening similarity above threshold

### What Does NOT Trigger a Signal
- Different settings with same fear type
- Reuse of common horror tropes
- Similar word count or structure

## Non-Enforcement Guarantee

This system provides the following guarantees:

1. **No automatic rejection**: HIGH signal does not prevent generation
2. **No silent filtering**: All signals are displayed to user
3. **User override**: Any signal can be ignored with explicit confirmation
4. **Audit trail**: Signal history is logged but not enforced

## Integration with Story Registry

The `story_registry.py` module maintains:
- Historical canonical fingerprints
- Template usage frequency
- Similarity computation results

Dedup signals query this registry but do not modify generation behavior.
