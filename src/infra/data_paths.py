"""
Data path helpers for horror-story-generator.

Phase B+: Centralized path management for all data directories.
v1.3.1: Added novel output directory, job directory, and legacy deprecation.
v1.4.0: Added story vectors directory for semantic dedup.

Directory structure:
data/
 ├── novel/                    # Story output (v1.3.1: unified output directory)
 │   └── YYYY/MM/              # Date-based subdirectories
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
 ├── story_vectors/            # Story embedding vectors (v1.4.0)
 │   ├── story.faiss           # FAISS index for stories
 │   └── metadata.json         # story_id <-> vector mapping
 └── story_registry.db         # Existing story registry

jobs/                          # Job storage (v1.3.1: centralized)

Environment Variables:
- NOVEL_OUTPUT_DIR: Override default novel output directory (default: data/novel)
- JOB_DIR: Override job storage directory (default: jobs)
- JOB_PRUNE_ENABLED: Enable job history pruning (default: false)
- JOB_PRUNE_DAYS: Days to keep job history (default: 30)
- JOB_PRUNE_MAX_COUNT: Maximum jobs to keep (default: 1000)
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Optional

logger = logging.getLogger("horror_story_generator")

# =============================================================================
# Environment Variable Configuration (v1.3.1)
# =============================================================================

def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    val = os.getenv(key, "").lower()
    if val in ("true", "1", "yes", "on"):
        return True
    elif val in ("false", "0", "no", "off"):
        return False
    return default


def _get_env_int(key: str, default: int) -> int:
    """Get integer value from environment variable."""
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            logger.warning(f"[DataPaths] Invalid integer for {key}: {val}, using default: {default}")
    return default

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
# Story Vector Paths (v1.4.0)
# =============================================================================

def get_story_vectors_dir() -> Path:
    """
    Get story vectors directory for FAISS index.

    v1.4.0: Separate vector storage for story embeddings.

    Returns:
        Path: story_vectors/ directory
    """
    return get_data_root() / "story_vectors"


def get_story_faiss_index_path() -> Path:
    """Get story FAISS index file path."""
    return get_story_vectors_dir() / "story.faiss"


def get_story_vector_metadata_path() -> Path:
    """Get story vector metadata JSON file path."""
    return get_story_vectors_dir() / "metadata.json"


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
# Novel Output Paths (v1.3.1)
# =============================================================================

def get_novel_output_dir() -> Path:
    """
    Get novel output directory.

    v1.3.1: Unified output directory for stories.
    Can be overridden via NOVEL_OUTPUT_DIR environment variable.

    Default: data/novel

    Returns:
        Path: Novel output directory
    """
    env_path = os.getenv("NOVEL_OUTPUT_DIR")
    if env_path:
        return Path(env_path).resolve()
    return get_data_root() / "novel"


def get_novel_output_subdir() -> Path:
    """
    Get date-based subdirectory for novel output.

    Returns path like: data/novel/2026/01/

    Returns:
        Path: Date-based subdirectory path
    """
    from datetime import datetime
    now = datetime.now()
    return get_novel_output_dir() / str(now.year) / f"{now.month:02d}"


# =============================================================================
# Job Storage Paths (v1.3.1)
# =============================================================================

def get_jobs_dir() -> Path:
    """
    Get jobs directory for job file storage.

    v1.3.1: Centralized job storage path.
    Can be overridden via JOB_DIR environment variable.

    Default: <project_root>/jobs

    Returns:
        Path: Jobs directory
    """
    env_path = os.getenv("JOB_DIR")
    if env_path:
        return Path(env_path).resolve()
    return get_project_root() / "jobs"


def get_logs_dir() -> Path:
    """
    Get logs directory for job execution logs.

    Returns:
        Path: Logs directory
    """
    return get_project_root() / "logs"


# =============================================================================
# Job Pruning Configuration (v1.3.1)
# =============================================================================

def get_job_prune_config() -> dict:
    """
    Get job pruning configuration from environment variables.

    v1.3.1: Optional job history cleanup.

    Environment Variables:
    - JOB_PRUNE_ENABLED: Enable pruning (default: false)
    - JOB_PRUNE_DAYS: Days to keep (default: 30)
    - JOB_PRUNE_MAX_COUNT: Max jobs to keep (default: 1000)

    Returns:
        dict: Pruning configuration
    """
    return {
        "enabled": _get_env_bool("JOB_PRUNE_ENABLED", False),
        "days": _get_env_int("JOB_PRUNE_DAYS", 30),
        "max_count": _get_env_int("JOB_PRUNE_MAX_COUNT", 1000),
    }


# =============================================================================
# Legacy Paths with Deprecation Warnings (v1.3.1)
# =============================================================================

def get_legacy_research_cards_jsonl() -> Path:
    """
    Get legacy research_cards.jsonl path.

    DEPRECATED: Use data/research/ directory structure instead.
    This function emits a deprecation warning on every call.

    Returns:
        Path: Legacy research_cards.jsonl path
    """
    warnings.warn(
        "research_cards.jsonl is deprecated. Use data/research/ directory structure. "
        "See docs/core/ARCHITECTURE.md for the new structure.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_data_root() / "research_cards.jsonl"


def get_legacy_generated_stories_dir() -> Path:
    """
    Get legacy generated_stories directory.

    DEPRECATED: Use data/novel/ directory instead.
    This function emits a deprecation warning on every call.

    Returns:
        Path: Legacy generated_stories directory
    """
    warnings.warn(
        "generated_stories/ is deprecated. Use data/novel/ directory instead. "
        "Set NOVEL_OUTPUT_DIR environment variable if needed.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_project_root() / "generated_stories"


# =============================================================================
# Directory Initialization
# =============================================================================

def ensure_data_directories() -> dict:
    """
    Ensure all required data directories exist.

    Creates directories if they don't exist.
    Safe to call multiple times.

    v1.3.1: Added novel output and jobs directories.

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
        "novel_output": get_novel_output_dir(),  # v1.3.1
        "jobs": get_jobs_dir(),  # v1.3.1
        "logs": get_logs_dir(),  # v1.3.1
        "story_vectors": get_story_vectors_dir(),  # v1.4.0
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

    v1.3.1: Added novel output, jobs, and prune config.

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
        # v1.3.1: New paths
        "novel_output": get_novel_output_dir(),
        "jobs": get_jobs_dir(),
        "logs": get_logs_dir(),
        "job_prune_config": get_job_prune_config(),
        # v1.4.0: Story vectors
        "story_vectors": {
            "root": get_story_vectors_dir(),
            "faiss_index": get_story_faiss_index_path(),
            "metadata": get_story_vector_metadata_path(),
        },
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
