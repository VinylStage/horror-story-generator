# System Architecture - Phase 1 Foundation

## Overview

The horror story generator follows a **four-layer pipeline** from research to templates:

```
Layer 1: Raw Research
    ↓
Layer 2: Knowledge Normalization
    ↓
Layer 3: Canonical Abstraction
    ↓
Layer 4: Template Design
    ↓
[Phase 2: Execution Layer - NOT IMPLEMENTED]
```

---

## Layer 1: Raw Research

**Location:** `phase1_foundation/00_raw_research/`

**Assets:**
- `report.md` - Consolidated research report (Korean)
- `results.json` - 15 structured research items from NotebookLM

**Purpose:**
- Academic grounding for horror mechanics
- Source material for knowledge extraction
- Covers: horror theory, K-horror, systemic horror, writing techniques

**Status:** ✅ Immutable

---

## Layer 2: Knowledge Normalization

**Location:** `phase1_foundation/01_knowledge_units/`

**Assets:**
- `knowledge_units.json` - 52 atomic Knowledge Units

**Schema:**
```json
{
  "ku_id": "KU-XXX",
  "type": "horror_concept | horror_theme | social_fear | writing_technique",
  "region": "Global | Korea | US | etc",
  "genre": [...],
  "primary_fear": "...",
  "secondary_fears": [...],
  "setting_archetype": "...",
  "antagonist_archetype": "...",
  "core_idea": "...",
  "usage_rules": [...],
  "avoid": [...],
  "template_affinity": [...],
  "sources": [...],
  "tags": [...]
}
```

**Breakdown:**
- 14 horror_concept (theoretical foundations)
- 15 horror_theme (specific motifs/scenarios)
- 17 social_fear (real-world systemic threats)
- 6 writing_technique (craft techniques)

**Purpose:**
- Atomic, reusable horror knowledge
- Strict source grounding (no invention)
- Usage rules + avoid constraints
- Template compatibility hints

**Status:** ✅ Immutable

---

## Layer 3: Canonical Abstraction

**Location:** `phase1_foundation/02_canonical_abstraction/`

**Assets:**
1. `canonical_enum.md` - Definitions of 5 canonical dimensions
2. `ku_canonical_features.json` - Feature extraction (52 KUs)
3. `resolved_canonical_keys.json` - Final canonical keys (45 KUs)

**Canonical Dimensions:**
```
1. setting_archetype: Where horror occurs
   - apartment, hospital, rural, domestic_space, digital, liminal,
     infrastructure, body, abstract

2. primary_fear: Core psychological fear
   - loss_of_autonomy, identity_erasure, social_displacement,
     contamination, isolation, annihilation

3. antagonist_archetype: Source of threat
   - ghost, system, technology, body, collective, unknown

4. threat_mechanism: How horror operates
   - surveillance, possession, debt, infection, impersonation,
     confinement, erosion, exploitation

5. twist_family: Narrative resolution pattern
   - revelation, inevitability, inversion, circularity,
     self_is_monster, ambiguity
```

**Purpose:**
- Structural abstraction of horror mechanics
- Template identity definition
- Duplicate template prevention
- KU-Template compatibility matching

**Key Output:**
- 45 KUs resolved to canonical keys
- 7 writing technique KUs excluded from resolution
- Distribution analysis (system antagonist 49%, social_displacement fear 24%, erosion mechanism 31%)

**Status:** ✅ Immutable

---

## Layer 4: Template Design

**Location:** `phase1_foundation/03_templates/`

**Assets:**
- `template_skeletons_v1.json` - 15 unique templates

**Schema:**
```json
{
  "template_id": "T-XXX-###",
  "template_name": "...",
  "canonical_core": {
    "setting": "...",
    "primary_fear": "...",
    "antagonist": "...",
    "mechanism": "...",
    "twist": "..."
  },
  "required_ku_categories": [...],
  "story_skeleton": {
    "act_1": "...",
    "act_2": "...",
    "act_3": "..."
  },
  "variation_axes": [...]
}
```

**Template Coverage:**
- Systemic horror (6 templates)
- Domestic horror (3 templates)
- Medical horror (2 templates)
- Digital horror (2 templates)
- Body/liminal/rural/infrastructure (1 each)

**Canonical Uniqueness:**
- All 15 templates have distinct canonical_core combinations
- No duplicates or semantic overlap

**Purpose:**
- Reusable story structure skeletons
- Canonical pattern instantiation
- KU requirement specification
- Variation guidance

**Status:** ✅ Immutable

---

## Phase 2: Execution Layer (NOT IMPLEMENTED)

**Planned Components:**

### Rule Engine
- Input: User keywords/preferences
- Output: Selected template + compatible KUs
- Method: Hybrid matching (category + canonical check)

### Prompt Compiler
- Input: Template + selected KUs
- Output: LLM prompt
- Method: Structured prompt assembly with constraints

### Variation Engine
- Input: Template variation_axes
- Output: Parameter variations
- Method: To be determined

### Output Validator
- Input: Generated story
- Output: Validation report
- Method: Canonical constraint checking

**Status:** ❌ Not started (Phase 2 deferred)

---

## Data Flow (Current State)

```
[Research Items]
       ↓
  (manual extraction)
       ↓
[Knowledge Units] ← normalization rules
       ↓
  (feature inference)
       ↓
[Canonical Features] ← canonical enum
       ↓
  (resolution)
       ↓
[Canonical Keys] ← template design
       ↓
[Templates]
       ↓
  ⚠️ MANUAL GAP ⚠️
       ↓
[Story Generation] ← existing generator (not integrated)
```

---

## Key Architectural Principles

1. **Separation of Concerns:**
   - Knowledge (facts) ≠ Structure (templates) ≠ Execution (prompts)

2. **Immutability:**
   - Phase 1 assets are frozen
   - Changes require new version (e.g., v2)

3. **Canonical Identity:**
   - Every template has unique canonical_core
   - Prevents duplicate patterns

4. **Source Grounding:**
   - No invented facts
   - All KUs cite sources

5. **Constraint Propagation:**
   - KU usage_rules + avoid constraints
   - Template required_ku_categories
   - Canonical compatibility checking

---

## Technical Debt & Known Gaps

### Resolved:
- ✅ KU normalization complete
- ✅ Canonical dimensions finalized
- ✅ Template uniqueness verified

### Deferred to Phase 2:
- ❌ Automated KU selection
- ❌ Prompt compilation strategy
- ❌ Variation parameter system
- ❌ Output validation

### Open Questions (Phase 2):
- How many KUs per template? (currently unspecified)
- Should writing technique KUs be automatically applied?
- What prompt format maximizes canonical adherence?

---

## References

- Canonical Enum: `docs/canonical_enum.md`
- Decision Log: `docs/decision_log.md`
- Knowledge Units: `phase1_foundation/01_knowledge_units/knowledge_units.json`
- Templates: `phase1_foundation/03_templates/template_skeletons_v1.json`
