"""
Data path helpers for horror-story-generator.

Phase B+: Centralized path management for all data directories.
Ensures portable directory structure without hardcoded absolute paths.

Directory structure:
data/
 ├── research/
 │   ├── cards/                # RC-*.json / md (research cards)
 │   │   └── YYYY/MM/          # Date-based subdirectories (existing format)
 │   ├── vectors/
 │   │   ├── research.faiss    # FAISS index
 │   │   └── metadata.json     # card_id <-> vector mapping
 │   ├── logs/                 # Research execution logs
 │   └── registry.sqlite       # Research registry
 ├── seeds/
 │   ├── SS-*.json             # Story Seeds
 │   └── seed_registry.sqlite
 └── story_registry.db         # Existing story registry
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("horror_story_generator")

# =============================================================================
# Base Paths (relative to project root)
# =============================================================================

def get_project_root() -> Path:
    """
    Get the project root directory.

    Uses the location of this file as reference.
    File is now at src/infra/data_paths.py, so project root is 2 levels up.

    Returns:
        Path: Project root directory
    """
    return Path(__file__).parent.parent.parent.resolve()


def get_data_root() -> Path:
    """
    Get the data root directory.

    Returns:
        Path: data/ directory path
    """
    return get_project_root() / "data"


# =============================================================================
# Research Paths
# =============================================================================

def get_research_root() -> Path:
    """Get research data root directory."""
    return get_data_root() / "research"


def get_research_cards_dir() -> Path:
    """
    Get research cards directory.

    Note: Cards are stored in date-based subdirectories (YYYY/MM/).
    This returns the base cards directory.

    Returns:
        Path: research/cards/ directory
    """
    return get_research_root() / "cards"


def get_research_vectors_dir() -> Path:
    """Get research vectors directory for FAISS index."""
    return get_research_root() / "vectors"


def get_research_logs_dir() -> Path:
    """Get research logs directory."""
    return get_research_root() / "logs"


def get_research_registry_path() -> Path:
    """Get research registry SQLite database path."""
    return get_research_root() / "registry.sqlite"


def get_faiss_index_path() -> Path:
    """Get FAISS index file path."""
    return get_research_vectors_dir() / "research.faiss"


def get_vector_metadata_path() -> Path:
    """Get vector metadata JSON file path."""
    return get_research_vectors_dir() / "metadata.json"


# =============================================================================
# Legacy Research Paths (backward compatibility)
# =============================================================================

def get_legacy_research_dir() -> Path:
    """
    Get legacy research directory (pre-Phase B+ structure).

    Legacy cards are stored directly in research/YYYY/MM/ without cards/ prefix.
    This function helps migrate and find existing cards.

    Returns:
        Path: Legacy research directory
    """
    return get_research_root()


def find_all_research_cards(include_legacy: bool = True) -> list:
    """
    Find all research card JSON files.

    Args:
        include_legacy: Include cards from legacy location

    Returns:
        List of Path objects to research card JSON files
    """
    cards = []

    # New location: data/research/cards/
    cards_dir = get_research_cards_dir()
    if cards_dir.exists():
        cards.extend(cards_dir.rglob("RC-*.json"))

    # Legacy location: data/research/YYYY/MM/
    if include_legacy:
        legacy_dir = get_legacy_research_dir()
        if legacy_dir.exists():
            for json_file in legacy_dir.rglob("RC-*.json"):
                # Exclude files already in cards/ subdirectory
                if "cards" not in json_file.parts:
                    cards.append(json_file)

    # Remove duplicates and sort by modification time (newest first)
    unique_cards = list(set(cards))
    unique_cards.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    return unique_cards


# =============================================================================
# Seeds Paths
# =============================================================================

def get_seeds_root() -> Path:
    """Get story seeds root directory."""
    return get_data_root() / "seeds"


def get_seed_registry_path() -> Path:
    """Get seed registry SQLite database path."""
    return get_seeds_root() / "seed_registry.sqlite"


# =============================================================================
# Story Registry Path
# =============================================================================

def get_story_registry_path() -> Path:
    """Get story registry SQLite database path (existing)."""
    return get_data_root() / "story_registry.db"


# =============================================================================
# Directory Initialization
# =============================================================================

def ensure_data_directories() -> dict:
    """
    Ensure all required data directories exist.

    Creates directories if they don't exist.
    Safe to call multiple times.

    Returns:
        dict: Dictionary of created/existing directory paths
    """
    directories = {
        "data_root": get_data_root(),
        "research_root": get_research_root(),
        "research_cards": get_research_cards_dir(),
        "research_vectors": get_research_vectors_dir(),
        "research_logs": get_research_logs_dir(),
        "seeds": get_seeds_root(),
    }

    created = []
    for name, path in directories.items():
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(name)
            logger.debug(f"[DataPaths] Created directory: {path}")

    if created:
        logger.info(f"[DataPaths] Initialized directories: {', '.join(created)}")

    return directories


def get_all_paths() -> dict:
    """
    Get all data paths as a dictionary.

    Useful for debugging and configuration display.

    Returns:
        dict: All path configurations
    """
    return {
        "project_root": get_project_root(),
        "data_root": get_data_root(),
        "research": {
            "root": get_research_root(),
            "cards": get_research_cards_dir(),
            "vectors": get_research_vectors_dir(),
            "logs": get_research_logs_dir(),
            "registry": get_research_registry_path(),
            "faiss_index": get_faiss_index_path(),
            "vector_metadata": get_vector_metadata_path(),
        },
        "seeds": {
            "root": get_seeds_root(),
            "registry": get_seed_registry_path(),
        },
        "story_registry": get_story_registry_path(),
    }


# =============================================================================
# Module Initialization
# =============================================================================

# Ensure directories exist on module import
_initialized = False

def initialize():
    """Initialize data directories. Safe to call multiple times."""
    global _initialized
    if not _initialized:
        ensure_data_directories()
        _initialized = True


# Auto-initialize when module is imported
initialize()
