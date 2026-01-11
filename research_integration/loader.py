"""
Research Card Loader

Scans and loads research cards from the data/research directory.
Cards are loaded from JSON files with quality filtering.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Default path for research cards
DEFAULT_RESEARCH_DIR = Path("./data/research")

# Quality score filter - only load cards with acceptable quality
ACCEPTABLE_QUALITY_SCORES = {"good", "partial"}


def load_research_cards(
    base_dir: str = "./data/research",
    quality_filter: bool = True,
    min_quality: str = "partial"
) -> List[Dict[str, Any]]:
    """
    Load all research cards from the specified directory.

    Recursively scans for JSON files in the YYYY/MM subdirectory structure.
    Filters by quality score unless disabled.

    Args:
        base_dir: Base directory containing research cards
        quality_filter: If True, filter by quality_score
        min_quality: Minimum quality level ("good" or "partial")
            - "good": Only fully complete cards
            - "partial": Include partial cards

    Returns:
        List of research card dictionaries, sorted by created_at (newest first)
    """
    base_path = Path(base_dir)

    if not base_path.exists():
        logger.debug(f"[ResearchInject] Research directory not found: {base_dir}")
        return []

    cards = []
    json_files = list(base_path.glob("**/*.json"))

    # Filter out hidden files and metadata files
    json_files = [f for f in json_files if not f.name.startswith(".")]

    logger.info(f"[ResearchInject] Scanning {len(json_files)} files in {base_dir}")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate required fields
            if "card_id" not in data:
                logger.debug(f"[ResearchInject] Skipping {json_path.name}: no card_id")
                continue

            # Quality filter
            if quality_filter:
                quality = data.get("validation", {}).get("quality_score", "unknown")
                if min_quality == "good" and quality != "good":
                    logger.debug(f"[ResearchInject] Skipping {data['card_id']}: quality={quality}")
                    continue
                elif min_quality == "partial" and quality not in ACCEPTABLE_QUALITY_SCORES:
                    logger.debug(f"[ResearchInject] Skipping {data['card_id']}: quality={quality}")
                    continue

            # Add source path for reference
            data["_source_path"] = str(json_path)
            cards.append(data)

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[ResearchInject] Failed to load {json_path.name}: {e}")
            continue

    # Sort by created_at (newest first)
    cards.sort(
        key=lambda c: c.get("metadata", {}).get("created_at", ""),
        reverse=True
    )

    logger.info(f"[ResearchInject] Loaded {len(cards)} research cards")
    return cards


def get_card_by_id(
    card_id: str,
    base_dir: str = "./data/research"
) -> Optional[Dict[str, Any]]:
    """
    Load a specific research card by ID.

    Args:
        card_id: Card ID (e.g., "RC-20260111-143052")
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
                    logger.warning(f"[ResearchInject] Failed to load {card_id}: {e}")

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


def get_card_summary(card: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract summary information from a research card.

    Provides a lightweight view for selection and logging.

    Args:
        card: Research card dictionary

    Returns:
        Summary dict with key fields
    """
    output = card.get("output", {})
    validation = card.get("validation", {})
    metadata = card.get("metadata", {})

    return {
        "card_id": card.get("card_id", "unknown"),
        "title": output.get("title", "Untitled"),
        "topic": card.get("input", {}).get("topic", ""),
        "quality": validation.get("quality_score", "unknown"),
        "created_at": metadata.get("created_at", ""),
        "canonical_affinity": get_canonical_affinity(card),
    }
