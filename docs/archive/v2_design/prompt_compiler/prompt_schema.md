# Prompt Compiler v0 - Schema & Rule Specification

**Version:** 0.1
**Status:** Design Specification
**Phase:** 2-A.2 (Assisted Manual)
**Date:** 2026-01-08

---

## 1. Purpose

The Prompt Compiler is a **template-driven prompt generation system** that transforms validated template + KU selections into a structured LLM prompt.

**Goals:**
- Enforce canonical constraints through prompt structure
- Inject knowledge units as narrative guidance
- Preserve template identity during generation
- Provide clear, unambiguous instructions to LLM

**Non-Goals (Phase 2-A):**
- Direct story generation (LLM does this)
- Prompt optimization or A/B testing
- Automatic variation generation
- Batch processing

---

## 2. Input Schema

### 2.1 Required Inputs

**`template`** (object)
```json
{
  "template_id": "T-XXX-###",
  "template_name": "Human-readable name",
  "canonical_core": {
    "setting": "canonical_value",
    "primary_fear": "canonical_value",
    "antagonist": "canonical_value",
    "mechanism": "canonical_value",
    "twist": "canonical_value"
  },
  "story_skeleton": {
    "act_1": "functional description",
    "act_2": "functional description",
    "act_3": "functional description"
  }
}
```

**`selected_kus`** (array of objects, minimum 1, maximum 5 recommended)
```json
[
  {
    "ku_id": "KU-XXX",
    "type": "horror_concept | horror_theme | social_fear",
    "core_idea": "one-sentence distilled idea",
    "usage_rules": ["explicit conditions..."],
    "avoid": ["what NOT to use this for..."],
    "sources": ["citation..."]
  }
]
```

### 2.2 Optional Inputs

**`enabled_writing_techniques`** (array of KU objects, default: `[]`)
```json
[
  {
    "ku_id": "KU-030 through KU-036 or KU-051",
    "core_idea": "writing technique description",
    "usage_rules": ["technique application rules"]
  }
]
```

**`variation_parameters`** (object, default: `{}`)
```json
{
  "tone": "dread | terror | unease | despair",
  "pacing": "slow_burn | escalating | sudden",
  "perspective": "first_person | third_limited | third_omniscient",
  "length_target": "flash | short | medium"
}
```
*Note: If empty, LLM uses default judgment within canonical constraints*

---

## 3. Output Schema

### 3.1 Compiled Prompt Structure

The output is a **single string** containing the following ordered sections:

```
[SECTION 1: ROLE & FRAMING]
[SECTION 2: CANONICAL IDENTITY LOCK]
[SECTION 3: STORY STRUCTURE GUIDANCE]
[SECTION 4: KNOWLEDGE INJECTION]
[SECTION 5: CONSTRAINTS & PROHIBITIONS]
[SECTION 6: OPTIONAL STYLE TECHNIQUES]
[SECTION 7: OUTPUT FORMAT INSTRUCTION]
```

Each section is clearly delimited and machine-parseable if needed.

### 3.2 Section Specifications

---

#### SECTION 1: ROLE & FRAMING

**Purpose:** Establish LLM role and task scope

**Template:**
```
You are a horror story writer specializing in {template_name}.

Your task is to write a complete horror short story that adheres strictly to the provided canonical constraints and knowledge foundation.

This is NOT freeform creative writing. You must respect the structural and thematic requirements defined below.
```

**Variables:**
- `{template_name}`: From `template.template_name`

---

#### SECTION 2: CANONICAL IDENTITY LOCK

**Purpose:** Enforce non-negotiable canonical constraints

**Template:**
```
## CANONICAL CONSTRAINTS (IMMUTABLE)

This story MUST maintain the following canonical identity:

**Setting Archetype:** {setting}
- {setting_constraint_text}

**Primary Fear:** {primary_fear}
- {primary_fear_constraint_text}

**Antagonist Archetype:** {antagonist}
- {antagonist_constraint_text}

**Threat Mechanism:** {mechanism}
- {mechanism_constraint_text}

**Twist Family:** {twist}
- {twist_constraint_text}

### HARD PROHIBITIONS:
{derived_prohibitions}
```

**Variables:**
- `{setting}`, `{primary_fear}`, `{antagonist}`, `{mechanism}`, `{twist}`: From `template.canonical_core`
- `{*_constraint_text}`: Derived from Constraint Text Rules (see §4)
- `{derived_prohibitions}`: Derived from Prohibition Rules (see §4)

---

#### SECTION 3: STORY STRUCTURE GUIDANCE

**Purpose:** Provide 3-act narrative skeleton

**Template:**
```
## STORY STRUCTURE

Your story must follow this three-act structure:

**Act 1 (Setup):**
{act_1_description}

**Act 2 (Development):**
{act_2_description}

**Act 3 (Resolution):**
{act_3_description}

These acts are functional guidance, not rigid scene divisions. Ensure smooth narrative flow while respecting the intent of each act.
```

**Variables:**
- `{act_1_description}`: From `template.story_skeleton.act_1`
- `{act_2_description}`: From `template.story_skeleton.act_2`
- `{act_3_description}`: From `template.story_skeleton.act_3`

---

#### SECTION 4: KNOWLEDGE INJECTION

**Purpose:** Inject KU content as narrative foundation

**Template:**
```
## KNOWLEDGE FOUNDATION

You must incorporate the following horror concepts into your narrative. These are research-grounded elements that define the story's thematic depth.

{for each KU in selected_kus:}

### Knowledge Unit {ku_index}: {ku_id}
**Core Idea:** {core_idea}

**Usage Guidance:**
{for each rule in usage_rules:}
- {rule}
{end}

**Source:** {sources[0]}

---
{end}

You are NOT required to mention these concepts explicitly by name. Instead, embody their principles in the narrative structure, character experience, and thematic development.
```

**Variables:**
- `{ku_index}`: Ordinal number (1, 2, 3...)
- `{ku_id}`, `{core_idea}`, `{usage_rules}`, `{sources}`: From each `selected_kus[i]`

**Note:** KU avoid rules are NOT included here; they go in Section 5 as prohibitions.

---

#### SECTION 5: CONSTRAINTS & PROHIBITIONS

**Purpose:** Aggregate all negative constraints

**Template:**
```
## CONSTRAINTS & PROHIBITIONS

The following narrative choices are FORBIDDEN:

### From Canonical Identity:
{canonical_prohibitions}

### From Knowledge Unit Constraints:
{for each KU in selected_kus:}
{if KU.avoid is not empty:}
**{ku_id} prohibits:**
{for each avoid_rule in KU.avoid:}
- {avoid_rule}
{end}
{end}
{end}

### General Horror Writing Prohibitions:
- Do NOT use "it was all a dream" endings
- Do NOT rely on unexplained jump scares without narrative function
- Do NOT introduce deus ex machina resolutions
- Do NOT break the established canonical identity mid-story
```

**Variables:**
- `{canonical_prohibitions}`: From Prohibition Derivation Rules (§4.2)
- `{ku_id}`, `{avoid_rule}`: From `selected_kus[i].avoid`

---

#### SECTION 6: OPTIONAL STYLE TECHNIQUES

**Purpose:** Apply writing technique KUs if enabled

**Condition:** Only included if `enabled_writing_techniques.length > 0`

**Template:**
```
## WRITING STYLE TECHNIQUES (Optional Enhancement)

Apply the following craft techniques to enhance prose quality:

{for each technique_KU in enabled_writing_techniques:}

### {technique_ku_id}: {technique_core_idea}
{for each rule in technique_usage_rules:}
- {rule}
{end}

---
{end}

NOTE: These techniques should enhance the story WITHOUT altering its canonical identity or thematic core.
```

**Variables:**
- `{technique_ku_id}`, `{technique_core_idea}`, `{technique_usage_rules}`: From `enabled_writing_techniques[i]`

**If Disabled:**
```
## WRITING STYLE TECHNIQUES

No specific style techniques requested. Use your judgment to craft effective horror prose while respecting canonical constraints.
```

---

#### SECTION 7: OUTPUT FORMAT INSTRUCTION

**Purpose:** Specify output structure

**Template:**
```
## OUTPUT FORMAT

Generate a complete horror short story in the following format:

**Format:** Markdown
**Length:** {length_instruction}
**Perspective:** {perspective_instruction}
**Structure:** Continuous prose narrative (not outline or bullet points)

**Required Elements:**
- Title that reflects the canonical identity
- Clear beginning, middle, and end
- Adherence to all canonical constraints above
- Integration of all provided knowledge units

**Prohibited Elements:**
- Meta-commentary about the writing process
- Explanations of horror theory or canonical dimensions
- Self-referential breaks of immersion
- Genre labels or category tags within the story

Begin writing now. Output only the story itself.
```

**Variables:**
- `{length_instruction}`: Derived from `variation_parameters.length_target` or default "500-1500 words (short story)"
- `{perspective_instruction}`: Derived from `variation_parameters.perspective` or default "your choice"

---

## 4. Canonical Enforcement Rules

### 4.1 Constraint Text Derivation

For each canonical dimension, generate constraint text:

#### Setting Archetype

| Value | Constraint Text |
|-------|----------------|
| `apartment` | The story MUST take place in a multi-unit residential building. Focus on shared walls, proximity anxiety, and class tensions. |
| `hospital` | The story MUST be set in a medical facility. Emphasize institutional control, bodily vulnerability, and life/death power. |
| `rural` | The story MUST occur in an isolated countryside or village. Use geographic isolation, tradition vs. modernity, and historical weight. |
| `domestic_space` | The story MUST center on a home environment (house, apartment unit interior). Emphasize the betrayal of sanctuary. |
| `digital` | The story MUST take place in or be driven by digital/online spaces. Focus on virtuality, identity fluidity, and mediated reality. |
| `liminal` | The story MUST use transitional, purpose-free spaces (hallways, waiting rooms, parking structures). Emphasize emptiness and disorientation. |
| `infrastructure` | The story MUST involve social infrastructure systems (power, water, roads, communications). Show systemic failure and dependency. |
| `body` | The story MUST use the human body itself as the primary space of horror. Internal landscapes, boundaries violated from within. |
| `abstract` | The story's setting is conceptual rather than physical. Prioritize psychological space over geographic location. |

#### Primary Fear

| Value | Constraint Text |
|-------|----------------|
| `loss_of_autonomy` | The story MUST center on the protagonist losing control over their own body, actions, or decisions. This is non-negotiable. |
| `identity_erasure` | The story MUST focus on the protagonist's sense of self being destroyed, replaced, or rendered meaningless. |
| `social_displacement` | The story MUST depict the protagonist being pushed out of their social position, community, or place in society. |
| `contamination` | The story MUST revolve around pollution, corruption, or violation of boundaries (bodily, spatial, moral). |
| `isolation` | The story MUST place the protagonist in complete separation from others—physically, socially, or existentially. |
| `annihilation` | The story MUST confront total destruction—of self, life, or existence itself. |

#### Antagonist Archetype

| Value | Constraint Text |
|-------|----------------|
| `ghost` | The antagonist MUST be a supernatural entity (spirit, revenant, or otherworldly presence). |
| `system` | The antagonist MUST be an institutional, organizational, or structural force (not an individual villain). |
| `technology` | The antagonist MUST be technological (AI, machines, digital systems, or tech-mediated threats). |
| `body` | The antagonist MUST emerge from within the body (disease, mutation, parasite, or bodily rebellion). |
| `collective` | The antagonist MUST be a group, crowd, community, or collective consciousness. |
| `unknown` | The antagonist's nature MUST remain fundamentally unknowable. Do not reveal or explain its essence. |

#### Threat Mechanism

| Value | Constraint Text |
|-------|----------------|
| `surveillance` | The horror operates through watching, recording, or exposing the protagonist. |
| `possession` | The horror operates through invasion, control, or inhabitation of the protagonist. |
| `debt` | The horror operates through obligation, financial entrapment, or contractual binding. |
| `infection` | The horror operates through contagion, spread, or transmission. |
| `impersonation` | The horror operates through replacement, mimicry, or identity theft. |
| `confinement` | The horror operates through trapping, imprisonment, or restriction of movement. |
| `erosion` | The horror operates through gradual degradation, slow collapse, or incremental loss. |
| `exploitation` | The horror operates through extraction, abuse, or parasitic consumption. |

#### Twist Family

| Value | Constraint Text |
|-------|----------------|
| `revelation` | The ending MUST reveal a hidden truth that recontextualizes the story. |
| `inevitability` | The ending MUST show that escape was never possible—the outcome was predetermined. |
| `inversion` | The ending MUST reverse a core assumption (safety becomes danger, helper becomes threat, etc.). |
| `circularity` | The ending MUST loop back to the beginning, showing the cycle continuing or restarting. |
| `self_is_monster` | The ending MUST reveal the protagonist as the source of horror. |
| `ambiguity` | The ending MUST resist clean interpretation—leave fundamental questions unresolved. |

---

### 4.2 Prohibition Derivation Rules

From `canonical_core`, generate specific prohibitions:

**Primary Fear Prohibitions:**

If `primary_fear = "identity_erasure"`:
```
- DO NOT focus primarily on physical death or bodily harm
- DO NOT make the core conflict about social exclusion or displacement
- The protagonist MUST experience identity threat as the central horror
```

If `primary_fear = "loss_of_autonomy"`:
```
- DO NOT make death the primary fear
- DO NOT center the story on identity confusion
- The protagonist MUST lose control as the central horror
```

If `primary_fear = "social_displacement"`:
```
- DO NOT focus on individual identity erasure
- DO NOT make isolation the core fear (unless isolation = displacement)
- The protagonist MUST be pushed out of social structures
```

*(Generate similar rules for all 6 primary_fear values)*

**Antagonist Prohibitions:**

If `antagonist = "technology"`:
```
- DO NOT use supernatural explanations for technological failures
- DO NOT anthropomorphize technology as conscious evil
- Technology remains mechanistic, algorithmic, or systematically indifferent
```

If `antagonist = "ghost"`:
```
- DO NOT explain the ghost scientifically or technologically
- DO NOT reduce the ghost to psychological projection unless that IS the twist
- Maintain supernatural framing
```

*(Generate similar rules for all 6 antagonist values)*

**Setting Prohibitions:**

If `setting = "digital"`:
```
- DO NOT place the horror exclusively in physical spaces
- DO NOT ignore the digital/online dimension
- Virtual/mediated reality must be central
```

If `setting = "rural"`:
```
- DO NOT set the story in cities or suburbs
- DO NOT use high-tech solutions as resolutions
- Geographic isolation must be meaningful
```

*(Generate similar rules for all 9 setting values)*

---

### 4.3 Prohibition Aggregation

Combine:
1. Canonical prohibitions (from §4.2)
2. KU avoid rules (from `selected_kus[].avoid`)
3. General horror prohibitions (hardcoded)

De-duplicate and present in order of:
- Canonical prohibitions first (highest priority)
- KU-specific prohibitions second
- General prohibitions last

---

## 5. Writing Technique Handling

### 5.1 Inclusion Logic

**Default State:** Writing techniques DISABLED

**Enabled When:**
- User explicitly provides `enabled_writing_techniques` array with KU IDs from:
  - KU-030 (Sensory Language)
  - KU-031 (Cliché Subversion)
  - KU-032 (Plot Structure)
  - KU-033 (Fear Framework)
  - KU-034 (Atmospheric Building)
  - KU-035 (Horror Vocabulary)
  - KU-036 (Multi-sensory Description)
  - KU-051 (Ambiguous Endings)

### 5.2 Application Rules

**Constraint:**
- Writing techniques MUST NOT alter canonical identity
- If conflict arises between technique and canonical constraint, canonical wins
- Techniques are STYLE-LEVEL, not STRUCTURE-LEVEL

**Example Conflict Resolution:**
- KU-051 (Ambiguous Endings) enabled
- Template twist_family = `"revelation"` (requires clear truth reveal)
- **Resolution:** LLM uses ambiguous *prose style* around the revelation, but the truth itself must still be revealed (canonical wins)

### 5.3 Section Template (if enabled)

```
## WRITING STYLE TECHNIQUES

The following techniques enhance prose quality without changing story structure:

### KU-030: Sensory Language
- Use concrete sensory details over abstract fear words
- Engage sight, sound, smell, touch, taste
- Example: "metallic smell of blood" not "scary scene"

### KU-034: Atmospheric Building
- Establish dread through environment before explicit threat
- Use weather, lighting, sound design descriptively
- Build anticipatory fear

[Additional techniques as provided...]

Apply these as prose-level enhancements. If they conflict with canonical constraints, prioritize canonical identity.
```

---

## 6. What the Prompt Compiler Does NOT Do

### 6.1 Not Responsible For:

1. **Story Generation**
   - The LLM generates the story, not the Prompt Compiler
   - Prompt Compiler only creates instructions

2. **KU Selection**
   - KU Selector handles compatibility checks
   - Prompt Compiler receives pre-validated KUs

3. **Template Selection**
   - User or Rule Engine selects template
   - Prompt Compiler receives template as input

4. **Variation Generation**
   - Prompt Compiler does not create multiple prompts
   - Variation is handled by changing inputs, not by compiler logic

5. **Output Validation**
   - Prompt Compiler does not check if LLM followed instructions
   - Output Validator (future component) handles this

6. **Prompt Optimization**
   - No A/B testing of prompt phrasing
   - No LLM-specific tuning (model-agnostic prompts)

### 6.2 LLM Responsibilities (Not System):

- Actual narrative prose writing
- Character development
- Scene construction
- Dialogue (if any)
- Pacing within canonical constraints
- Stylistic voice
- Metaphor and imagery selection
- Plot detail resolution

**Division of Labor:**
- Prompt Compiler: **WHAT** must be in the story (constraints)
- LLM: **HOW** to write the story (execution)

---

## 7. Worked Example: T-DIG-001 + KU-018 + KU-043

### 7.1 Input Data

**Template:**
```json
{
  "template_id": "T-DIG-001",
  "template_name": "Digital Impersonation",
  "canonical_core": {
    "setting": "digital",
    "primary_fear": "identity_erasure",
    "antagonist": "technology",
    "mechanism": "impersonation",
    "twist": "self_is_monster"
  },
  "story_skeleton": {
    "act_1": "Protagonist identity functions normally within digital authentication systems",
    "act_2": "Technological duplicate operates autonomously, authentic self becomes indistinguishable from copy",
    "act_3": "Protagonist cannot prove authenticity, self becomes the false copy in social perception"
  }
}
```

**Selected KUs:**
```json
[
  {
    "ku_id": "KU-018",
    "type": "social_fear",
    "core_idea": "Deepfakes enable identity theft at scale, making voice and face unreliable for trust, exemplified by $25M fraud case.",
    "usage_rules": [
      "Use when depicting AI-powered identity fraud",
      "Apply to scenarios where visual/audio evidence becomes unreliable",
      "Foundation for digital doppelganger horror",
      "Use to explore crisis of authentication in digital age"
    ],
    "avoid": [
      "Do not treat as distant future tech—it is current reality",
      "Avoid focusing on tech details over human impact",
      "Not suitable for low-tech or historical settings"
    ],
    "sources": ["Cybercrime: Lessons learned from a $25m deepfake attack"]
  },
  {
    "ku_id": "KU-043",
    "type": "social_fear",
    "core_idea": "Technology destroys epistemic trust: when voice/face cannot authenticate identity, social bonds and institutional authority collapse.",
    "usage_rules": [
      "Use when depicting crisis of authentication",
      "Apply to narratives about trust breakdown in digital age",
      "Foundation for post-truth horror",
      "Use to explore what happens when evidence becomes unreliable"
    ],
    "avoid": [
      "Do not focus on technology over human impact",
      "Avoid treating as solvable through technical means alone",
      "Not suitable for low-tech settings"
    ],
    "sources": ["Cybercrime: Lessons learned from a $25m deepfake attack"]
  }
]
```

**Optional Inputs:**
```json
{
  "enabled_writing_techniques": [],
  "variation_parameters": {}
}
```

---

### 7.2 Compiled Prompt Output

```
You are a horror story writer specializing in Digital Impersonation.

Your task is to write a complete horror short story that adheres strictly to the provided canonical constraints and knowledge foundation.

This is NOT freeform creative writing. You must respect the structural and thematic requirements defined below.

---

## CANONICAL CONSTRAINTS (IMMUTABLE)

This story MUST maintain the following canonical identity:

**Setting Archetype:** digital
- The story MUST take place in or be driven by digital/online spaces. Focus on virtuality, identity fluidity, and mediated reality.

**Primary Fear:** identity_erasure
- The story MUST focus on the protagonist's sense of self being destroyed, replaced, or rendered meaningless.

**Antagonist Archetype:** technology
- The antagonist MUST be technological (AI, machines, digital systems, or tech-mediated threats).

**Threat Mechanism:** impersonation
- The horror operates through replacement, mimicry, or identity theft.

**Twist Family:** self_is_monster
- The ending MUST reveal the protagonist as the source of horror.

### HARD PROHIBITIONS:
- DO NOT focus primarily on physical death or bodily harm
- DO NOT make the core conflict about social exclusion or displacement
- The protagonist MUST experience identity threat as the central horror
- DO NOT use supernatural explanations for technological failures
- DO NOT anthropomorphize technology as conscious evil
- Technology remains mechanistic, algorithmic, or systematically indifferent
- DO NOT place the horror exclusively in physical spaces
- DO NOT ignore the digital/online dimension
- Virtual/mediated reality must be central

---

## STORY STRUCTURE

Your story must follow this three-act structure:

**Act 1 (Setup):**
Protagonist identity functions normally within digital authentication systems

**Act 2 (Development):**
Technological duplicate operates autonomously, authentic self becomes indistinguishable from copy

**Act 3 (Resolution):**
Protagonist cannot prove authenticity, self becomes the false copy in social perception

These acts are functional guidance, not rigid scene divisions. Ensure smooth narrative flow while respecting the intent of each act.

---

## KNOWLEDGE FOUNDATION

You must incorporate the following horror concepts into your narrative. These are research-grounded elements that define the story's thematic depth.

### Knowledge Unit 1: KU-018
**Core Idea:** Deepfakes enable identity theft at scale, making voice and face unreliable for trust, exemplified by $25M fraud case.

**Usage Guidance:**
- Use when depicting AI-powered identity fraud
- Apply to scenarios where visual/audio evidence becomes unreliable
- Foundation for digital doppelganger horror
- Use to explore crisis of authentication in digital age

**Source:** Cybercrime: Lessons learned from a $25m deepfake attack

---

### Knowledge Unit 2: KU-043
**Core Idea:** Technology destroys epistemic trust: when voice/face cannot authenticate identity, social bonds and institutional authority collapse.

**Usage Guidance:**
- Use when depicting crisis of authentication
- Apply to narratives about trust breakdown in digital age
- Foundation for post-truth horror
- Use to explore what happens when evidence becomes unreliable

**Source:** Cybercrime: Lessons learned from a $25m deepfake attack

---

You are NOT required to mention these concepts explicitly by name. Instead, embody their principles in the narrative structure, character experience, and thematic development.

---

## CONSTRAINTS & PROHIBITIONS

The following narrative choices are FORBIDDEN:

### From Canonical Identity:
- DO NOT focus primarily on physical death or bodily harm
- DO NOT make the core conflict about social exclusion or displacement
- The protagonist MUST experience identity threat as the central horror
- DO NOT use supernatural explanations for technological failures
- DO NOT anthropomorphize technology as conscious evil
- DO NOT place the horror exclusively in physical spaces
- DO NOT ignore the digital/online dimension

### From Knowledge Unit Constraints:

**KU-018 prohibits:**
- Do not treat as distant future tech—it is current reality
- Avoid focusing on tech details over human impact
- Not suitable for low-tech or historical settings

**KU-043 prohibits:**
- Do not focus on technology over human impact
- Avoid treating as solvable through technical means alone
- Not suitable for low-tech settings

### General Horror Writing Prohibitions:
- Do NOT use "it was all a dream" endings
- Do NOT rely on unexplained jump scares without narrative function
- Do NOT introduce deus ex machina resolutions
- Do NOT break the established canonical identity mid-story

---

## WRITING STYLE TECHNIQUES

No specific style techniques requested. Use your judgment to craft effective horror prose while respecting canonical constraints.

---

## OUTPUT FORMAT

Generate a complete horror short story in the following format:

**Format:** Markdown
**Length:** 500-1500 words (short story)
**Perspective:** your choice
**Structure:** Continuous prose narrative (not outline or bullet points)

**Required Elements:**
- Title that reflects the canonical identity
- Clear beginning, middle, and end
- Adherence to all canonical constraints above
- Integration of all provided knowledge units

**Prohibited Elements:**
- Meta-commentary about the writing process
- Explanations of horror theory or canonical dimensions
- Self-referential breaks of immersion
- Genre labels or category tags within the story

Begin writing now. Output only the story itself.
```

---

## 8. Implementation Guidance

### 8.1 Processing Order

1. Load template data
2. Load selected KUs data
3. Generate canonical constraint text (§4.1)
4. Derive canonical prohibitions (§4.2)
5. Extract KU avoid rules
6. Aggregate all prohibitions (§4.3)
7. Check if writing techniques enabled
8. Assemble prompt sections in order (§3.2)
9. Return single string output

### 8.2 String Assembly

**Recommended Approach:**
- Use template literals or string builder
- Include newlines and markdown formatting
- Ensure section delimiters are clear (e.g., `---`)
- Validate output is valid markdown

**Section Separator:**
```
---
```
(Three hyphens create horizontal rule in markdown)

### 8.3 Variable Substitution

**Safe Substitution:**
- All template variables must be sanitized
- No user-provided raw strings in canonical sections
- KU text is trusted (Phase 1 immutable)
- Variation parameters are enum-validated

**Escaping:**
- No markdown escaping needed (text is already clean)
- No HTML injection risk (output is markdown, not rendered)

### 8.4 Error Handling

**Missing Required Data:**
- If `template` missing: Throw error "Template required"
- If `selected_kus` empty: Throw error "At least 1 KU required"
- If `canonical_core` incomplete: Throw error "Invalid template canonical_core"

**Invalid Optional Data:**
- If `enabled_writing_techniques` contains non-technique KU: Warn and filter out
- If `variation_parameters` contains invalid enum: Ignore and use default

**Malformed KU Data:**
- If KU missing `core_idea`: Skip KU with warning
- If KU missing `usage_rules`: Use empty array
- If KU missing `avoid`: Use empty array

---

## 9. Validation Checklist

Before implementation, verify:

- [ ] All 7 prompt sections are present in output
- [ ] Canonical constraint text covers all 5 dimensions
- [ ] Prohibition derivation rules are exhaustive (all 6 fears, 6 antagonists, 9 settings)
- [ ] KU injection preserves all usage_rules
- [ ] KU avoid rules are correctly placed in Section 5
- [ ] Writing techniques are optional and clearly marked
- [ ] Output format instruction is explicit
- [ ] Worked example produces expected prompt structure
- [ ] No executable code in specification
- [ ] No modifications to Phase 1 data

---

## 10. Future Extensions (Phase 2-B+)

**Not Implemented in v0:**
- Multi-language prompt generation
- LLM-specific prompt optimization (GPT vs Claude vs etc)
- Prompt versioning and A/B testing
- Dynamic variation parameter expansion
- Prompt length optimization

**Defer to Phase 3:**
- Automatic prompt refinement based on output quality
- Feedback loop integration
- Batch prompt generation

---

## 11. Document Maintenance

**Version History:**
- v0.1 (2026-01-08): Initial specification for Phase 2-A.2

**Review Schedule:**
- After first 10 story generations: Review canonical enforcement effectiveness
- After first 50 story generations: Review prohibition clarity
- Quarterly: Review constraint text accuracy

**Change Process:**
- Changes to canonical constraint text require specification update first
- New prohibition rules require documentation here
- Implementation must match specification exactly

---

## 12. References

- Phase 1 Foundation: `phase1_foundation/`
- Canonical Enum: `docs/canonical_enum.md`
- KU Selector Spec: `phase2_execution/ku_selector/ku_selector_spec.md`
- Decision Log: `docs/decision_log.md` (D-004: Writing Techniques)

---

**END OF SPECIFICATION**

Next Step: Implement Prompt Compiler according to this specification.
