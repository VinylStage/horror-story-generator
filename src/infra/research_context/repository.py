"""
Research Card Repository

Provides unified access to research cards with dedup-aware filtering.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .policy import is_usable_card, DedupLevel

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_RESEARCH_DIR = Path("./data/research")

# Quality scores considered acceptable
ACCEPTABLE_QUALITY = {"good", "partial"}


def load_all_research_cards(
    base_dir: str = "./data/research"
) -> List[Dict[str, Any]]:
    """
    Load all research cards from disk without filtering.

    Recursively scans for JSON files in YYYY/MM subdirectory structure.

    Args:
        base_dir: Base directory containing research cards

    Returns:
        List of all research card dictionaries, sorted by created_at (newest first)
    """
    base_path = Path(base_dir)

    if not base_path.exists():
        logger.debug(f"[ResearchContext] Directory not found: {base_dir}")
        return []

    cards = []
    json_files = list(base_path.glob("**/*.json"))

    # Filter out hidden files and metadata files
    json_files = [f for f in json_files if not f.name.startswith(".")]

    logger.debug(f"[ResearchContext] Scanning {len(json_files)} files in {base_dir}")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate required fields
            if "card_id" not in data:
                continue

            # Add source path for reference
            data["_source_path"] = str(json_path)
            cards.append(data)

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[ResearchContext] Failed to load {json_path.name}: {e}")
            continue

    # Sort by created_at (newest first)
    cards.sort(
        key=lambda c: c.get("metadata", {}).get("created_at", ""),
        reverse=True
    )

    return cards


def load_usable_research_cards(
    base_dir: str = "./data/research",
    exclude_level: DedupLevel = DedupLevel.HIGH
) -> List[Dict[str, Any]]:
    """
    Load research cards that are usable (not HIGH duplicates).

    This is the primary function for story generation to get research context.

    Args:
        base_dir: Base directory containing research cards
        exclude_level: Dedup level at or above which cards are excluded

    Returns:
        List of usable research cards, sorted by created_at (newest first)
    """
    all_cards = load_all_research_cards(base_dir)

    usable = [c for c in all_cards if is_usable_card(c, exclude_level)]

    logger.info(
        f"[ResearchContext] Loaded {len(usable)}/{len(all_cards)} usable cards "
        f"(excluding {exclude_level.value})"
    )

    return usable


def get_card_by_id(
    card_id: str,
    base_dir: str = "./data/research"
) -> Optional[Dict[str, Any]]:
    """
    Load a specific research card by ID.

    Args:
        card_id: Card ID (e.g., "RC-20260112-143052")
        base_dir: Base directory containing research cards

    Returns:
        Research card dictionary or None if not found
    """
    base_path = Path(base_dir)

    if not base_path.exists():
        return None

    # Card ID format: RC-YYYYMMDD-HHMMSS
    # File structure: YYYY/MM/RC-YYYYMMDD-HHMMSS.json
    parts = card_id.split("-")
    if len(parts) >= 2:
        date_str = parts[1]
        if len(date_str) >= 6:
            year = date_str[:4]
            month = date_str[4:6]
            expected_path = base_path / year / month / f"{card_id}.json"

            if expected_path.exists():
                try:
                    with open(expected_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["_source_path"] = str(expected_path)
                    return data
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"[ResearchContext] Failed to load {card_id}: {e}")

    # Fallback: search all files
    json_files = list(base_path.glob("**/*.json"))
    for json_path in json_files:
        if json_path.stem == card_id:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_source_path"] = str(json_path)
                return data
            except (json.JSONDecodeError, IOError):
                continue

    return None


def get_canonical_affinity(card: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract canonical_affinity from a research card.

    Returns a normalized structure with all dimensions.

    Args:
        card: Research card dictionary

    Returns:
        Dict with setting, primary_fear, antagonist, mechanism lists
    """
    output = card.get("output", {})
    affinity = output.get("canonical_affinity", {})

    return {
        "setting": affinity.get("setting", []) or [],
        "primary_fear": affinity.get("primary_fear", []) or [],
        "antagonist": affinity.get("antagonist", []) or [],
        "mechanism": affinity.get("mechanism", []) or [],
    }


def get_canonical_core(card: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Get the canonical_core (single-value CK) from a research card.

    Returns None if canonical_core is not present.

    Args:
        card: Research card dictionary

    Returns:
        Dict with single values for each dimension, or None
    """
    return card.get("canonical_core")


def get_card_summary(card: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract summary information from a research card.

    Args:
        card: Research card dictionary

    Returns:
        Summary dict with key fields
    """
    output = card.get("output", {})
    validation = card.get("validation", {})
    metadata = card.get("metadata", {})
    dedup = card.get("dedup", {})

    return {
        "card_id": card.get("card_id", "unknown"),
        "title": output.get("title", "Untitled"),
        "topic": card.get("input", {}).get("topic", ""),
        "quality": validation.get("quality_score", "unknown"),
        "created_at": metadata.get("created_at", ""),
        "dedup_level": dedup.get("level", "LOW"),
        "dedup_score": dedup.get("similarity_score", 0.0),
        "canonical_affinity": get_canonical_affinity(card),
        "canonical_core": get_canonical_core(card),
    }


def search_cards_by_topic(
    topic: str,
    base_dir: str = "./data/research",
    exclude_level: DedupLevel = DedupLevel.HIGH
) -> List[Dict[str, Any]]:
    """
    Search research cards by topic keyword matching.

    Performs case-insensitive substring matching on card topics and titles.

    Args:
        topic: Search topic string
        base_dir: Base directory containing research cards
        exclude_level: Dedup level at or above which cards are excluded

    Returns:
        List of matching cards, sorted by relevance (exact match first, then newest)
    """
    all_cards = load_usable_research_cards(base_dir, exclude_level)

    if not all_cards:
        return []

    topic_lower = topic.lower()
    matches = []

    for card in all_cards:
        card_topic = card.get("input", {}).get("topic", "").lower()
        card_title = card.get("output", {}).get("title", "").lower()

        # Check for match in topic or title
        if topic_lower in card_topic or topic_lower in card_title:
            # Score: exact match > partial match
            score = 0
            if card_topic == topic_lower:
                score = 100  # Exact topic match
            elif topic_lower in card_topic:
                score = 50   # Topic contains query
            elif topic_lower in card_title:
                score = 25   # Title contains query

            matches.append({"card": card, "score": score})

    # Sort by score (highest first), then by created_at (newest first)
    matches.sort(
        key=lambda x: (
            x["score"],
            x["card"].get("metadata", {}).get("created_at", "")
        ),
        reverse=True
    )

    logger.info(f"[ResearchContext] Found {len(matches)} cards matching topic: {topic}")

    return [m["card"] for m in matches]


def get_best_card_for_topic(
    topic: str,
    base_dir: str = "./data/research",
    exclude_level: DedupLevel = DedupLevel.HIGH
) -> Optional[Dict[str, Any]]:
    """
    Get the best matching research card for a topic.

    Args:
        topic: Search topic string
        base_dir: Base directory containing research cards
        exclude_level: Dedup level at or above which cards are excluded

    Returns:
        Best matching card or None if no match
    """
    matches = search_cards_by_topic(topic, base_dir, exclude_level)
    return matches[0] if matches else None
