# Canonical Key Application Scope

> **Version:** v1.4.2 <!-- x-release-please-version -->

**Date:** 2026-01-12
**Status:** ACTIVE
**Canonical Enum Version:** v1.0 (FROZEN)

---

## Overview

This document defines the **official application scope** of Canonical Key within the Horror Story Generator system. It specifies where Canonical Key is:
- **Generated** (required)
- **Stored** (required)
- **Consumed** (optional, current phase)
- **Not applied** (intentionally deferred)

---

## Definitions

| Term | Description |
|------|-------------|
| `canonical_core` | Fixed identity values for story templates (5 dimensions) |
| `canonical_affinity` | Research card output indicating which canonical dimensions apply |
| Canonical Key | General term for canonical dimension values |

---

## Current Application Scope

### 1. Canonical Key Generation (REQUIRED)

**Location:** Research Card Generation

| Component | File | Description |
|-----------|------|-------------|
| Prompt Template | `src/research/executor/prompt_template.py` | Requests `canonical_affinity` from LLM |
| Validator | `src/research/executor/validator.py` | Validates and parses `canonical_affinity` |
| Output Writer | `src/research/executor/output_writer.py` | Writes `canonical_affinity` to research card JSON |

**Rule:** All research cards MUST include `canonical_affinity` with at least one dimension populated.

**Output Format:**
```json
{
  "output": {
    "canonical_affinity": {
      "setting": ["apartment", "urban"],
      "primary_fear": ["isolation"],
      "antagonist": ["system"],
      "mechanism": ["surveillance"]
    }
  }
}
```

---

### 2. Canonical Key Storage (REQUIRED)

| Storage Type | Location | Content |
|--------------|----------|---------|
| Research Cards | `data/research/YYYY/MM/*.json` | `canonical_affinity` (generated) |
| Story Templates | `assets/templates/template_skeletons_v1.json` | `canonical_core` (predefined) |
| In-Memory (transient) | `src/dedup/similarity.py` | `canonical_keys` for similarity observation |

---

### 3. Canonical Key Consumption (OPTIONAL - Current Phase)

**Location:** Story Generation Pipeline

| Component | File | Usage |
|-----------|------|-------|
| Generator | `src/story/generator.py` | Uses template's `canonical_core` for dedup |
| Prompt Builder | `src/story/prompt_builder.py` | Includes `canonical_core` in prompt context |
| Dedup API | `src/api/services/dedup_service.py` | Compares `canonical_core` for similarity |
| Job Dedup | `src/api/routers/jobs.py` | Extracts `canonical_affinity` from research cards |
| **Canonical Extractor** | `src/story/canonical_extractor.py` | Extracts story's own CK for alignment scoring |

**Rule:** Story generation MAY consume Canonical Keys from:
- Template `canonical_core` (for dedup comparison)
- Research card `canonical_affinity` (via integration)
- Generated story text `canonical_affinity` (via LLM extraction)

**Note:** Consumption is NOT enforced. Stories can be generated without Canonical Key validation.

---

### 4. Story Canonical Key Extraction (IMPLEMENTED)

**Location:** Story Generation Pipeline (Post-generation)

| Component | File | Description |
|-----------|------|-------------|
| Canonical Extractor | `src/story/canonical_extractor.py` | LLM-based extraction of CK from story text |
| Generator Integration | `src/story/generator.py` | Calls extractor after story generation |

**How It Works:**
1. After story text is generated, the extractor analyzes the content
2. LLM identifies the 5 canonical dimensions from actual story text
3. Multi-value `canonical_affinity` is collapsed to single-value `canonical_core`
4. Story's CK is compared with template's CK for alignment scoring

**Output Format (in story metadata):**
```json
{
  "story_canonical_extraction": {
    "canonical_core": {
      "setting_archetype": "apartment",
      "primary_fear": "social_displacement",
      "antagonist_archetype": "system",
      "threat_mechanism": "surveillance",
      "twist_family": "inevitability"
    },
    "canonical_affinity": {
      "setting": ["apartment", "domestic_space"],
      "primary_fear": ["social_displacement", "isolation"],
      "antagonist": ["system", "collective"],
      "mechanism": ["surveillance"],
      "twist": ["inevitability"]
    },
    "template_comparison": {
      "match_score": 0.8,
      "match_count": 4,
      "total_dimensions": 5,
      "matches": ["setting_archetype", "primary_fear", "antagonist_archetype", "threat_mechanism"],
      "divergences": [{"dimension": "twist_family", "template": "revelation", "story": "inevitability"}]
    }
  }
}
```

**Configuration:**
- `ENABLE_STORY_CK_EXTRACTION`: Enable/disable extraction (default: `true`)
- `STORY_CK_MODEL`: Override model for extraction (default: same as story generation)

---

### 5. Story Canonical Key Enforcement (IMPLEMENTED)

**Location:** Story Generation Pipeline (Post-extraction)

| Component | File | Description |
|-----------|------|-------------|
| Enforcement Check | `src/story/canonical_extractor.py` | Validates alignment against threshold |
| Generator Integration | `src/story/generator.py` | Applies enforcement policy (retry/reject) |

**How It Works:**
1. After CK extraction and comparison, alignment score is checked against threshold
2. Enforcement policy determines action: accept, warn, retry, or reject
3. Retry policy causes re-generation with new template selection
4. Strict policy rejects stories that fail to meet alignment threshold

**Enforcement Policies:**

| Policy | Behavior |
|--------|----------|
| `none` | Disabled - always accept |
| `warn` | Log warning if below threshold (default) |
| `retry` | Re-attempt generation with different template |
| `strict` | Reject story if below threshold |

**Configuration:**
- `STORY_CK_ENFORCEMENT`: Policy level (default: `warn`)
- `STORY_CK_MIN_ALIGNMENT`: Minimum alignment score 0.0-1.0 (default: `0.6`)

**Output Format (in story metadata):**
```json
{
  "story_canonical_extraction": {
    "enforcement": {
      "passed": true,
      "action": "accept",
      "reason": "Alignment 80% meets threshold 60%",
      "match_score": 0.8,
      "threshold": 0.6,
      "policy": "warn"
    }
  }
}
```

---

### 6. Intentionally NOT Applied (Deferred)

The following are **explicitly deferred** to future phases:

| Feature | Status | Rationale |
|---------|--------|-----------|
| Cross-pipeline Canonical Key matching | DEFERRED | No automatic matching between research affinity and template core (Issue #21) |

---

## Decision Summary

| Scope | Status | Enforcement |
|-------|--------|-------------|
| Research card generation | REQUIRED | canonical_affinity must be present |
| Research card storage | REQUIRED | canonical_affinity persisted in JSON |
| Story template definition | PREDEFINED | canonical_core is fixed per template |
| Story dedup comparison | OPTIONAL | Used if available, not required |
| Story output extraction | IMPLEMENTED | Stories extract own CK for alignment scoring |
| Story output enforcement | IMPLEMENTED | Configurable policy (none/warn/retry/strict) |

---

## References

- Canonical Enum v1.0: `docs/technical/canonical_enum.md`
- Template Skeletons: `assets/templates/template_skeletons_v1.json`
- Research Executor: `src/research/executor/`
- **Story Canonical Extractor: `src/story/canonical_extractor.py`**
- Dedup System: `docs/core/ARCHITECTURE.md`

---

## Change Policy

- Canonical Enum v1.0 is **FROZEN** (value additions only, no semantic changes)
- Application scope changes require documentation update
- Runtime behavior changes require separate implementation ticket
