"""
Story Deduplication Check

Provides the enforcement logic for story-level deduplication.
Checks if a story signature already exists in the registry.

Configuration:
- ENABLE_STORY_DEDUP: Enable/disable signature-based dedup (default: true)
- STORY_DEDUP_STRICT: If true, abort generation on duplicate (default: false)
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .story_signature import compute_story_signature, normalize_canonical_core

logger = logging.getLogger(__name__)

# Configuration from environment
ENABLE_STORY_DEDUP = os.getenv("ENABLE_STORY_DEDUP", "true").lower() == "true"
STORY_DEDUP_STRICT = os.getenv("STORY_DEDUP_STRICT", "false").lower() == "true"


@dataclass
class StoryDedupResult:
    """
    Result of story deduplication check.

    Attributes:
        signature: The computed story signature
        is_duplicate: Whether a duplicate was found
        existing_story_id: ID of existing duplicate (if found)
        existing_created_at: When the duplicate was created
        reason: Human-readable explanation
        action: What action was taken (warn/abort/none)
    """
    signature: str
    is_duplicate: bool = False
    existing_story_id: Optional[str] = None
    existing_created_at: Optional[str] = None
    reason: str = "unique"
    action: str = "none"  # "none", "warn", "abort"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        return {
            "story_signature": self.signature,
            "story_dedup_result": "duplicate" if self.is_duplicate else "unique",
            "story_dedup_reason": self.reason,
            "story_dedup_action": self.action,
            "story_dedup_existing_id": self.existing_story_id,
        }


def check_story_duplicate(
    canonical_core: Optional[Dict[str, str]],
    research_used: Optional[List[str]],
    registry: Any = None,  # StoryRegistry instance
    strict: Optional[bool] = None,
) -> StoryDedupResult:
    """
    Check if a story with the same signature already exists.

    This function:
    1. Computes the story signature from canonical_core + research_used
    2. Queries the registry for existing stories with same signature
    3. Returns result indicating whether duplicate was found

    Args:
        canonical_core: Template's canonical_core (5 dimensions)
        research_used: List of research card IDs
        registry: StoryRegistry instance (optional, for lookup)
        strict: Override STORY_DEDUP_STRICT env var

    Returns:
        StoryDedupResult with signature and duplicate status

    Raises:
        ValueError: If strict=True and duplicate found
    """
    # Compute signature
    signature = compute_story_signature(canonical_core, research_used)

    result = StoryDedupResult(signature=signature)

    # Check if dedup is enabled
    if not ENABLE_STORY_DEDUP:
        result.reason = "dedup_disabled"
        logger.debug(f"[StoryDedup] Dedup disabled, signature={signature[:16]}...")
        return result

    # If no registry provided, we can't check
    if registry is None:
        result.reason = "no_registry"
        logger.debug(f"[StoryDedup] No registry, signature={signature[:16]}...")
        return result

    # Query registry for existing story with same signature
    existing = registry.find_by_signature(signature)

    if existing:
        result.is_duplicate = True
        result.existing_story_id = existing.get("id")
        result.existing_created_at = existing.get("created_at")
        result.reason = f"duplicate_of_{result.existing_story_id}"

        # Determine action based on strict mode
        use_strict = strict if strict is not None else STORY_DEDUP_STRICT

        if use_strict:
            result.action = "abort"
            logger.warning(
                f"[StoryDedup] DUPLICATE DETECTED (STRICT MODE) - "
                f"signature={signature[:16]}..., existing={result.existing_story_id}"
            )
            raise ValueError(
                f"Story signature duplicate detected: {result.existing_story_id}. "
                f"STORY_DEDUP_STRICT=true prevents generation."
            )
        else:
            result.action = "warn"
            logger.warning(
                f"[StoryDedup] DUPLICATE DETECTED (WARN) - "
                f"signature={signature[:16]}..., existing={result.existing_story_id}"
            )
    else:
        result.reason = "unique"
        result.action = "none"
        logger.info(f"[StoryDedup] Signature unique: {signature[:16]}...")

    return result


def log_dedup_decision(
    result: StoryDedupResult,
    template_id: Optional[str] = None,
    research_count: int = 0
) -> None:
    """
    Log the dedup decision for observability.

    Args:
        result: The StoryDedupResult
        template_id: Template ID being used
        research_count: Number of research cards used
    """
    status = "DUPLICATE" if result.is_duplicate else "UNIQUE"

    logger.info(
        f"[StoryDedup] Decision: {status} | "
        f"Template: {template_id} | "
        f"Research: {research_count} cards | "
        f"Signature: {result.signature[:16]}... | "
        f"Action: {result.action}"
    )

    if result.is_duplicate:
        logger.info(
            f"[StoryDedup] Existing story: {result.existing_story_id} "
            f"(created: {result.existing_created_at})"
        )
