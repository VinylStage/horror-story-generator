# Canonical Key Application Scope

> **Version:** v1.9.0 <!-- x-release-please-version -->

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

**Rule:** Story generation MAY consume Canonical Keys from:
- Template `canonical_core` (for dedup comparison)
- Research card `canonical_affinity` (via integration)

**Note:** Consumption is NOT enforced. Stories can be generated without Canonical Key validation.

---

### 4. Intentionally NOT Applied (Deferred)

The following are **explicitly deferred** to future phases:

| Feature | Status | Rationale |
|---------|--------|-----------|
| Story output Canonical Key generation | DEFERRED | Stories do not generate their own Canonical Key |
| Canonical Key enforcement on story output | DEFERRED | No validation that story content matches template's canonical_core |
| Cross-pipeline Canonical Key matching | DEFERRED | No automatic matching between research affinity and template core |

---

## Decision Summary

| Scope | Status | Enforcement |
|-------|--------|-------------|
| Research card generation | REQUIRED | canonical_affinity must be present |
| Research card storage | REQUIRED | canonical_affinity persisted in JSON |
| Story template definition | PREDEFINED | canonical_core is fixed per template |
| Story dedup comparison | OPTIONAL | Used if available, not required |
| Story output generation | NOT APPLIED | Stories do not output Canonical Keys |

---

## References

- Canonical Enum v1.0: `docs/technical/canonical_enum.md`
- Template Skeletons: `assets/templates/template_skeletons_v1.json`
- Research Executor: `src/research/executor/`
- Dedup System: `docs/core/ARCHITECTURE.md`

---

## Change Policy

- Canonical Enum v1.0 is **FROZEN** (value additions only, no semantic changes)
- Application scope changes require documentation update
- Runtime behavior changes require separate implementation ticket
