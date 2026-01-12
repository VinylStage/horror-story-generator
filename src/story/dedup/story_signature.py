"""
Story Signature Computation

Computes a deterministic, portable signature for story structural identity.
Used to detect structurally duplicated stories even with cosmetic variations.

The signature is based on:
- canonical_core (template's 5-dimensional identity)
- research_used (sorted list of research card IDs)

Properties:
- Deterministic: same inputs always produce same signature
- Machine-independent: no absolute paths or process IDs
- Order-independent for research_used (sorted before hashing)
- Stable: uses SHA256 for collision resistance
"""

import hashlib
import json
from typing import Dict, List, Optional, Any


def normalize_canonical_core(canonical_core: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Normalize canonical_core for stable signature computation.

    Handles both full field names (research cards) and short names (templates):
    - setting_archetype / setting
    - primary_fear
    - antagonist_archetype / antagonist
    - threat_mechanism / mechanism
    - twist_family / twist

    Args:
        canonical_core: Raw canonical_core dict (may have short or full names)

    Returns:
        Normalized dict with consistent key names, sorted alphabetically
    """
    if not canonical_core:
        return {}

    # Map short names to full names for consistency
    key_mapping = {
        "setting": "setting_archetype",
        "antagonist": "antagonist_archetype",
        "mechanism": "threat_mechanism",
        "twist": "twist_family",
    }

    normalized = {}
    for key, value in canonical_core.items():
        # Convert short names to full names
        normalized_key = key_mapping.get(key, key)
        normalized[normalized_key] = value

    # Return with sorted keys for determinism
    return {k: normalized[k] for k in sorted(normalized.keys())}


def compute_story_signature(
    canonical_core: Optional[Dict[str, str]],
    research_used: Optional[List[str]]
) -> str:
    """
    Compute a deterministic signature for story structural identity.

    The signature uniquely identifies a story's structural base:
    - Same canonical_core + same research_used = same signature
    - Different research_used = different signature

    This enables detection of "same base story with cosmetic changes".

    Args:
        canonical_core: The 5-dimensional canonical key (from template)
        research_used: List of research card IDs used in generation

    Returns:
        SHA256 hex digest (64 characters)

    Example:
        >>> sig = compute_story_signature(
        ...     {"setting": "apartment", "primary_fear": "isolation", ...},
        ...     ["RC-20260112-082330"]
        ... )
        >>> print(sig)
        'a1b2c3d4...'  # 64-char hex string
    """
    # 1. Normalize canonical_core
    normalized_core = normalize_canonical_core(canonical_core)

    # 2. Sort research_used for order-independence
    sorted_research = sorted(research_used) if research_used else []

    # 3. Create deterministic JSON representation
    signature_data = {
        "canonical_core": normalized_core,
        "research_used": sorted_research,
    }

    # 4. Serialize to JSON with sorted keys and no whitespace variance
    json_str = json.dumps(signature_data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

    # 5. SHA256 hash
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def compute_signature_preview(
    canonical_core: Optional[Dict[str, str]],
    research_used: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Compute signature and return intermediate data for debugging.

    Useful for understanding what goes into the signature.

    Args:
        canonical_core: The 5-dimensional canonical key
        research_used: List of research card IDs

    Returns:
        Dict with signature, normalized data, and JSON string
    """
    normalized_core = normalize_canonical_core(canonical_core)
    sorted_research = sorted(research_used) if research_used else []

    signature_data = {
        "canonical_core": normalized_core,
        "research_used": sorted_research,
    }

    json_str = json.dumps(signature_data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    signature = hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    return {
        "signature": signature,
        "signature_short": signature[:16],  # First 16 chars for display
        "normalized_core": normalized_core,
        "sorted_research": sorted_research,
        "json_input": json_str,
    }
