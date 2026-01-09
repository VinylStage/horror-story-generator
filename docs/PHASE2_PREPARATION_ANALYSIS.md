# Phase 2 Preparation Analysis

**Document Type:** Phase 1 → Phase 2 Transition Snapshot
**Date:** 2026-01-09
**Status:** IMMUTABLE REFERENCE DOCUMENT
**Purpose:** Evidence-based analysis of structural limitations preventing long-term non-duplicate story generation

---

## Executive Summary

This document establishes why the current Phase 1 system **cannot guarantee non-duplicate story generation** during long-running or scheduled operations. All findings are based on direct code and data inspection.

**Core Finding:** The system uses a **static, single prompt** for all generations with **zero memory** of previous outputs. Duplication probability increases with each generation because the conceptual space is constrained and untracked.

---

## 1. Current Template Constraints

### 1.1 Template Selection Mechanism

**Status:** STATIC / ABSENT

**Evidence:**

The main execution path in `main.py:279` calls:
```python
result = run_basic_generation()
```

Which in `main.py:72` calls:
```python
result = generate_horror_story()  # No arguments
```

Which in `horror_story_generator.py:640-692` uses:
```python
def generate_horror_story(
    template_path: Optional[str] = None,  # DEFAULT: None
    custom_request: Optional[str] = None,  # DEFAULT: None
    ...
):
    template = None
    if template_path:  # FALSE when None
        template = load_prompt_template(template_path)
    else:
        logger.info("기본 심리 공포 프롬프트 사용 (템플릿 없음)")
```

**Result:** Every generation uses `template=None`, which triggers the **same hardcoded system prompt** in `build_system_prompt()` (lines 184-247).

### 1.2 System Prompt Content

**Location:** `horror_story_generator.py:185-245`

**Structure:**
```
- Role definition: "specialist in quiet psychological horror"
- Setting constraint: "Ordinary spaces (apartment, office, subway...)"
- Horror intensity: LEVEL 4
- Ending rules (cyclic threat)
- Narrative constraints (1st person, no over-explanation)
- Story structure (4-act ratio)
- Target length: 3,000-4,000 characters
- Output language: Korean
```

**Key Observation:** The prompt defines a **narrow conceptual space**:
- Only "everyday psychological horror"
- Only "ordinary spaces"
- Only "system malfunction, abnormal behavior of others, cracks in reality"
- Only first-person perspective
- Only unresolved endings

This narrow space **mathematically limits** the number of semantically distinct stories that can be generated.

### 1.3 User Prompt Content

**Location:** `horror_story_generator.py:336`

When `custom_request=None` (which is always true in the current execution path):
```python
user_prompt = "Following the guidelines above, write an original and unsettling horror story."
```

**Result:** The user prompt is **identical for every generation**.

### 1.4 Unused Template Assets

**Phase 1 Foundation Assets (NOT REFERENCED IN CODE):**

| Asset | Location | Status |
|-------|----------|--------|
| 15 Template Skeletons | `phase1_foundation/03_templates/template_skeletons_v1.json` | **UNUSED** |
| 52 Knowledge Units | `phase1_foundation/01_knowledge_units/knowledge_units.json` | **UNUSED** |
| Canonical Enum | `phase1_foundation/02_canonical_abstraction/canonical_enum.md` | **UNUSED** |
| Resolved Canonical Keys | `phase1_foundation/02_canonical_abstraction/resolved_canonical_keys.json` | **UNUSED** |

**Verification:**
```bash
grep -r "phase1_foundation\|canonical_core\|KU-\|template_id" *.py
# Result: No matches
```

---

## 2. Root Causes of Duplication Risk

### 2.1 Definition of "Duplicate"

In this system, duplication can occur at three levels:

#### Level 1: Prompt-Level Duplication
**Definition:** Identical input prompts sent to LLM
**Current Status:** **100% duplication** - Every generation uses the same system prompt and user prompt

#### Level 2: Semantic-Level Duplication
**Definition:** Stories that cover the same conceptual territory despite different surface text
**Current Status:** **HIGH RISK** - Constrained to "everyday psychological horror in ordinary spaces"

#### Level 3: Theme-Level Duplication
**Definition:** Stories with the same core narrative pattern (setting + fear + mechanism)
**Current Status:** **HIGH RISK** - No theme tracking, no variation mechanism

### 2.2 Evidence of Semantic Duplication

**Observed duplication in generated stories (same day):**

| Timestamp | Title | Setting | Theme |
|-----------|-------|---------|-------|
| 20260108_235002 | 퇴근길의 규칙 | Subway (3호선, 오후 6시 17분) | Anomaly in commute routine |
| 20260108_235615 | 퇴근길의 반복 | Subway (3호선, 오후 6시 32분) | Anomaly in commute routine |

**Analysis:**
- Both stories are about **commuting**
- Both occur at **approximately the same time** (~6pm)
- Both involve **subway** (Line 3)
- Both follow the pattern: "routine → anomaly → escalation → unresolved threat"
- Both use nearly **identical opening sentences**: "나는 매일 같은 시간에 퇴근한다"

**This is semantic duplication despite different surface text.**

### 2.3 Why Duplication Probability Increases Over Time

The probability of generating a semantically distinct story **decreases** with each generation because:

1. **Fixed Conceptual Space:** The prompt constrains stories to:
   - Everyday settings (apartment, office, subway, convenience store)
   - Psychological horror (no supernatural explanation)
   - First-person narration
   - Unresolved endings

2. **No Exclusion Mechanism:** The system has no way to:
   - Know what settings have already been used
   - Know what themes have already been explored
   - Avoid repeating narrative patterns

3. **LLM Statistical Distribution:** Without steering, the LLM will:
   - Favor common patterns in its training data
   - Converge toward "mode collapse" for the given prompt
   - Generate variations within a narrow distribution

**Mathematical Reality:** If the prompt allows N semantically distinct story patterns, and no mechanism tracks what has been generated, the expected number of collisions after K generations follows the birthday problem distribution:

```
P(collision) ≈ 1 - e^(-K²/2N)
```

For a constrained prompt like this, N might be ~20-50 distinct patterns. After 10 generations, collision probability is already significant.

---

## 3. Absence of Memory and Its Consequences

### 3.1 Verification of Memory Absence

**Search for persistence mechanisms:**
```bash
grep -rn "pickle\|sqlite\|database\|memory\|history\|previous" horror_story_generator.py main.py
# Result: No matches
```

**Result:** The system has **ZERO** persistent memory of:
- Previously generated stories
- Previously used themes
- Previously used settings
- Previously used narrative patterns

### 3.2 Current Storage Structure

**Output Directory:** `generated_stories/`

**File Structure:**
```
horror_story_YYYYMMDD_HHMMSS.md         # Story content
horror_story_YYYYMMDD_HHMMSS_metadata.json  # Generation metadata
```

**Metadata Content Example** (`horror_story_20260109_001402_metadata.json`):
```json
{
  "generated_at": "2026-01-09T00:14:02.925051",
  "model": "claude-sonnet-4-5-20250929",
  "template_used": null,
  "custom_request": null,
  "config": { "max_tokens": 8192, "temperature": 0.8 },
  "word_count": 2117,
  "usage": { "input_tokens": 747, "output_tokens": 2149, "total_tokens": 2896 },
  "title": "층간소음",
  "tags": ["호러", "horror"],
  "description": "..."
}
```

**What IS stored:**
- ✅ Generation timestamp
- ✅ Model configuration
- ✅ Token usage
- ✅ Title (extracted from output)
- ✅ Generic tags (always `["호러", "horror"]`)

**What is NOT stored:**
- ❌ Canonical identity (setting, fear, antagonist, mechanism, twist)
- ❌ Semantic fingerprint or content hash
- ❌ Theme classification
- ❌ Knowledge Units used
- ❌ Narrative pattern identification

### 3.3 Why Filesystem Presence Cannot Prevent Semantic Duplication

**Current State:**
- Stories are stored as **isolated files**
- No **index** or **registry** exists
- No **searchable metadata** exists
- The generation process **never reads** the output directory

**Evidence:**
```python
# generate_horror_story() does NOT:
# - List existing story files
# - Read existing metadata
# - Check for thematic overlap
# - Modify prompt based on history
```

**Consequence:** Even if 100 stories about "subway commute horror" already exist, the system will happily generate the 101st because it has no awareness of what exists.

---

## 4. Why Phase 1 Structure Cannot Solve Duplication

### 4.1 Structural Limitations

| Capability | Required for Non-Duplication | Phase 1 Status |
|------------|------------------------------|----------------|
| Template rotation | Vary conceptual space per generation | ❌ Static single prompt |
| Theme tracking | Know what themes have been used | ❌ Not implemented |
| Semantic memory | Compare new ideas against existing ones | ❌ Not implemented |
| Canonical identity | Classify stories by structured dimensions | ❌ Not implemented |
| KU integration | Inject varied knowledge per generation | ❌ Assets exist but unused |
| Generation index | Queryable record of all outputs | ❌ Not implemented |

### 4.2 Why Adding Features to Phase 1 Would Not Be Sufficient

Even if we added simple checks like "don't repeat the same title", it would not prevent semantic duplication because:

1. **Surface vs. Semantic:** "퇴근길의 규칙" and "퇴근길의 반복" have different titles but are semantically identical
2. **Prompt Constraint:** The prompt itself forces stories into a narrow space
3. **No Structured Classification:** Without canonical dimensions (setting, fear, mechanism), we cannot define what "same" means

### 4.3 Evidence: Phase 1 Assets Are Designed for This But Unused

**Template Skeletons** (`template_skeletons_v1.json`) include:
```json
{
  "template_id": "T-SYS-001",
  "canonical_core": {
    "setting": "abstract",
    "primary_fear": "social_displacement",
    "antagonist": "system",
    "mechanism": "erosion",
    "twist": "inevitability"
  }
}
```

If templates were used, they would provide **structural variation**.

**Knowledge Units** (`knowledge_units.json`) include:
```json
{
  "ku_id": "KU-001",
  "type": "horror_concept",
  "primary_fear": "cognitive_dissonance",
  "core_idea": "Art-Horror is defined by...",
  "usage_rules": ["Use when designing monsters..."],
  "avoid": ["Do not use for pure jump scares..."]
}
```

If KUs were used, they would inject **varied conceptual content** per generation.

**Current Status:** These assets exist in `phase1_foundation/` but are **never loaded or referenced** by the runtime code.

---

## 5. Conceptual Requirements for Phase 2

### 5.1 What Must Change (Conceptually)

To guarantee non-duplicate story generation over long runs, the system must gain:

#### 5.1.1 Input Variation
**Need:** Each generation must receive **different instructions**
**Why:** Identical prompts → Identical conceptual space → High collision probability

#### 5.1.2 Generation Memory
**Need:** The system must **know what has been generated**
**Why:** Without memory, the system cannot avoid repetition

#### 5.1.3 Semantic Classification
**Need:** Each story must be **classified by structured dimensions**
**Why:** Surface-level comparison (title, first paragraph) is insufficient

#### 5.1.4 Theme Exclusion
**Need:** The system must be able to **exclude recently used themes**
**Why:** Simple rotation without exclusion will still cause long-term repetition

#### 5.1.5 Knowledge Injection
**Need:** Varied knowledge content must be **injected into prompts**
**Why:** The same prompt with the same knowledge produces the same conceptual patterns

### 5.2 What This Document Does NOT Define

This analysis establishes **what is missing** but does NOT propose:

- ❌ Specific tools or technologies (no "use vector DB", "use embeddings")
- ❌ Implementation architecture
- ❌ Code changes
- ❌ Data schemas
- ❌ API designs

These will be defined in Phase 2 design specifications.

---

## 6. Summary of Verified Findings

### 6.1 Verified: Template Usage Limitations

| Finding | Evidence |
|---------|----------|
| Template selection is static | `generate_horror_story()` always called with `template_path=None` |
| System prompt is hardcoded | `build_system_prompt()` returns fixed string when `template=None` |
| User prompt is identical every time | `build_user_prompt()` returns fixed string when `custom_request=None` |
| 15 template skeletons exist but are unused | No code reference to `template_skeletons_v1.json` |
| 52 Knowledge Units exist but are unused | No code reference to `knowledge_units.json` |

### 6.2 Verified: Duplication Risk

| Finding | Evidence |
|---------|----------|
| Prompt-level duplication is 100% | Same code path every execution |
| Semantic duplication observed | Two "퇴근길" subway stories generated same day |
| No theme tracking exists | Metadata has no canonical keys |
| No generation memory exists | No database, no index, no history mechanism |

### 6.3 Verified: Memory Absence

| Finding | Evidence |
|---------|----------|
| No persistent state between runs | `grep` for persistence mechanisms returns nothing |
| Stories stored as isolated files | Only `.md` and `_metadata.json` per story |
| No index or registry exists | `generated_stories/` is flat file directory |
| Output metadata lacks semantic keys | `tags` is always `["호러", "horror"]` |

### 6.4 NOT VERIFIED (Future Phase 2 Concerns)

| Item | Status |
|------|--------|
| Optimal number of canonical dimensions | NOT VERIFIED - requires design |
| Minimum memory size for effective de-duplication | NOT VERIFIED - requires experimentation |
| Embedding vs. structured classification effectiveness | NOT VERIFIED - requires evaluation |
| Template rotation strategy | NOT VERIFIED - requires design |

---

## 7. Appendix: Code Evidence Index

### System Prompt Location
**File:** `horror_story_generator.py`
**Lines:** 184-247
**Function:** `build_system_prompt()`

### User Prompt Location
**File:** `horror_story_generator.py`
**Lines:** 335-342
**Function:** `build_user_prompt()`

### Main Execution Path
**File:** `main.py`
**Lines:** 279 → 72 → (imports) `generate_horror_story`
**Call Chain:** `main()` → `run_basic_generation()` → `generate_horror_story()`

### Phase 1 Foundation Assets
**Location:** `phase1_foundation/`
```
00_raw_research/          # Research source material
01_knowledge_units/       # 52 KUs (UNUSED)
02_canonical_abstraction/ # Canonical system (UNUSED)
03_templates/             # 15 template skeletons (UNUSED)
```

### Generated Output Storage
**Location:** `generated_stories/`
**File Pattern:** `horror_story_YYYYMMDD_HHMMSS.md`, `..._metadata.json`
**Index:** NONE

---

## Document Integrity

This document is an **immutable snapshot** of the Phase 1 → Phase 2 boundary.

**Any modification to this document must be tracked as a separate versioned update, not an edit to this original snapshot.**

---

**Document Hash (for integrity verification):**
```
Created: 2026-01-09
Author: Claude Code (Sonnet 4.5)
Purpose: Phase 2 Design Reference
Scope: Analysis Only - No Implementation
```
