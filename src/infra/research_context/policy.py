"""
Research Dedup Policy

Defines usability rules for research cards based on dedup levels.
HIGH duplicates are excluded from "usable research" by default.
"""

from enum import Enum
from typing import Dict, Any, Optional


class DedupLevel(str, Enum):
    """
    Deduplication signal levels.

    LOW: Similarity < 0.70 - Card is unique
    MEDIUM: 0.70 <= Similarity < 0.85 - Some overlap, still usable
    HIGH: Similarity >= 0.85 - Duplicate, excluded by default
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# Threshold configuration (consistent with src/dedup/research/dedup.py)
DEDUP_THRESHOLD_MEDIUM = 0.70
DEDUP_THRESHOLD_HIGH = 0.85

# Default exclusion level
DEFAULT_EXCLUDE_LEVEL = DedupLevel.HIGH


def get_dedup_level(similarity_score: float) -> DedupLevel:
    """
    Determine dedup level from similarity score.

    Args:
        similarity_score: Cosine similarity score (0.0 to 1.0)

    Returns:
        DedupLevel enum value
    """
    if similarity_score >= DEDUP_THRESHOLD_HIGH:
        return DedupLevel.HIGH
    elif similarity_score >= DEDUP_THRESHOLD_MEDIUM:
        return DedupLevel.MEDIUM
    else:
        return DedupLevel.LOW


def is_usable_card(
    card: Dict[str, Any],
    exclude_level: DedupLevel = DEFAULT_EXCLUDE_LEVEL
) -> bool:
    """
    Check if a research card is usable based on dedup policy.

    A card is usable if:
    1. It has valid quality_score (good or partial)
    2. Its dedup level is below the exclusion threshold

    Args:
        card: Research card dictionary
        exclude_level: Level at or above which cards are excluded

    Returns:
        True if card is usable, False otherwise
    """
    # Check quality
    validation = card.get("validation", {})
    quality = validation.get("quality_score", "unknown")
    if quality not in ("good", "partial"):
        return False

    # Check dedup level
    dedup = card.get("dedup", {})
    card_level_str = dedup.get("level", "LOW")

    try:
        card_level = DedupLevel(card_level_str)
    except ValueError:
        # Unknown level, assume usable
        return True

    # Exclude HIGH (or configured level)
    if exclude_level == DedupLevel.HIGH:
        return card_level != DedupLevel.HIGH
    elif exclude_level == DedupLevel.MEDIUM:
        return card_level == DedupLevel.LOW
    else:
        # No exclusion
        return True


def get_usability_reason(card: Dict[str, Any]) -> str:
    """
    Get human-readable reason for card usability status.

    Args:
        card: Research card dictionary

    Returns:
        Reason string
    """
    validation = card.get("validation", {})
    quality = validation.get("quality_score", "unknown")

    if quality not in ("good", "partial"):
        return f"quality={quality} (requires good/partial)"

    dedup = card.get("dedup", {})
    level = dedup.get("level", "LOW")
    score = dedup.get("similarity_score", 0.0)

    if level == "HIGH":
        return f"dedup=HIGH (score={score:.2f}, excluded)"

    return f"usable (quality={quality}, dedup={level})"
