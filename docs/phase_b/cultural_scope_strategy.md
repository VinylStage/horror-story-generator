# Cultural Scope Strategy

## Overview

The horror story generator targets **Korean horror fiction** as its primary output. This document defines how cultural context influences research selection and story generation without excluding non-Korean sources.

## Core Principle: Weighting, Not Exclusion

> **Korean cultural context receives priority weighting; other cultural sources remain available.**

The system:
- **Prioritizes** Korean horror themes, settings, and cultural references
- **Weights** research cards with Korean specificity higher in selection
- **Includes** universal and cross-cultural horror concepts

The system does NOT:
- Exclude non-Korean research sources
- Block stories with non-Korean settings
- Reject research lacking Korean cultural markers

## Korean Horror Characteristics

### Setting Preferences
| Preferred | Also Valid |
|-----------|------------|
| 아파트 (apartment complex) | Generic urban housing |
| 지하철/버스 (public transit) | Any transit system |
| 편의점 (convenience store) | Any retail setting |
| 고시원/원룸 (one-room/study rooms) | Small living spaces |
| 회사/사무실 (office/workplace) | Any workplace |
| 학교 (school) | Any educational setting |

### Fear Types with Cultural Weight
| Korean-Weighted | Universal Alternative |
|-----------------|----------------------|
| 사회적 고립 (social isolation) | Isolation |
| 체면/눈치 (social pressure) | Social anxiety |
| 과로/번아웃 (overwork) | Exhaustion |
| 무연고 (no social ties) | Loneliness |
| 층간소음 (apartment noise) | Neighbor conflict |

### Antagonist Patterns
| Korean Context | Universal Mapping |
|----------------|-------------------|
| 시스템 (systemic pressure) | Bureaucracy |
| 이웃 (neighbor) | Community |
| 직장 상사 (boss/supervisor) | Authority |
| 온라인 군중 (online mob) | Digital collective |

## Research Card Weighting

### Cultural Specificity Score

```python
def cultural_weight(card):
    """
    Calculate cultural relevance weight for Korean horror.

    Returns: float between 0.5 and 2.0
    """
    specificity = card.quality.cultural_specificity

    weights = {
        "korean": 2.0,      # Strong preference
        "asian": 1.5,       # Moderate preference
        "universal": 1.0,   # Neutral
        "western": 0.8,     # Slight deprioritization
        "mixed": 1.2        # Mild preference
    }

    return weights.get(specificity, 1.0)
```

### Application in Selection

When selecting research cards for context injection:

1. All cards remain in the candidate pool
2. Korean-specific cards receive higher selection probability
3. Final selection respects canonical affinity matching

```python
# Pseudocode for weighted selection
def select_research_card(candidates, template):
    scores = []
    for card in candidates:
        base_score = canonical_affinity_match(card, template)
        cultural_weight = get_cultural_weight(card)
        scores.append(base_score * cultural_weight)

    return weighted_random_choice(candidates, scores)
```

## Template Alignment

The 15 template skeletons already emphasize Korean settings:

| Template ID | Setting | Cultural Specificity |
|-------------|---------|---------------------|
| T-APT-001 | apartment | Korean |
| T-SUB-001 | subway | Korean |
| T-OFF-001 | office | Korean |
| T-CVS-001 | convenience_store | Korean |
| T-ECO-001 | ecommerce | Universal |
| T-NET-001 | online_community | Universal |

## Non-Exclusion Guarantee

Research cards with non-Korean cultural context are:
- Stored and indexed normally
- Available for selection (with lower weight)
- Useful for universal horror concepts
- Not deleted or hidden

This ensures the system can leverage:
- Cross-cultural horror research
- Universal psychological concepts
- Comparative horror analysis
- Adaptable foreign horror tropes

## Future Considerations

### Explicit Cultural Mode (Planned)
```bash
# Force Korean-only research
python main.py --cultural-mode korean-only

# Allow all cultures equally
python main.py --cultural-mode universal

# Default: Korean-weighted
python main.py  # Uses cultural weighting
```

### Multi-Cultural Output (Future)
The current system outputs Korean-language horror stories. Future phases may support:
- English output with Korean cultural context
- Localized versions of the same story
- Cultural adaptation suggestions
