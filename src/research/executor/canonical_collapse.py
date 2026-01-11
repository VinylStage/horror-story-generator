"""
Canonical Affinity to Canonical Core Collapsing

Collapses multi-value canonical_affinity arrays to single-value canonical_core.
Based on rules from docs/technical/KU_TO_CANONICAL_KEY_RULES.md

The collapsing follows priority rules when multiple values exist:
- primary_fear: most fundamental fear wins
- setting: where climax occurs
- antagonist: primary source of horror
- mechanism: what enables persistence
- twist_family: derived from story structure if not provided
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Schema path for validation
SCHEMA_PATH = Path("schema/canonical_key.schema.json")

# Priority orderings for tie-breaking
# Lower index = higher priority (more fundamental)
PRIMARY_FEAR_PRIORITY = [
    "annihilation",
    "identity_erasure",
    "loss_of_autonomy",
    "isolation",
    "social_displacement",
    "contamination",
]

# Valid values from schema
VALID_SETTINGS = [
    "apartment", "hospital", "rural", "domestic_space",
    "digital", "liminal", "infrastructure", "body", "abstract"
]

VALID_PRIMARY_FEARS = [
    "loss_of_autonomy", "identity_erasure", "social_displacement",
    "contamination", "isolation", "annihilation"
]

VALID_ANTAGONISTS = [
    "ghost", "system", "technology", "body", "collective", "unknown"
]

VALID_MECHANISMS = [
    "surveillance", "possession", "debt", "infection",
    "impersonation", "confinement", "erosion", "exploitation"
]

VALID_TWISTS = [
    "revelation", "inevitability", "inversion",
    "circularity", "self_is_monster", "ambiguity"
]


def select_primary_fear(values: List[str]) -> Optional[str]:
    """
    Select single primary_fear from candidates using priority rules.

    Args:
        values: List of candidate primary_fear values

    Returns:
        Selected value or None if no valid candidates
    """
    valid = [v for v in values if v in VALID_PRIMARY_FEARS]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]

    # Use priority order
    for fear in PRIMARY_FEAR_PRIORITY:
        if fear in valid:
            return fear

    # Fallback to first valid
    return valid[0]


def select_single_value(values: List[str], valid_set: List[str]) -> Optional[str]:
    """
    Select single value from candidates, preferring first valid.

    Args:
        values: List of candidate values
        valid_set: List of valid enum values

    Returns:
        Selected value or None if no valid candidates
    """
    valid = [v for v in values if v in valid_set]
    if not valid:
        return None
    return valid[0]


def collapse_canonical_affinity(
    affinity: Dict[str, List[str]],
    default_twist: str = "inevitability"
) -> Dict[str, str]:
    """
    Collapse canonical_affinity (arrays) to canonical_core (single values).

    Args:
        affinity: Dict with setting, primary_fear, antagonist, mechanism lists
        default_twist: Default twist_family if not provided

    Returns:
        Dict with single values for each dimension (canonical_core)
    """
    # Extract arrays, handling various key names
    setting_values = affinity.get("setting", []) or []
    fear_values = affinity.get("primary_fear", []) or []
    antagonist_values = affinity.get("antagonist", []) or []
    mechanism_values = affinity.get("mechanism", []) or []
    twist_values = affinity.get("twist", []) or affinity.get("twist_family", []) or []

    # Collapse each dimension
    core = {}

    # Setting
    setting = select_single_value(setting_values, VALID_SETTINGS)
    core["setting_archetype"] = setting or "abstract"

    # Primary fear (uses priority rules)
    fear = select_primary_fear(fear_values)
    core["primary_fear"] = fear or "isolation"

    # Antagonist
    antagonist = select_single_value(antagonist_values, VALID_ANTAGONISTS)
    core["antagonist_archetype"] = antagonist or "unknown"

    # Mechanism
    mechanism = select_single_value(mechanism_values, VALID_MECHANISMS)
    core["threat_mechanism"] = mechanism or "erosion"

    # Twist
    twist = select_single_value(twist_values, VALID_TWISTS)
    core["twist_family"] = twist or default_twist

    logger.debug(f"[CanonicalCollapse] Collapsed to: {core}")
    return core


def validate_canonical_core(core: Dict[str, str]) -> tuple[bool, Optional[str]]:
    """
    Validate canonical_core against schema.

    Args:
        core: Canonical core dict to validate

    Returns:
        Tuple of (is_valid, error_message or None)
    """
    required_fields = [
        "setting_archetype",
        "primary_fear",
        "antagonist_archetype",
        "threat_mechanism",
        "twist_family"
    ]

    valid_values = {
        "setting_archetype": VALID_SETTINGS,
        "primary_fear": VALID_PRIMARY_FEARS,
        "antagonist_archetype": VALID_ANTAGONISTS,
        "threat_mechanism": VALID_MECHANISMS,
        "twist_family": VALID_TWISTS,
    }

    # Check required fields
    for field in required_fields:
        if field not in core:
            return False, f"Missing required field: {field}"

        value = core[field]
        if value not in valid_values[field]:
            return False, f"Invalid value for {field}: {value}"

    return True, None


def extract_canonical_core_from_card(card_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract and collapse canonical_core from a research card.

    Args:
        card_data: Full research card data

    Returns:
        Canonical core dict
    """
    output = card_data.get("output", {})
    affinity = output.get("canonical_affinity", {})

    return collapse_canonical_affinity(affinity)
