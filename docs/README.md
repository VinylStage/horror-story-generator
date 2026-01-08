# Horror Story Generator - Phase 1 Foundation

## Project Purpose

A research-grounded horror content generation system that:
- Transforms academic horror research into reusable knowledge units
- Abstracts horror mechanics into canonical dimensions
- Provides template skeletons for assisted story generation

## Current Phase: Phase 1 Complete (Foundation Assets)

**Status:** ✅ Research, normalization, abstraction, and templates complete
**Mode:** Manual/assisted generation only
**Automation:** NOT IMPLEMENTED (Phase 2)

---

## What IS Implemented

### ✅ Phase 1: Research & Normalization
- 15 academic/sociological horror research items
- Consolidated research report (Korean)
- Structured JSON export

### ✅ Phase 2: Knowledge Unit Extraction
- 52 atomic Knowledge Units (KUs)
- Categorized as: horror_concept, horror_theme, social_fear, writing_technique
- Each KU includes:
  - Core idea
  - Usage rules
  - Avoid constraints
  - Sources and tags

### ✅ Phase 3: Canonical Abstraction
- 5 canonical dimensions defined:
  - setting_archetype
  - primary_fear
  - antagonist_archetype
  - threat_mechanism
  - twist_family
- 45 KUs resolved to canonical keys
- 7 writing technique KUs separated

### ✅ Phase 4: Template Design
- 15 template skeletons created
- Each template has unique canonical_core
- Required KU categories specified
- Story skeleton (3-act structure)
- Variation axes defined

---

## What IS NOT Implemented

### ❌ Phase 2 (Deferred):
- Rule Engine (template + KU selection)
- Prompt Compiler (template → LLM prompt)
- Variation Engine
- Output Validator
- Batch generation

---

## Project Structure

```
phase1_foundation/          # IMMUTABLE - DO NOT MODIFY
├── 00_raw_research/        # Original research data
├── 01_knowledge_units/     # Normalized KUs
├── 02_canonical_abstraction/  # Canonical keys & enums
└── 03_templates/           # Template skeletons

phase2_execution/           # FUTURE - Not yet implemented
├── rule_engine/
├── prompt_compiler/
└── validators/
```

---

## Usage (Manual Mode)

**Current workflow:**
1. Browse `phase1_foundation/03_templates/` - select template
2. Browse `phase1_foundation/01_knowledge_units/` - select 2-5 compatible KUs
3. Manually combine template skeleton + KU content
4. Use existing generator or write custom prompt
5. Generate story

**Compatibility check:**
- Match KU `type` to template `required_ku_categories`
- Verify KU canonical_key aligns with template canonical_core
- Check KU `avoid` rules don't conflict

---

## Key Decisions (Finalized)

- **Primary Goal:** Proof-of-concept with high-quality assisted generation
- **KU Selection:** Hybrid (category match + canonical conflict check)
- **Automation Level:** Assisted manual only
- **Writing Techniques:** Optional, DISABLED by default
- **Cultural Scope:** Flexible (culturally-specific KUs allowed in abstract templates)

See `docs/decision_log.md` for full rationale.

---

## Next Steps (Phase 2 - Not Started)

1. Implement assisted KU selector (suggests compatible KUs)
2. Build prompt compiler (template + KUs → LLM prompt)
3. Create output validator
4. Develop variation engine

**Do NOT proceed** without reviewing `docs/decision_log.md`.

---

## Data Assets

- **Knowledge Units:** 52 total (45 content + 7 technique)
- **Templates:** 15 unique canonical patterns
- **Canonical Dimensions:** 5 (setting, fear, antagonist, mechanism, twist)
- **Research Sources:** 15 items

---

## License & Attribution

[To be determined]

Research sources cited in individual KUs.
