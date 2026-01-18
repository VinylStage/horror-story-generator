# KU → Canonical Key Generation Rules

> **Version:** v1.5.0 <!-- x-release-please-version -->
> **Enum Version:** 1.0
> **Status:** Active

---

## 1. Purpose

This document defines the RULES and PROCESS for generating a Canonical Key (CK) from upstream inputs including Knowledge Units (KU), research context, and story intent.

**Authoritative Sources:**
- `/docs/technical/canonical_enum.md` — Human-readable dimension definitions
- `/schema/canonical_key.schema.json` — Machine-readable JSON Schema
- `/assets/canonical/canonical_enum.md` — Assets copy of definitions

---

## 2. What Canonical Key IS and IS NOT

### CK IS Responsible For:

| Responsibility | Description |
|----------------|-------------|
| Structural identity | The "horror DNA" of a story or template |
| Deduplication signal | Detecting when two stories are structurally identical |
| Template uniqueness | Ensuring no two templates share the same CK |
| Matching compatibility | Linking research/KU to appropriate templates |

### CK IS NOT Responsible For:

| Out of Scope | Reason |
|--------------|--------|
| Writing style | Prose quality is not structural |
| Locale/names | "Korean apartment" vs "Japanese apartment" → same CK |
| Surface details | Character names, specific dates, visual descriptions |
| Narrative length | Short story vs novella can share CK |
| Cultural markers | Cultural context is variation, not identity |

---

## 3. Canonical Key Structure

A complete Canonical Key MUST contain exactly 5 dimensions, each with a SINGLE value:

```json
{
  "setting_archetype": "<one value>",
  "primary_fear": "<one value>",
  "antagonist_archetype": "<one value>",
  "threat_mechanism": "<one value>",
  "twist_family": "<one value>"
}
```

All fields are REQUIRED. No additional properties are permitted.

---

## 4. Input Sources

### 4.1 Research Cards (canonical_affinity)

Research cards output `canonical_affinity` with ARRAYS of candidate values:

```json
"canonical_affinity": {
  "setting": ["apartment", "liminal"],
  "primary_fear": ["isolation", "social_displacement"],
  "antagonist": ["system", "collective"],
  "mechanism": ["surveillance", "confinement"]
}
```

**Note:** Research output uses abbreviated keys (`setting`, `antagonist`, `mechanism`, `twist`). These MUST be mapped to schema keys (`setting_archetype`, `antagonist_archetype`, `threat_mechanism`, `twist_family`).

### 4.2 Knowledge Units

KUs may contain fields that hint at canonical dimensions but use LEGACY terminology:

| KU Field | Maps To | Notes |
|----------|---------|-------|
| `setting_archetype` | `setting_archetype` | May use legacy values (e.g., "domestic" → "domestic_space") |
| `primary_fear` | `primary_fear` | May use non-canonical values (e.g., "ego_death" → requires mapping) |
| `antagonist_archetype` | `antagonist_archetype` | May use specific names (e.g., "doppelganger" → "unknown") |
| `genre` | Hints only | Not directly mappable |
| `template_affinity` | Hints only | Not directly mappable |

### 4.3 Story Intent

User-provided topic or intent (e.g., "Korean apartment noise horror") provides contextual signals but MUST be interpreted through canonical dimensions.

---

## 5. Dimension-by-Dimension Decision Rules

### 5.1 setting_archetype

**Question:** Where does the horror primarily occur?

| Value | Signals to Look For |
|-------|---------------------|
| `apartment` | Shared walls, neighbors, elevators, floor noise, urban density |
| `hospital` | Medical staff, patients, treatment, clinical environment |
| `rural` | Isolation, farmland, small towns, tradition, hidden history |
| `domestic_space` | Single-family home, family dynamics, "safe" space violated |
| `digital` | Online, virtual, screens, accounts, digital identity |
| `liminal` | Transit spaces, hallways, waiting rooms, backrooms, non-places |
| `infrastructure` | Public systems (subway, power grid, water), societal collapse |
| `body` | The horror occurs inside a body; body as environment |
| `abstract` | No specific physical space; conceptual or systemic horror |

**Decision Rule:**
1. Identify the PRIMARY location where horror unfolds
2. Abstract from specific details (e.g., "Seoul apartment" → `apartment`)
3. If multiple spaces, choose where the CLIMAX occurs
4. If genuinely no physical space, use `abstract`

**Common Pitfalls:**
- ❌ "Hospital in a rural area" → Choose PRIMARY space (usually `hospital`)
- ❌ "Online harassment about apartment" → Digital is medium, apartment is setting → `apartment` unless the digital space IS the horror
- ❌ "Body horror in apartment" → If the body is the primary site of horror, consider `body`

### 5.2 primary_fear

**Question:** What is the SINGLE ultimate fear this story evokes?

| Value | Core Meaning |
|-------|--------------|
| `loss_of_autonomy` | Cannot control my own body or actions |
| `identity_erasure` | I am no longer "me"; my identity is dissolving |
| `social_displacement` | I am being pushed out of society/community |
| `contamination` | I am being polluted, infected, or corrupted |
| `isolation` | I am utterly alone with no hope of connection |
| `annihilation` | My existence will end completely |

**Decision Rule:**
1. This is the HIGHEST PRIORITY dimension
2. All other dimensions serve this fear
3. Ask: "What does the protagonist MOST fear losing?"
4. Select ONE value only; if multiple apply, choose the most fundamental

**Priority Hierarchy (when in conflict):**
```
annihilation > identity_erasure > loss_of_autonomy > isolation > social_displacement > contamination
```

**Common Pitfalls:**
- ❌ "Fear of death" → Could be `annihilation` (physical) OR `identity_erasure` (self-loss) — analyze deeper
- ❌ "Pandemic story" → Not automatically `contamination`; could be `isolation` or `social_displacement`
- ❌ Conflating surface threat with core fear

### 5.3 antagonist_archetype

**Question:** What TYPE of entity or force causes the horror?

| Value | Description |
|-------|-------------|
| `ghost` | Traditional supernatural entity; spirits, specters |
| `system` | Institution, bureaucracy, social structure |
| `technology` | AI, machines, software, technological systems |
| `body` | The threat comes from within a body |
| `collective` | Crowd, mob, community, consensus |
| `unknown` | Unidentifiable; could be anything or nothing |

**Decision Rule:**
1. Identify WHAT is causing the horror (not where or how)
2. Abstract to archetype (e.g., "evil AI" → `technology`, "apartment complex committee" → `system`)
3. If antagonist is ambiguous by design, use `unknown`
4. If multiple antagonists, choose the PRIMARY source

**Common Pitfalls:**
- ❌ "Haunted hospital" → `ghost` is antagonist, `hospital` is setting — don't conflate
- ❌ "Doppelganger" → Usually `unknown` unless specifically technological (`technology`)
- ❌ "Disease" → Could be `body` (internal) or `unknown` (external pathogen)

### 5.4 threat_mechanism

**Question:** HOW does the horror operate and persist?

| Value | Mechanism |
|-------|-----------|
| `surveillance` | Being watched, monitored, exposed |
| `possession` | Body/mind being taken over |
| `debt` | Obligation, contract, owing something |
| `infection` | Spreading, contaminating, replicating |
| `impersonation` | Being replaced, copied, mimicked |
| `confinement` | Trapped, restricted, imprisoned |
| `erosion` | Gradual wearing down, slow decay |
| `exploitation` | Being used, extracted from, consumed |

**Decision Rule:**
1. Ask: "How does the horror WORK on the protagonist?"
2. This is NOT about scare tactics; it's about the structural mechanism
3. Choose the mechanism that enables the horror to PERSIST

**Common Pitfalls:**
- ❌ Choosing based on scary scenes rather than structural operation
- ❌ "Jump scares" → This is presentation, not mechanism
- ❌ "Ghost watching" → Could be `surveillance` OR `haunting` (use `possession` if taking control)

### 5.5 twist_family

**Question:** What is the structural resolution or revelation type?

| Value | Pattern |
|-------|---------|
| `revelation` | Hidden truth is exposed; "it was X all along" |
| `inevitability` | Cannot escape; fate was sealed |
| `inversion` | Roles/meanings flip; victim becomes perpetrator |
| `circularity` | End returns to beginning; cycle repeats |
| `self_is_monster` | Protagonist discovers they are the threat |
| `ambiguity` | Resolution is unclear; interpretation impossible |

**Decision Rule:**
1. Consider the ENDING structure, not the mid-story twists
2. If no twist, ask: "What is the NATURE of the conclusion?"
3. `inevitability` is common when horror is systemic
4. `ambiguity` is used when deliberately unresolved

**Common Pitfalls:**
- ❌ Every story with a reveal is `revelation` — check if it's actually `inversion` or `self_is_monster`
- ❌ Sad ending ≠ `inevitability`; `inevitability` requires structural inescapability
- ❌ Using `ambiguity` for incomplete analysis

---

## 6. Conflict Resolution Rules

### 6.1 Priority of Dimensions

When making trade-offs, dimensions have this priority:

1. **primary_fear** — ALWAYS wins; all other dimensions serve this
2. **antagonist_archetype** — The source of horror
3. **threat_mechanism** — How horror operates
4. **setting_archetype** — Where horror occurs
5. **twist_family** — Structural resolution

### 6.2 When Multiple Candidates Exist

**For canonical_affinity arrays:**

1. If array contains 1 value → Use that value
2. If array contains 2+ values → Apply rules:
   - For `primary_fear`: Choose the more fundamental (see hierarchy)
   - For `setting_archetype`: Choose where CLIMAX occurs
   - For `antagonist_archetype`: Choose PRIMARY source of horror
   - For `threat_mechanism`: Choose what enables PERSISTENCE
   - For `twist_family`: Derive from story structure if not provided

### 6.3 Tie-Breaking Principles

When two values seem equally valid:

1. **Prefer the more specific** over the more generic
2. **Prefer the more structural** over the more surface-level
3. **Prefer alignment** with primary_fear
4. If still tied, **document the choice** and proceed

### 6.4 Cross-Dimension Consistency

After selecting all 5 values, verify:

- Does the `threat_mechanism` logically work in the `setting_archetype`?
- Does the `antagonist_archetype` naturally produce this `primary_fear`?
- Does the `twist_family` resolve the horror appropriately?

If inconsistent, re-evaluate starting from `primary_fear`.

---

## 7. Validation & Failure Handling

### 7.1 JSON Schema Validation

All generated Canonical Keys MUST pass validation against:
```
/schema/canonical_key.schema.json
```

Validation requirements:
- All 5 fields present
- Each field has exactly one value
- Each value is from the allowed enum
- No additional properties

### 7.2 Invalid Value Handling

If LLM/research output contains invalid values:

| Scenario | Action |
|----------|--------|
| Value not in enum (e.g., "doppelganger") | Map to nearest valid value or use `unknown` |
| Empty array for dimension | MUST derive from other signals |
| Missing dimension entirely | MUST derive from context or mark as unassignable |
| Multiple values where one required | Apply conflict resolution rules |

### 7.3 When CK Cannot Be Assigned

If Canonical Key cannot be confidently derived:

1. **First attempt:** Use LLM to clarify with focused prompt
2. **Second attempt:** Use defaults based on input type:
   - Research topic about systems → `system` antagonist, `abstract` setting
   - Research topic about technology → `technology` antagonist, `digital` setting
3. **Final fallback:** Mark as `requires_manual_review`

**MUST NOT:**
- Guess randomly
- Use placeholder values
- Skip dimensions

### 7.4 Logging Requirements

All CK generation SHOULD log:
- Input signals used
- Candidates considered for each dimension
- Final selection with brief rationale
- Validation result

---

## 8. Worked Examples

### Example 1: Korean Apartment Noise Horror

**Input:**
- Topic: "Korean apartment buildings and floor noise disputes leading to violence"
- KU hints: `setting_archetype: "apartment"`, `primary_fear: "social_displacement"`

**Analysis:**

| Dimension | Candidates | Selection | Rationale |
|-----------|------------|-----------|-----------|
| `setting_archetype` | apartment | `apartment` | Explicit in topic |
| `primary_fear` | social_displacement, isolation | `social_displacement` | Core fear is being pushed out of community |
| `antagonist_archetype` | system, collective | `system` | Apartment rules/management structure |
| `threat_mechanism` | surveillance, confinement | `surveillance` | Neighbors monitoring and reporting |
| `twist_family` | inevitability | `inevitability` | Cannot escape the system |

**Output:**
```json
{
  "setting_archetype": "apartment",
  "primary_fear": "social_displacement",
  "antagonist_archetype": "system",
  "threat_mechanism": "surveillance",
  "twist_family": "inevitability"
}
```

---

### Example 2: Deepfake Identity Theft

**Input:**
- Topic: "AI-generated deepfakes stealing someone's digital identity"
- canonical_affinity from research:
  ```json
  {
    "setting": ["digital"],
    "primary_fear": ["identity_erasure", "loss_of_autonomy"],
    "antagonist": ["technology"],
    "mechanism": ["impersonation"]
  }
  ```

**Analysis:**

| Dimension | Candidates | Selection | Rationale |
|-----------|------------|-----------|-----------|
| `setting_archetype` | digital | `digital` | Horror occurs in digital space |
| `primary_fear` | identity_erasure, loss_of_autonomy | `identity_erasure` | Core fear is self becoming indistinguishable from fake |
| `antagonist_archetype` | technology | `technology` | AI/deepfake technology is threat |
| `threat_mechanism` | impersonation | `impersonation` | Being copied/replaced |
| `twist_family` | (not in input) | `self_is_monster` | Protagonist cannot prove they are authentic |

**Output:**
```json
{
  "setting_archetype": "digital",
  "primary_fear": "identity_erasure",
  "antagonist_archetype": "technology",
  "threat_mechanism": "impersonation",
  "twist_family": "self_is_monster"
}
```

---

## 9. Key Name Mapping Reference

Current implementations may use abbreviated keys. Map as follows:

| Source Key | Canonical Key Schema |
|------------|---------------------|
| `setting` | `setting_archetype` |
| `primary_fear` | `primary_fear` |
| `antagonist` | `antagonist_archetype` |
| `mechanism` | `threat_mechanism` |
| `twist` | `twist_family` |

---

## 10. Related Documents

| Document | Purpose |
|----------|---------|
| `/docs/technical/canonical_enum.md` | Human-readable enum definitions |
| `/schema/canonical_key.schema.json` | Machine-readable JSON Schema |
| `/docs/technical/CANONICAL_KEY_APPLICATION_SCOPE.md` | Where CK is generated/consumed |

---

## 11. Story-to-Template Alignment Scoring

After story generation, the system extracts a Canonical Key from the **generated story text** and compares it against the template's predefined `canonical_core`. This provides alignment scoring for quality validation.

### 11.1 Purpose

| Goal | Description |
|------|-------------|
| Validate output | Verify story matches intended structural pattern |
| Track divergence | Identify where story deviates from template |
| Quality signal | Provide metrics for future improvements |

### 11.2 Extraction Process

1. Story text → LLM analysis
2. LLM outputs `canonical_affinity` (arrays)
3. Collapse to `canonical_core` (single values) using same rules as Section 6
4. Compare story CK vs template CK dimension-by-dimension

### 11.3 Alignment Score Calculation

```
alignment_score = matched_dimensions / 5 × 100%
```

**Dimension-by-Dimension Comparison:**

| Template Value | Story Value | Match? |
|----------------|-------------|--------|
| `apartment` | `apartment` | Yes |
| `social_displacement` | `social_displacement` | Yes |
| `system` | `collective` | No |
| `surveillance` | `surveillance` | Yes |
| `inevitability` | `inevitability` | Yes |

**Result:** 4/5 = 80% alignment

### 11.4 Interpretation Guide

| Score | Interpretation | Recommended Action |
|-------|----------------|-------------------|
| 100% | Perfect alignment | Story matches template structure exactly |
| 80-99% | High alignment | Minor divergence, usually acceptable |
| 60-79% | Moderate alignment | Story drifted from template; review recommended |
| <60% | Low alignment | Significant divergence; may indicate prompt issues |

### 11.5 Handling Divergences

When story CK diverges from template CK:

1. **Enforcement policy** — Action depends on `STORY_CK_ENFORCEMENT` setting
2. **Retry mode** — Low alignment can trigger regeneration with different template
3. **Strict mode** — Low alignment can reject the story entirely
4. **Metadata recorded** — Full comparison and enforcement result stored

**Enforcement Policies:**
| Policy | Action on Low Alignment |
|--------|-------------------------|
| `none` | Always accept (disabled) |
| `warn` | Log warning, accept anyway (default) |
| `retry` | Re-attempt with different template |
| `strict` | Reject story entirely |

**Divergence Example:**
```json
{
  "dimension": "antagonist_archetype",
  "template": "system",
  "story": "collective"
}
```

This indicates the LLM wrote a story emphasizing collective/mob threat when the template expected systemic/institutional threat.

### 11.6 Configuration

**Extraction:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `ENABLE_STORY_CK_EXTRACTION` | `true` | Enable/disable extraction |
| `STORY_CK_MODEL` | (none) | Override model for extraction |

**Enforcement:**
| Env Variable | Default | Description |
|--------------|---------|-------------|
| `STORY_CK_ENFORCEMENT` | `warn` | Policy: none/warn/retry/strict |
| `STORY_CK_MIN_ALIGNMENT` | `0.6` | Minimum alignment score (0.0-1.0) |

### 11.7 Related Implementation

| File | Role |
|------|------|
| `src/story/canonical_extractor.py` | Extraction logic |
| `src/story/generator.py` | Integration point |

---

**Note:** This document defines RULES for Canonical Key generation. It does not contain LLM prompts or implementation code. For integration, see the research executor source code.
