# Decision Log - Horror Story Generator

## Purpose
This document records all major design decisions, their rationale, and deferral status.

---

## ✅ Finalized Decisions (Phase 1)

### D-001: Primary Goal
**Decision:** Proof-of-concept with high-quality manual/assisted generation
**Date:** 2026-01-08
**Rationale:**
- Focus on validating knowledge base quality over automation scale
- Allows iterative template refinement through real usage
- Demonstrates system capability without Rule Engine complexity

**Alternatives Rejected:**
- A. Automated story generation at scale → Deferred to Phase 3
- D. Multimodal content pipeline → Out of scope for v1

**Status:** FROZEN

---

### D-002: KU Selection Strategy
**Decision:** Hybrid (category match + canonical conflict check)
**Date:** 2026-01-08
**Rationale:**
- Category matching ensures KU type fits template requirements
- Canonical checking prevents conceptual mismatches
- Balances strictness with flexibility
- Example: KU-005 (han) shouldn't be used in T-DIG-001 (digital impersonation) despite both being social_fear

**Alternatives Rejected:**
- A. Strict canonical matching → Too rigid, limits KU pool
- C. Semantic similarity embeddings → Overkill for 52 KUs

**Implementation Details:**
```
Selection Algorithm (Phase 2):
1. Filter KUs by required_ku_categories
2. Check KU canonical_key compatibility with template canonical_core
3. Check KU avoid rules don't conflict
4. Present compatible KUs to user
```

**Status:** FROZEN

---

### D-003: Automation Level
**Decision:** Assisted manual only
**Date:** 2026-01-08
**Rationale:**
- Validates system design through human-in-loop usage
- Avoids premature automation before validation
- Enables quality control at each step
- User selects template → System suggests KUs → User approves → System generates

**Alternatives Rejected:**
- A. Fully automated → Phase 3 goal after validation
- D. Manual with validation → Too passive

**Workflow:**
1. User browses templates or provides keywords
2. System suggests compatible templates (Phase 2)
3. User selects template
4. System filters compatible KUs
5. User selects 2-5 KUs
6. System compiles prompt (Phase 2)
7. System generates story
8. User reviews/edits

**Status:** FROZEN

---

### D-004: Writing Technique Application
**Decision:** Optional, DISABLED by default
**Date:** 2026-01-08
**Rationale:**
- Writing technique KUs (KU-030 to KU-036, KU-051) are meta-instructions
- Should not alter canonical identity of generated story
- User can manually enable if desired
- Prevents technique KUs from polluting KU selection

**Alternatives Rejected:**
- A. Apply universally → Forces uniform style
- C. Template specifies → Reduces template reusability

**Implementation:**
- Writing technique KUs excluded from automatic selection
- Separate toggle in prompt compiler (Phase 2)
- If enabled, apply as post-processing instructions

**Status:** FROZEN

---

### D-005: Cultural Specificity Scope
**Decision:** Flexible (allow culturally-specific KUs in abstract templates with awareness)
**Date:** 2026-01-08
**Rationale:**
- Some KUs are region-locked (Korea: 7 KUs, US: 11 KUs)
- Abstract templates should be able to use regional KUs for specificity
- System warns user about cultural context requirements
- Example: T-SYS-001 (abstract systemic erosion) can use KU-005 (han) if user wants Korean context

**Alternatives Rejected:**
- A. Culture-agnostic only → Loses valuable regional horror insights
- B. Strict enforcement → Too rigid

**Implementation (Phase 2):**
- KU selector shows region tag
- Warns if mixing incompatible regions (e.g., Korean + US-specific)
- User can override with awareness

**Status:** FROZEN

---

### D-006: Canonical Enum Stability
**Decision:** Enum v1.0 is stable but extensible (no semantic changes to existing values)
**Date:** 2026-01-08
**Rationale:**
- Adding new values is allowed (e.g., new setting_archetype)
- Changing meaning of existing values breaks existing templates
- Removal requires deprecation path

**Rules:**
- ✅ Can add: new setting, fear, antagonist, mechanism, twist
- ❌ Cannot change: meaning of existing values
- ❌ Cannot remove: values used by existing templates
- ⚠️ Deprecation: requires migration plan

**Example:**
```
✅ Allowed: Add "virtual_reality" to setting_archetype
❌ Forbidden: Change "system" antagonist to mean "weather system"
```

**Status:** FROZEN

---

### D-007: Template Canonical Uniqueness
**Decision:** No two templates can share the same canonical_core
**Date:** 2026-01-08
**Rationale:**
- Canonical_core defines template identity
- Duplicates defeat purpose of canonical abstraction
- Variations belong in variation_axes, not new templates

**Verification:**
- All 15 v1 templates have unique canonical_core ✅
- Future templates must be checked against existing set

**Status:** FROZEN

---

## ⏸️ Deferred Decisions (Phase 2+)

### D-101: KU Count Per Template
**Question:** How many KUs should be selected per template?
**Status:** DEFERRED to Phase 2 (assisted workflow testing)
**Current Assumption:** 2-5 KUs recommended, user decides
**Revisit When:** After 10+ manual generations to see optimal range

---

### D-102: Variation Engine Design
**Question:** Should variation_axes be parametric or stochastic?
**Status:** DEFERRED to Phase 2
**Options:**
- Parametric: User sets "erosion_rate: slow/medium/fast"
- Stochastic: System randomly varies within axes
**Revisit When:** Prompt compiler is implemented

---

### D-103: Prompt Compilation Strategy
**Question:** How to structure LLM prompts from template + KUs?
**Status:** DEFERRED to Phase 2
**Open Questions:**
- Should act_1/act_2/act_3 be explicit sections or implicit guidance?
- How to integrate KU usage_rules and avoid constraints?
- Should prompt include negative examples?
**Revisit When:** Starting prompt compiler implementation

---

### D-104: Output Validation Strictness
**Question:** How strict should canonical constraint checking be?
**Status:** DEFERRED to Phase 2
**Options:**
- Strict: Flag any deviation from canonical_core
- Lenient: Only flag major violations (e.g., wrong primary_fear)
**Revisit When:** After generating 20+ stories manually

---

## 🚫 Explicitly Rejected

### R-001: Full Automation (Phase 1)
**Rejected:** 2026-01-08
**Reason:** Premature without validation
**May Reconsider:** Phase 3 after assisted workflow proves effective

---

### R-002: Embedding-Based KU Selection
**Rejected:** 2026-01-08
**Reason:** Overkill for 52 KUs, adds complexity without clear benefit
**May Reconsider:** If KU count exceeds 200+

---

### R-003: Template Auto-Generation
**Rejected:** 2026-01-08
**Reason:** Templates are design artifacts, not mechanical outputs
**May Reconsider:** Never (this is a human design task)

---

## 📋 Decision Review Schedule

- **Phase 2 Start:** Review all deferred decisions
- **After 50 stories:** Evaluate D-101, D-104
- **After prompt compiler:** Evaluate D-102, D-103
- **Quarterly:** Review frozen decisions for necessary updates

---

## Change Log

| Date | Decision | Change | Reason |
|------|----------|--------|--------|
| 2026-01-08 | D-001 to D-007 | Initial freeze | Phase 1 completion |

---

## References

- Canonical Enum: `docs/canonical_enum.md`
- System Architecture: `docs/system_architecture.md`
- Templates: `phase1_foundation/03_templates/template_skeletons_v1.json`
