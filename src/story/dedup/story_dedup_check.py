"""
Story Deduplication Check

Provides the enforcement logic for story-level deduplication.
Checks if a story signature already exists in the registry.

v1.4.0: Added semantic/hybrid deduplication support.

Configuration:
- ENABLE_STORY_DEDUP: Enable/disable signature-based dedup (default: true)
- STORY_DEDUP_STRICT: If true, abort generation on duplicate (default: false)
- ENABLE_STORY_SEMANTIC_DEDUP: Enable semantic similarity check (default: true)
- STORY_HYBRID_THRESHOLD: Threshold for hybrid duplicate detection (default: 0.85)
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

# v1.4.0: Semantic dedup configuration
ENABLE_STORY_SEMANTIC_DEDUP = os.getenv(
    "ENABLE_STORY_SEMANTIC_DEDUP", "true"
).lower() == "true"


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
        semantic_score: Semantic similarity score (v1.4.0)
        hybrid_score: Combined canonical + semantic score (v1.4.0)
        nearest_story_id: ID of semantically similar story (v1.4.0)
    """
    signature: str
    is_duplicate: bool = False
    existing_story_id: Optional[str] = None
    existing_created_at: Optional[str] = None
    reason: str = "unique"
    action: str = "none"  # "none", "warn", "abort"
    # v1.4.0: Semantic dedup fields
    semantic_score: float = 0.0
    hybrid_score: float = 0.0
    nearest_story_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        result = {
            "story_signature": self.signature,
            "story_dedup_result": "duplicate" if self.is_duplicate else "unique",
            "story_dedup_reason": self.reason,
            "story_dedup_action": self.action,
            "story_dedup_existing_id": self.existing_story_id,
        }
        # v1.4.0: Add semantic fields if available
        if self.semantic_score > 0:
            result["semantic_similarity_score"] = round(self.semantic_score, 4)
        if self.hybrid_score > 0:
            result["hybrid_dedup_score"] = round(self.hybrid_score, 4)
        if self.nearest_story_id:
            result["nearest_story_id"] = self.nearest_story_id
        return result


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

    # v1.4.0: Log semantic info if available
    if result.semantic_score > 0:
        logger.info(
            f"[StoryDedup] Semantic: score={result.semantic_score:.4f}, "
            f"hybrid={result.hybrid_score:.4f}, nearest={result.nearest_story_id}"
        )


def check_story_duplicate_hybrid(
    canonical_core: Optional[Dict[str, str]],
    research_used: Optional[List[str]],
    story_data: Dict[str, Any],
    registry: Any = None,
    strict: Optional[bool] = None,
) -> StoryDedupResult:
    """
    Check for duplicates using both signature and semantic methods.

    v1.4.0: Hybrid deduplication combining:
    1. Exact signature matching (canonical_core + research_used)
    2. Semantic similarity via embeddings (story content)

    Args:
        canonical_core: Template's canonical_core (5 dimensions)
        research_used: List of research card IDs
        story_data: Story data dict (title, body, summary, etc.)
        registry: StoryRegistry instance (optional)
        strict: Override STORY_DEDUP_STRICT env var

    Returns:
        StoryDedupResult with signature, semantic, and hybrid scores

    Raises:
        ValueError: If strict=True and duplicate found
    """
    # First, do the signature-based check
    result = check_story_duplicate(
        canonical_core=canonical_core,
        research_used=research_used,
        registry=registry,
        strict=False,  # Don't raise here, we'll check hybrid score
    )

    # If semantic dedup is disabled, return signature-only result
    if not ENABLE_STORY_SEMANTIC_DEDUP:
        logger.debug("[StoryDedup] Semantic dedup disabled, using signature only")
        # Check strict mode for signature-only
        if result.is_duplicate:
            use_strict = strict if strict is not None else STORY_DEDUP_STRICT
            if use_strict:
                result.action = "abort"
                raise ValueError(
                    f"Story signature duplicate detected: {result.existing_story_id}. "
                    f"STORY_DEDUP_STRICT=true prevents generation."
                )
        return result

    # Try to import hybrid dedup (may fail if dependencies not available)
    try:
        from src.dedup.story.hybrid_dedup import check_hybrid_duplicate
    except ImportError as e:
        logger.warning(f"[StoryDedup] Hybrid dedup not available: {e}")
        # Fall back to signature-only
        if result.is_duplicate:
            use_strict = strict if strict is not None else STORY_DEDUP_STRICT
            if use_strict:
                result.action = "abort"
                raise ValueError(
                    f"Story signature duplicate detected: {result.existing_story_id}. "
                    f"STORY_DEDUP_STRICT=true prevents generation."
                )
        return result

    # Do hybrid check
    try:
        hybrid_result = check_hybrid_duplicate(
            canonical_core=canonical_core or {},
            research_used=research_used or [],
            story_data=story_data,
            registry=registry,
        )

        # Update result with semantic/hybrid info
        result.semantic_score = hybrid_result.semantic_score
        result.hybrid_score = hybrid_result.hybrid_score
        result.nearest_story_id = hybrid_result.nearest_story_id

        # Update duplicate status based on hybrid score
        if hybrid_result.is_duplicate and not result.is_duplicate:
            result.is_duplicate = True
            result.reason = f"semantic_similar_to_{hybrid_result.nearest_story_id}"
            logger.warning(
                f"[StoryDedup] SEMANTIC DUPLICATE DETECTED - "
                f"hybrid_score={hybrid_result.hybrid_score:.4f}, "
                f"nearest={hybrid_result.nearest_story_id}"
            )

    except Exception as e:
        logger.warning(f"[StoryDedup] Hybrid check failed: {e}")
        # Continue with signature-only result

    # Final strict mode check
    if result.is_duplicate:
        use_strict = strict if strict is not None else STORY_DEDUP_STRICT
        if use_strict:
            result.action = "abort"
            raise ValueError(
                f"Story duplicate detected (hybrid): {result.reason}. "
                f"STORY_DEDUP_STRICT=true prevents generation."
            )
        else:
            result.action = "warn"

    return result


def add_story_to_semantic_index(
    story_id: str,
    story_data: Dict[str, Any],
) -> bool:
    """
    Add a story to the semantic dedup index.

    Should be called after a story is accepted.

    v1.4.0: Adds story embedding to FAISS index.

    Args:
        story_id: Unique story identifier
        story_data: Story data dict (title, body, etc.)

    Returns:
        True if added successfully, False otherwise
    """
    if not ENABLE_STORY_SEMANTIC_DEDUP:
        return False

    try:
        from src.dedup.story.semantic_dedup import add_story_to_index
        return add_story_to_index(story_data, story_id)
    except ImportError as e:
        logger.warning(f"[StoryDedup] Cannot add to semantic index: {e}")
        return False
    except Exception as e:
        logger.error(f"[StoryDedup] Failed to add to semantic index: {e}")
        return False
