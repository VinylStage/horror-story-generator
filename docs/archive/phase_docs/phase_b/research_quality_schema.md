# Research Quality Schema

## Overview

Research cards may include optional quality metadata fields for future filtering, prioritization, and analytics. These fields are **advisory only** and do not affect story generation.

## Quality Fields (Optional)

### In Research Card JSON

```json
{
  "card_id": "RC-20260111-143052",
  "version": "1.0",
  "metadata": {
    "created_at": "2026-01-11T14:30:52",
    "model": "qwen3:30b",
    "status": "complete"
  },
  "output": {
    "title": "...",
    "summary": "...",
    "key_concepts": [...],
    "horror_applications": [...],
    "canonical_affinity": {...}
  },
  "validation": {
    "has_title": true,
    "has_summary": true,
    "has_concepts": true,
    "has_applications": true,
    "canonical_parsed": true,
    "quality_score": "good"
  },
  "quality": {
    "depth_rating": "medium",
    "horror_relevance": "high",
    "cultural_specificity": "korean",
    "source_reliability": "unverified",
    "manual_review": null
  }
}
```

## Field Definitions

### `quality.depth_rating`
How thoroughly the topic was researched.

| Value | Description |
|-------|-------------|
| `shallow` | Surface-level concepts only |
| `medium` | Moderate exploration with some applications |
| `deep` | Comprehensive analysis with multiple applications |

### `quality.horror_relevance`
How applicable the research is to horror storytelling.

| Value | Description |
|-------|-------------|
| `low` | Tangential connection to horror |
| `medium` | Some horror applications identified |
| `high` | Strong horror potential with clear applications |

### `quality.cultural_specificity`
Primary cultural context of the research.

| Value | Description |
|-------|-------------|
| `universal` | Culturally neutral concepts |
| `korean` | Korean cultural context |
| `asian` | Broader Asian context |
| `western` | Western cultural context |
| `mixed` | Multiple cultural contexts |

### `quality.source_reliability`
Confidence in the research accuracy.

| Value | Description |
|-------|-------------|
| `unverified` | LLM-generated, not fact-checked |
| `plausible` | Consistent with known information |
| `verified` | Cross-referenced with external sources |

### `quality.manual_review`
Human review status.

| Value | Description |
|-------|-------------|
| `null` | Not reviewed |
| `approved` | Human approved for use |
| `flagged` | Human flagged for issues |
| `rejected` | Human rejected |

## Validation Quality Score

The `validation.quality_score` field is automatically computed:

```python
# From validator.py
if all_fields_present:
    quality_score = "good"
elif most_fields_present:
    quality_score = "partial"
else:
    quality_score = "incomplete"

# If JSON parsing failed:
quality_score = "parse_failed"
```

## Usage Guidelines

### For Filtering (Future)
```python
# Example: Find high-relevance Korean research
cards = filter(
    lambda c: c.quality.horror_relevance == "high"
              and c.quality.cultural_specificity == "korean",
    all_cards
)
```

### For Prioritization (Future)
```python
# Example: Prefer verified, deep research
priority = (
    depth_weights[card.quality.depth_rating] +
    reliability_weights[card.quality.source_reliability]
)
```

## Non-Enforcement Policy

Quality fields are used for:
- Display and user information
- Optional filtering in list commands
- Analytics and reporting

Quality fields are NOT used for:
- Automatic story generation decisions
- Blocking or rejecting generation requests
- Mandatory quality gates

## Default Values

When quality fields are not explicitly set:

```json
{
  "quality": {
    "depth_rating": "medium",
    "horror_relevance": "medium",
    "cultural_specificity": "universal",
    "source_reliability": "unverified",
    "manual_review": null
  }
}
```
