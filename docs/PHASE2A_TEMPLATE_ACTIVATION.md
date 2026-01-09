# Phase 2A: Template Activation

**Date:** 2026-01-09
**Status:** IMPLEMENTED
**Scope:** Stateless template selection from Phase 1 assets

---

## Summary

Phase 2A activates the 15 template skeletons created during Phase 1. Each generation now receives a randomly selected template that provides thematic direction and story structure, reducing semantic duplication through input variation.

---

## Implementation Details

### 1. Template Loading

**File:** `horror_story_generator.py`
**Function:** `load_template_skeletons()`
**Source:** `phase1_foundation/03_templates/template_skeletons_v1.json`

Loads all 15 template skeletons into memory. Returns empty list if file not found.

### 2. Template Selection

**Function:** `select_random_template()`

- **Method:** Simple random choice
- **Back-to-back prevention:** Same template will not be selected consecutively within the same process
- **State scope:** Process-scoped only (`_last_template_id` module variable)
- **Persistence:** None (resets on process restart)

### 3. Prompt Integration

**Function:** `build_system_prompt(template, skeleton)`

When a skeleton is selected, the following is appended to the base psychological horror prompt:

```
## THIS SESSION'S STORY DIRECTION (Template: {template_name})

### Thematic Framework
- Setting Type: {setting}
- Primary Fear: {primary_fear}
- Antagonist Type: {antagonist}
- Horror Mechanism: {mechanism}
- Twist Pattern: {twist}

### Narrative Arc
- **Act 1 (Setup):** {act_1}
- **Act 2 (Escalation):** {act_2}
- **Act 3 (Resolution):** {act_3}
```

### 4. Metadata Output

Each generation's metadata now includes:

```json
{
  "skeleton_template": {
    "template_id": "T-XXX-NNN",
    "template_name": "Template Name",
    "canonical_core": {
      "setting": "...",
      "primary_fear": "...",
      "antagonist": "...",
      "mechanism": "...",
      "twist": "..."
    }
  }
}
```

---

## What This Does NOT Do

| Feature | Status |
|---------|--------|
| Duplication detection | NOT IMPLEMENTED |
| Generation memory | NOT IMPLEMENTED |
| Template usage tracking | NOT IMPLEMENTED |
| Semantic comparison | NOT IMPLEMENTED |
| Knowledge Unit injection | NOT IMPLEMENTED |

These are Phase 2B+ concerns.

---

## Backward Compatibility

The existing `template_path` parameter still works:
- If `template_path` is provided → Legacy template loading (no skeleton)
- If `template_path` is None → Phase 2A skeleton selection

---

## Available Templates (15)

| ID | Name | Setting | Primary Fear |
|----|------|---------|--------------|
| T-SYS-001 | Systemic Erosion | abstract | social_displacement |
| T-DOM-001 | Domestic Confinement | domestic_space | loss_of_autonomy |
| T-MED-001 | Medical Debt Spiral | hospital | annihilation |
| T-DIG-001 | Digital Impersonation | digital | identity_erasure |
| T-DOM-002 | Smart Home Surveillance | domestic_space | loss_of_autonomy |
| T-BOD-001 | Bodily Contamination | body | contamination |
| T-MED-002 | Medical Exploitation | hospital | loss_of_autonomy |
| T-LIM-001 | Liminal Confinement | liminal | isolation |
| T-RUR-001 | Rural Historical Possession | rural | isolation |
| T-APT-001 | Apartment Social Surveillance | apartment | social_displacement |
| T-COL-001 | Collective Exploitation | abstract | identity_erasure |
| T-INF-001 | Infrastructure Isolation | infrastructure | isolation |
| T-DIG-002 | Digital Collective Infection | digital | identity_erasure |
| T-ECO-001 | Economic Annihilation | abstract | annihilation |
| T-DOM-003 | Domestic Trauma Possession | domestic_space | identity_erasure |

---

## Observability

Template selection is logged at INFO level:

```
템플릿 선택: T-DOM-001 - Domestic Confinement
Phase 2A 템플릿 사용: T-DOM-001 - Domestic Confinement
```

---

## Testing

To verify template activation:

```bash
# Run single generation and check logs
python main.py 2>&1 | grep -E "템플릿|Template"

# Check metadata for skeleton_template field
cat generated_stories/horror_story_*_metadata.json | jq '.skeleton_template'
```

---

## Next Steps (Phase 2B+)

1. Knowledge Unit injection
2. Generation index/registry
3. Semantic classification
4. Theme exclusion mechanism
