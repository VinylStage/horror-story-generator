# KU Selector v0 - Specification Document

**Version:** 0.1
**Status:** Design Specification
**Phase:** 2-A (Assisted Manual)
**Date:** 2026-01-08

---

## 1. Purpose

The KU Selector is a **rule-based filtering system** that assists users in selecting compatible Knowledge Units (KUs) for a given template during manual story generation.

**Goals:**
- Prevent conceptually incompatible KU-template combinations
- Surface canonical mismatches before generation
- Provide clear explanations for rejections
- Enable informed user overrides where appropriate

**Non-Goals (Phase 2-A):**
- Automatic KU selection
- Optimization for "best" KUs
- Machine learning or embeddings
- Batch processing

---

## 2. System Inputs

### 2.1 Required Input

**`template_id`** (string)
- Format: `T-XXX-###` (e.g., `T-DIG-001`)
- Must exist in `phase1_foundation/03_templates/template_skeletons_v1.json`
- System loads:
  - `canonical_core` (5 dimensions)
  - `required_ku_categories` (array of KU type strings)
  - `template_name` (for display)

### 2.2 Optional User Constraints

**`region_preference`** (string, optional)
- Values: `"Global"`, `"Korea"`, `"US"`, or any region from KU dataset
- Default: `null` (no preference)
- Effect: Issues warnings for mismatched regions, does not block

**`exclude_tags`** (array of strings, optional)
- Values: Any tags present in KU dataset
- Default: `[]`
- Effect: Hard blocks KUs with matching tags
- Example: `["Explicit Violence", "Sexual Content"]`

**`exclude_ku_ids`** (array of strings, optional)
- Values: KU IDs (e.g., `["KU-030", "KU-031"]`)
- Default: All writing_technique KUs (`["KU-030", "KU-031", "KU-032", "KU-033", "KU-034", "KU-035", "KU-036", "KU-051"]`)
- Effect: Hard blocks specified KUs
- Note: Writing technique KUs excluded by default per D-004

---

## 3. System Outputs

### 3.1 Compatible KUs

**Structure:**
```json
{
  "ku_id": "KU-XXX",
  "ku_name": "...",
  "compatibility_score": "perfect" | "good" | "acceptable",
  "warnings": [
    {
      "type": "region_mismatch" | "canonical_partial" | "setting_abstract",
      "message": "..."
    }
  ],
  "match_details": {
    "category_match": true,
    "canonical_matches": 5,
    "canonical_mismatches": 0
  }
}
```

**Compatibility Score Definitions:**
- **perfect**: All 5 canonical dimensions match + category match + no warnings
- **good**: 4/5 canonical dimensions match + category match + minor warnings only
- **acceptable**: 3/5 canonical dimensions match + category match + warnings present

### 3.2 Incompatible KUs

**Structure:**
```json
{
  "ku_id": "KU-XXX",
  "ku_name": "...",
  "rejection_reason": "hard_block" | "conflict" | "category_mismatch",
  "details": [
    "Category mismatch: template requires [social_fear], KU is [writing_technique]",
    "Canonical conflict: template primary_fear is identity_erasure, KU is social_displacement"
  ]
}
```

**Rejection Reason Types:**
- **hard_block**: User constraint violation (excluded tag/ID, writing technique)
- **conflict**: KU `avoid` rules violated by template characteristics
- **category_mismatch**: KU type not in `required_ku_categories`

---

## 4. Selection Algorithm

### Step 1: Initial Filtering by Category

**Rule:**
```
IF KU.type NOT IN template.required_ku_categories:
    REJECT with reason "category_mismatch"
```

**Implementation:**
1. Load all 52 KUs from `phase1_foundation/01_knowledge_units/knowledge_units.json`
2. For each KU:
   - Check if `KU.type` exists in `template.required_ku_categories`
   - If NO: Add to `incompatible_kus` with rejection_reason = `"category_mismatch"`
   - If YES: Proceed to Step 2

**Example:**
- Template `T-DIG-001` requires: `["social_fear", "horror_theme"]`
- KU-001 type: `horror_concept` → **REJECT** (category_mismatch)
- KU-018 type: `social_fear` → **PASS** to Step 2

---

### Step 2: Canonical Compatibility Check

**Rule:**
Load KU canonical_key from `phase1_foundation/02_canonical_abstraction/resolved_canonical_keys.json`

**Matching Logic:**

For each of 5 canonical dimensions, compare:
- `template.canonical_core[dimension]` vs `KU.canonical_key[dimension]`

**Compatibility Matrix:**

| Dimension | Exact Match | Compatible Mismatch | Incompatible Mismatch |
|-----------|-------------|---------------------|----------------------|
| **setting_archetype** | Same value | `template=abstract` OR `KU=abstract` | Different concrete values |
| **primary_fear** | Same value | N/A | Any mismatch |
| **antagonist_archetype** | Same value | `template=unknown` OR `KU=unknown` | Different concrete values |
| **threat_mechanism** | Same value | Any mismatch (warning only) | N/A |
| **twist_family** | Same value | Any mismatch (warning only) | N/A |

**Scoring:**
- Exact match: +1 point
- Compatible mismatch: +0.5 points
- Incompatible mismatch: +0 points
- **Minimum threshold: 3.0 points (out of 5) to proceed**

**Hard Block Conditions:**
1. **Primary Fear Mismatch**: If `template.canonical_core.primary_fear ≠ KU.canonical_key.primary_fear`
   - REJECT with reason: `"canonical_conflict"`
   - Explanation: "Primary fear is the core identity of horror; mismatch creates thematic incoherence"

2. **Setting Incompatibility**: If both setting values are concrete (not `abstract`) AND different
   - REJECT with reason: `"canonical_conflict"`
   - Explanation: "Cannot place digital horror in rural setting without abstract mediation"

3. **Antagonist Incompatibility**: If both antagonist values are concrete (not `unknown`) AND fundamentally incompatible
   - Incompatible pairs:
     - `ghost` ↔ `technology`
     - `ghost` ↔ `system`
     - `body` ↔ `collective`
   - REJECT with reason: `"canonical_conflict"`
   - Explanation: "Antagonist types have mutually exclusive mechanics"

**Warning Conditions:**
1. **Mechanism Mismatch**: If `threat_mechanism` differs, add warning
   - Warning type: `"canonical_partial"`
   - Message: "Template uses {template_mechanism}, KU uses {ku_mechanism}. Verify compatibility."

2. **Twist Mismatch**: If `twist_family` differs, add warning
   - Warning type: `"canonical_partial"`
   - Message: "Template expects {template_twist}, KU suggests {ku_twist}. May create tonal conflict."

**Implementation:**
```
score = 0
warnings = []

FOR each dimension in [setting, primary_fear, antagonist, mechanism, twist]:
    IF template[dimension] == KU[dimension]:
        score += 1
    ELSE IF dimension == "setting":
        IF template[dimension] == "abstract" OR KU[dimension] == "abstract":
            score += 0.5
        ELSE IF incompatible_settings(template[dimension], KU[dimension]):
            REJECT with "canonical_conflict"
    ELSE IF dimension == "primary_fear":
        REJECT with "canonical_conflict"
    ELSE IF dimension == "antagonist":
        IF template[dimension] == "unknown" OR KU[dimension] == "unknown":
            score += 0.5
        ELSE IF incompatible_antagonists(template[dimension], KU[dimension]):
            REJECT with "canonical_conflict"
    ELSE IF dimension == "mechanism":
        warnings.append("canonical_partial", mechanism mismatch message)
    ELSE IF dimension == "twist":
        warnings.append("canonical_partial", twist mismatch message)

IF score < 3.0:
    REJECT with "canonical_conflict"
```

---

### Step 3: KU Avoid Rules Check

**Rule:**
Check if template characteristics violate any KU `avoid` constraints

**Implementation:**
1. Load KU `avoid` array from knowledge_units.json
2. For each avoid rule:
   - Parse rule text for keywords matching template characteristics
   - Keywords to check:
     - Setting keywords: "domestic", "hospital", "digital", "rural", etc.
     - Antagonist keywords: "ghost", "system", "technology", etc.
     - Genre keywords: "supernatural", "systemic", "body_horror", etc.
   - If keyword match found in template:
     - REJECT with reason `"conflict"`
     - Details: Copy verbatim avoid rule text

**Example Avoid Rules:**
- KU-002 (Abject): "Not suitable for pure psychological horror without physical manifestation"
  - Check: If template.canonical_core.setting ≠ "body" AND template.canonical_core.antagonist ≠ "body"
  - Reject if true

- KU-006 (Apartment Horror): "Not suitable for rural or historical settings"
  - Check: If template.canonical_core.setting == "rural"
  - Reject if true

**Edge Case Handling:**
- If avoid rule is ambiguous or non-parseable: Skip (do not reject)
- Log warning for manual review
- Prefer false negatives (accepting when should reject) over false positives

---

### Step 4: Cultural Region Warning Logic

**Rule:**
Warn (but do not block) when region mismatch occurs

**Implementation:**
1. Check if `region_preference` is set
2. If YES:
   - Load KU `region` field
   - If `KU.region ≠ region_preference` AND `KU.region ≠ "Global"`:
     - Add warning:
       - Type: `"region_mismatch"`
       - Message: "Template has no region lock, but KU is {KU.region}-specific. Ensure cultural context is appropriate."

3. Check template region implications:
   - If template uses region-locked KU in canonical design:
     - Extract region from template metadata (if available)
     - Warn if mixing regions (e.g., Korean KU + US KU)

**Special Cases:**
- `region="Global"`: Never triggers warnings
- User can set `region_preference="Global"`: Suppresses all region warnings
- Multiple region-specific KUs selected: Warn if mixing incompatible regions (Korea + US)

---

### Step 5: Final Recommendation Set

**Rule:**
Rank compatible KUs by compatibility_score and present to user

**Ranking:**
1. **perfect** matches first
2. **good** matches second
3. **acceptable** matches third
4. Within each tier, sort by:
   - Fewest warnings
   - Alphabetical by ku_id (deterministic)

**Output Format:**
```json
{
  "template_id": "T-DIG-001",
  "template_name": "Digital Impersonation",
  "total_kus_evaluated": 52,
  "compatible_kus": [
    { "ku_id": "KU-018", "compatibility_score": "perfect", ... },
    { "ku_id": "KU-043", "compatibility_score": "good", ... }
  ],
  "incompatible_kus": [
    { "ku_id": "KU-005", "rejection_reason": "canonical_conflict", ... }
  ],
  "summary": {
    "perfect": 2,
    "good": 5,
    "acceptable": 8,
    "rejected": 37
  },
  "recommendations": [
    "Select 2-5 KUs from compatible list",
    "Prioritize 'perfect' matches for canonical coherence",
    "Review warnings before final selection"
  ]
}
```

---

## 5. Canonical Compatibility Rules (Reference Table)

### 5.1 Hard Blocks (MUST Reject)

| Condition | Reason |
|-----------|--------|
| `primary_fear` mismatch | Core thematic identity violation |
| Both `setting` concrete + different | Spatial impossibility (e.g., digital ≠ rural) |
| Incompatible `antagonist` pair | Mechanically exclusive (ghost vs technology) |
| KU type not in `required_ku_categories` | Category violation |
| User `exclude_tags` match | Explicit user constraint |
| User `exclude_ku_ids` match | Explicit user constraint |
| KU `avoid` rule violated | KU explicitly forbids this usage |

### 5.2 Warnings (SHOULD Flag, Allow Override)

| Condition | Warning Message |
|-----------|-----------------|
| `threat_mechanism` mismatch | "Mechanism mismatch may create tonal inconsistency" |
| `twist_family` mismatch | "Twist expectations may conflict" |
| `region` mismatch (when preference set) | "Cultural context may not align" |
| `setting=abstract` in template or KU | "Abstract setting requires careful grounding" |
| `antagonist=unknown` in template or KU | "Unknown antagonist requires narrative clarity" |

### 5.3 Allowed Mismatches

| Condition | Rationale |
|-----------|-----------|
| `mechanism` differs | Mechanisms can coexist in complex narratives |
| `twist` differs | Twist is outcome, not structure; can be adapted |
| `setting=abstract` mediates concrete settings | Abstract allows flexibility |
| `antagonist=unknown` mediates concrete types | Unknown is conceptually flexible |
| `region=Global` KU with any template | Global KUs are universally applicable |

---

## 6. Worked Example: T-DIG-001 (Digital Impersonation)

### Template Canonical Core
```json
{
  "setting": "digital",
  "primary_fear": "identity_erasure",
  "antagonist": "technology",
  "mechanism": "impersonation",
  "twist": "self_is_monster"
}
```

**Required KU Categories:** `["social_fear", "horror_theme"]`

---

### Candidate KU Evaluation

#### **KU-018: Deepfakes**

**KU Data:**
- Type: `social_fear` ✅
- Region: `Global`
- Canonical Key:
  ```json
  {
    "setting": "digital",
    "primary_fear": "identity_erasure",
    "antagonist": "technology",
    "mechanism": "impersonation",
    "twist": "self_is_monster"
  }
  ```

**Evaluation:**

**Step 1 (Category):** PASS
- `social_fear` ∈ `["social_fear", "horror_theme"]` ✅

**Step 2 (Canonical):**
| Dimension | Template | KU | Match | Score |
|-----------|----------|-----|-------|-------|
| setting | digital | digital | ✅ Exact | +1.0 |
| primary_fear | identity_erasure | identity_erasure | ✅ Exact | +1.0 |
| antagonist | technology | technology | ✅ Exact | +1.0 |
| mechanism | impersonation | impersonation | ✅ Exact | +1.0 |
| twist | self_is_monster | self_is_monster | ✅ Exact | +1.0 |

**Total Score:** 5.0 / 5.0 → PASS

**Step 3 (Avoid Rules):**
- KU-018 avoid: "Not suitable for low-tech or historical settings"
- Template setting: `digital` → No violation ✅

**Step 4 (Region):**
- KU region: `Global`
- No region warning ✅

**Step 5 (Final):**
- **Compatibility Score:** `perfect`
- **Warnings:** None
- **Recommendation:** ✅ **ACCEPT** - Ideal match for this template

---

#### **KU-043: Epistemic Trust Collapse**

**KU Data:**
- Type: `social_fear` ✅
- Region: `Global`
- Canonical Key:
  ```json
  {
    "setting": "digital",
    "primary_fear": "identity_erasure",
    "antagonist": "technology",
    "mechanism": "erosion",
    "twist": "ambiguity"
  }
  ```

**Evaluation:**

**Step 1 (Category):** PASS
- `social_fear` ∈ `["social_fear", "horror_theme"]` ✅

**Step 2 (Canonical):**
| Dimension | Template | KU | Match | Score |
|-----------|----------|-----|-------|-------|
| setting | digital | digital | ✅ Exact | +1.0 |
| primary_fear | identity_erasure | identity_erasure | ✅ Exact | +1.0 |
| antagonist | technology | technology | ✅ Exact | +1.0 |
| mechanism | impersonation | erosion | ❌ Mismatch (warning) | +0.0 |
| twist | self_is_monster | ambiguity | ❌ Mismatch (warning) | +0.0 |

**Total Score:** 3.0 / 5.0 → PASS (meets minimum threshold)

**Step 3 (Avoid Rules):**
- KU-043 avoid: "Not suitable for low-tech settings"
- Template setting: `digital` → No violation ✅

**Step 4 (Region):**
- KU region: `Global`
- No region warning ✅

**Step 5 (Final):**
- **Compatibility Score:** `good`
- **Warnings:**
  1. `canonical_partial`: "Template uses impersonation mechanism, KU uses erosion. Verify compatibility."
  2. `canonical_partial`: "Template expects self_is_monster twist, KU suggests ambiguity. May create tonal conflict."
- **Recommendation:** ⚠️ **ACCEPT WITH WARNINGS** - Compatible but requires narrative care to reconcile mechanism/twist differences

---

#### **KU-005: Han (Korean Resentment)**

**KU Data:**
- Type: `social_fear` ✅
- Region: `Korea`
- Canonical Key:
  ```json
  {
    "setting": "abstract",
    "primary_fear": "social_displacement",
    "antagonist": "system",
    "mechanism": "erosion",
    "twist": "inevitability"
  }
  ```

**Evaluation:**

**Step 1 (Category):** PASS
- `social_fear` ∈ `["social_fear", "horror_theme"]` ✅

**Step 2 (Canonical):**
| Dimension | Template | KU | Match | Score |
|-----------|----------|-----|-------|-------|
| setting | digital | abstract | ⚠️ Compatible | +0.5 |
| primary_fear | identity_erasure | social_displacement | ❌ **HARD BLOCK** | - |

**Result:** PRIMARY FEAR MISMATCH → **REJECT**

**Rejection Details:**
- **Rejection Reason:** `canonical_conflict`
- **Details:**
  - "Primary fear mismatch: template requires identity_erasure, KU provides social_displacement"
  - "Primary fear is the core thematic identity; this mismatch creates fundamental incoherence"

**Step 5 (Final):**
- **Status:** ❌ **REJECT** - Primary fear conflict is non-negotiable
- **User Override:** Not recommended even with manual override
- **Alternative:** Use KU-005 with templates focused on social_displacement (e.g., T-SYS-001, T-APT-001)

---

## 7. Summary of Example Results

| KU | Category Match | Canonical Score | Warnings | Final Status |
|----|----------------|-----------------|----------|--------------|
| KU-018 | ✅ | 5.0 / 5.0 | None | ✅ ACCEPT (perfect) |
| KU-043 | ✅ | 3.0 / 5.0 | 2 warnings | ⚠️ ACCEPT (good) |
| KU-005 | ✅ | N/A | N/A | ❌ REJECT (primary fear conflict) |

**Recommended Selection for T-DIG-001:**
1. KU-018 (Deepfakes) - Perfect match
2. KU-043 (Epistemic Trust) - Good match with warnings
3. Select 0-3 additional compatible KUs from perfect/good tiers

---

## 8. Edge Cases & Special Handling

### 8.1 Writing Technique KUs (KU-030 to KU-036, KU-051)

**Default Behavior:**
- Automatically excluded from selection (per D-004)
- Added to `exclude_ku_ids` by default

**User Override:**
- User can explicitly include by removing from `exclude_ku_ids`
- System adds warning: "Writing technique KUs affect prose style, not canonical structure"

### 8.2 Abstract Settings

**Rule:**
- `setting=abstract` in template: KU with ANY setting is compatible
- `setting=abstract` in KU: Compatible with ANY template setting
- Score: +0.5 (compatible mismatch, not perfect)

**Rationale:**
- Abstract settings are conceptual, not spatial
- Allow maximum flexibility for thematic horror

### 8.3 Unknown Antagonists

**Rule:**
- `antagonist=unknown` in template: KU with ANY antagonist is compatible
- `antagonist=unknown` in KU: Compatible with ANY template antagonist
- Score: +0.5 (compatible mismatch, not perfect)

**Rationale:**
- Unknown represents indeterminacy, not specific entity type
- Philosophically compatible with any concrete type

### 8.4 Multiple KU Selection

**Conflict Detection:**
- When user selects multiple KUs, check for inter-KU conflicts:
  - If two KUs have contradictory `avoid` rules
  - If two KUs have incompatible canonical keys (e.g., different primary_fears)
- Warn user but allow selection (user judgment overrides)

**Example:**
- User selects KU-018 (identity_erasure) + KU-005 (social_displacement)
- System warns: "Selected KUs have different primary_fears. Ensure narrative coherence."

### 8.5 Ambiguous Avoid Rules

**Rule:**
- If KU avoid rule cannot be parsed or matched to template characteristics:
  - Do NOT reject
  - Add warning: "KU has usage constraint: [verbatim avoid text]. Manual review required."

**Example:**
- KU avoid: "Do not use for pure psychological horror without physical manifestation"
- Cannot algorithmically determine "psychological horror" from canonical values
- Flag for manual review

---

## 9. Implementation Guidance

### 9.1 Data Sources

**Required Files:**
1. `phase1_foundation/03_templates/template_skeletons_v1.json`
2. `phase1_foundation/01_knowledge_units/knowledge_units.json`
3. `phase1_foundation/02_canonical_abstraction/resolved_canonical_keys.json`

**Load Order:**
1. Load template by `template_id`
2. Load all 52 KUs
3. Load all 45 resolved canonical keys (map KU-ID → canonical_key)
4. Process selection algorithm

### 9.2 Performance Considerations

**Optimization:**
- Phase 2-A processes single template at a time (no batch)
- Pre-load all KUs and canonical keys once per session
- Cache compatible KU sets per template for instant retrieval

**Expected Performance:**
- Initial load: <1 second
- Selection processing: <100ms
- UI response: Immediate

### 9.3 Error Handling

**Missing Data:**
- If template_id not found: Return error "Template {id} does not exist"
- If KU missing canonical_key: Skip KU with warning "KU-XXX has no canonical key (likely writing_technique)"
- If KU missing required fields: Skip with warning

**Invalid Constraints:**
- If `region_preference` not in dataset: Warn and ignore
- If `exclude_tags` contains non-existent tag: Warn and ignore
- If `exclude_ku_ids` contains invalid ID: Warn and ignore

---

## 10. Future Extensions (Phase 2-B+)

**Not Implemented in v0:**
- Semantic similarity scoring
- User preference learning
- Batch template processing
- Automatic "best match" selection
- LLM-based avoid rule parsing

**Defer to Phase 3:**
- Full automation
- Template auto-suggestion based on KU input
- Dynamic canonical key generation

---

## 11. Validation Checklist

Before implementing, verify:

- [ ] All 5 canonical dimensions have compatibility rules defined
- [ ] Hard block conditions are exhaustive and mutually exclusive
- [ ] Warning conditions are actionable (user can understand and override)
- [ ] Worked example produces expected results
- [ ] Edge cases have explicit handling rules
- [ ] No references to Phase 1 data modifications
- [ ] No ML/embedding dependencies
- [ ] Output format is JSON-serializable
- [ ] Performance targets are reasonable (<1s total processing)

---

## 12. Document Maintenance

**Version History:**
- v0.1 (2026-01-08): Initial specification for Phase 2-A

**Review Schedule:**
- After first 10 manual selections: Review hard block accuracy
- After first 50 manual selections: Review warning usefulness
- Quarterly: Review edge case handling

**Change Process:**
- All changes require updating this specification first
- Implementation must match specification (specification is source of truth)
- Breaking changes require new major version (v1.0, v2.0, etc.)

---

## 13. References

- Phase 1 Foundation: `phase1_foundation/`
- Canonical Enum: `docs/canonical_enum.md`
- Decision Log: `docs/decision_log.md` (D-002, D-004, D-005)
- System Architecture: `docs/system_architecture.md`

---

**END OF SPECIFICATION**

Next Step: Implement KU Selector according to this specification.
