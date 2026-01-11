"""
Seed Integration - Select and inject Story Seeds into story generation.

Phase B+: Non-blocking seed consumption for story generation.

Seeds provide:
- key_themes: Thematic elements to explore
- atmosphere_tags: Atmospheric descriptors
- suggested_hooks: Story opening hooks
- cultural_elements: Cultural/contextual elements

IMPORTANT: Seed influence is READ-ONLY - it guides but NEVER blocks generation.
"""

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from data_paths import get_seeds_root
from story_seed import StorySeed, load_seed, list_seeds
from seed_registry import get_seed_registry, SeedRegistry

logger = logging.getLogger("horror_story_generator")


@dataclass
class SeedSelection:
    """
    Result of seed selection for story generation.

    Attributes:
        seed: Selected StorySeed (None if no seed available)
        selection_reason: Human-readable selection reason
        total_available: Total seeds available
    """
    seed: Optional[StorySeed]
    selection_reason: str
    total_available: int

    @property
    def has_seed(self) -> bool:
        """Check if a seed was selected."""
        return self.seed is not None


def select_seed_for_generation(
    strategy: str = "least_used",
    registry: Optional[SeedRegistry] = None
) -> SeedSelection:
    """
    Select a Story Seed for story generation.

    Strategies:
    - "least_used": Select seed with lowest usage count (default)
    - "random": Select a random available seed
    - "newest": Select most recently created seed

    This function NEVER raises exceptions - always returns valid SeedSelection.

    Args:
        strategy: Selection strategy
        registry: Seed registry (uses global if not provided)

    Returns:
        SeedSelection with selected seed (or None if unavailable)
    """
    logger.info(f"[SeedInject] Selecting seed with strategy: {strategy}")

    if registry is None:
        try:
            registry = get_seed_registry()
        except Exception as e:
            logger.warning(f"[SeedInject] Registry unavailable: {e}")
            return SeedSelection(
                seed=None,
                selection_reason=f"Registry unavailable: {e}",
                total_available=0
            )

    # Get available seeds from registry
    try:
        available = registry.list_available()
        total = registry.count()
    except Exception as e:
        logger.warning(f"[SeedInject] Failed to list seeds: {e}")
        return SeedSelection(
            seed=None,
            selection_reason=f"Failed to list seeds: {e}",
            total_available=0
        )

    if not available:
        # Fallback: try to find seed files directly
        seed_files = list_seeds()
        if not seed_files:
            logger.info("[SeedInject] No seeds available")
            return SeedSelection(
                seed=None,
                selection_reason="No seeds available",
                total_available=0
            )

        # Load random seed file directly
        seed_path = random.choice(seed_files)
        seed = load_seed(seed_path)
        if seed:
            logger.info(f"[SeedInject] Loaded seed from file: {seed.seed_id}")
            return SeedSelection(
                seed=seed,
                selection_reason=f"Loaded from file (registry empty): {seed.seed_id}",
                total_available=len(seed_files)
            )

        return SeedSelection(
            seed=None,
            selection_reason="Failed to load seed from file",
            total_available=len(seed_files)
        )

    # Select based on strategy
    selected_record = None

    if strategy == "least_used":
        selected_record = registry.get_least_used()
    elif strategy == "random":
        selected_record = random.choice(available)
    elif strategy == "newest":
        selected_record = available[0] if available else None  # Sorted by created_at DESC
    else:
        logger.warning(f"[SeedInject] Unknown strategy '{strategy}', using least_used")
        selected_record = registry.get_least_used()

    if not selected_record:
        return SeedSelection(
            seed=None,
            selection_reason="No seed selected",
            total_available=total
        )

    # Load the seed file
    seed_path = Path(selected_record.file_path) if selected_record.file_path else None

    if seed_path and seed_path.exists():
        seed = load_seed(seed_path)
    else:
        # Try to find by seed_id in seeds directory
        seeds_dir = get_seeds_root()
        seed_path = seeds_dir / f"{selected_record.seed_id}.json"
        seed = load_seed(seed_path) if seed_path.exists() else None

    if not seed:
        logger.warning(f"[SeedInject] Seed file not found: {selected_record.seed_id}")
        return SeedSelection(
            seed=None,
            selection_reason=f"Seed file not found: {selected_record.seed_id}",
            total_available=total
        )

    logger.info(f"[SeedInject] Selected: {seed.seed_id} (used {selected_record.times_used} times)")

    return SeedSelection(
        seed=seed,
        selection_reason=f"Selected {seed.seed_id} via {strategy} strategy",
        total_available=total
    )


def get_seed_context_for_prompt(selection: SeedSelection) -> Optional[Dict[str, Any]]:
    """
    Format selected seed for prompt injection.

    Returns None if no seed is selected.

    Args:
        selection: SeedSelection result

    Returns:
        Dict with seed context for prompt, or None
    """
    if not selection.has_seed:
        return None

    seed = selection.seed

    context = {
        "seed_id": seed.seed_id,
        "source_card_id": seed.source_card_id,
        "key_themes": seed.key_themes,
        "atmosphere_tags": seed.atmosphere_tags,
        "suggested_hooks": seed.suggested_hooks,
        "cultural_elements": seed.cultural_elements,
    }

    logger.debug(f"[SeedInject] Context: {len(seed.key_themes)} themes, "
                 f"{len(seed.atmosphere_tags)} atmosphere tags")

    return context


def format_seed_for_system_prompt(context: Optional[Dict[str, Any]]) -> str:
    """
    Format seed context as a system prompt section.

    Args:
        context: Seed context from get_seed_context_for_prompt

    Returns:
        Formatted string for insertion into system prompt
    """
    if not context:
        return ""

    lines = [
        "",
        "## Story Seed (thematic inspiration)",
        "",
    ]

    themes = context.get("key_themes", [])
    if themes:
        lines.append("**Core themes to explore:**")
        for theme in themes:
            lines.append(f"- {theme}")
        lines.append("")

    atmosphere = context.get("atmosphere_tags", [])
    if atmosphere:
        lines.append("**Atmosphere:**")
        lines.append(f"{', '.join(atmosphere)}")
        lines.append("")

    hooks = context.get("suggested_hooks", [])
    if hooks:
        lines.append("**Possible story hooks:**")
        for hook in hooks:
            lines.append(f"- {hook}")
        lines.append("")

    cultural = context.get("cultural_elements", [])
    if cultural:
        lines.append("**Cultural elements:**")
        for elem in cultural:
            lines.append(f"- {elem}")
        lines.append("")

    lines.append("*These are seeds to inspire your writing. "
                 "Develop them naturally into your horror narrative.*")

    return "\n".join(lines)


def mark_seed_used(
    seed_id: str,
    registry: Optional[SeedRegistry] = None
) -> bool:
    """
    Mark a seed as used after successful story generation.

    Should be called AFTER story is saved, not before.

    Args:
        seed_id: Seed identifier
        registry: Seed registry (uses global if not provided)

    Returns:
        True if marked successfully
    """
    if registry is None:
        try:
            registry = get_seed_registry()
        except Exception:
            return False

    return registry.mark_used(seed_id)


def get_seed_injection_status() -> Dict[str, Any]:
    """
    Get status information for seed injection system.

    Returns:
        Dict with status info (seed counts, registry stats)
    """
    try:
        registry = get_seed_registry()
        stats = registry.get_stats()
        seed_files = list_seeds()

        return {
            "available": True,
            "registry_stats": stats,
            "seed_files_count": len(seed_files),
            "seeds_root": str(get_seeds_root()),
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }
