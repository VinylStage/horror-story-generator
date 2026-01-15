"""
Hybrid deduplication combining canonical signature and semantic similarity.

Provides a combined score from:
1. Canonical signature matching (exact match = 1.0, no match = 0.0)
2. Semantic embedding similarity (0.0 to 1.0 continuous)

The hybrid score enables detection of stories that are:
- Exact duplicates (same canonical + research)
- Semantically similar but structurally different
- Structurally identical but semantically varied
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from .semantic_dedup import (
    check_semantic_duplicate,
    DedupSignal,
    get_dedup_signal,
    SemanticDedupResult,
    THRESHOLD_HIGH,
)
from .index import StoryFaissIndex

# Import story signature functions
from src.story.dedup.story_signature import compute_story_signature

logger = logging.getLogger("horror_story_generator")

# Hybrid scoring weights (can be overridden via environment)
CANONICAL_WEIGHT = float(os.getenv("STORY_HYBRID_CANONICAL_WEIGHT", "0.3"))
SEMANTIC_WEIGHT = float(os.getenv("STORY_HYBRID_SEMANTIC_WEIGHT", "0.7"))

# Hybrid threshold for duplicate detection
HYBRID_THRESHOLD = float(os.getenv("STORY_HYBRID_THRESHOLD", "0.85"))


@dataclass
class HybridDedupResult:
    """
    Result of hybrid deduplication check.

    Combines canonical signature matching with semantic similarity.

    Attributes:
        canonical_match: True if exact signature match found
        canonical_score: 1.0 if match, 0.0 otherwise
        semantic_score: Cosine similarity (0.0 to 1.0)
        hybrid_score: Weighted combination of canonical and semantic
        signal: Deduplication signal based on hybrid score
        is_duplicate: True if hybrid score >= threshold
        nearest_story_id: ID of most similar story (from semantic search)
        matching_story_id: ID of exact match (from canonical search, if any)
    """
    canonical_match: bool
    canonical_score: float
    semantic_score: float
    hybrid_score: float
    signal: DedupSignal
    is_duplicate: bool
    nearest_story_id: Optional[str]
    matching_story_id: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "canonical_match": self.canonical_match,
            "canonical_score": round(self.canonical_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "hybrid_score": round(self.hybrid_score, 4),
            "signal": self.signal.value,
            "is_duplicate": self.is_duplicate,
            "nearest_story_id": self.nearest_story_id,
            "matching_story_id": self.matching_story_id,
        }


def compute_hybrid_score(
    canonical_score: float,
    semantic_score: float,
    canonical_weight: float = CANONICAL_WEIGHT,
    semantic_weight: float = SEMANTIC_WEIGHT
) -> float:
    """
    Compute weighted hybrid score from canonical and semantic scores.

    Args:
        canonical_score: Canonical match score (1.0 or 0.0)
        semantic_score: Semantic similarity score (0.0 to 1.0)
        canonical_weight: Weight for canonical score
        semantic_weight: Weight for semantic score

    Returns:
        Hybrid score (0.0 to 1.0)
    """
    # Normalize weights if they don't sum to 1.0
    total_weight = canonical_weight + semantic_weight
    if total_weight > 0:
        canonical_weight = canonical_weight / total_weight
        semantic_weight = semantic_weight / total_weight

    return (canonical_score * canonical_weight) + (semantic_score * semantic_weight)


def check_hybrid_duplicate(
    canonical_core: dict,
    research_used: list,
    story_data: dict,
    registry=None,
    index: Optional[StoryFaissIndex] = None,
    canonical_weight: float = CANONICAL_WEIGHT,
    semantic_weight: float = SEMANTIC_WEIGHT,
    threshold: float = HYBRID_THRESHOLD,
) -> HybridDedupResult:
    """
    Check for duplicates using both canonical and semantic methods.

    This function combines:
    1. Exact signature matching via registry lookup
    2. Semantic similarity via FAISS embedding search

    The hybrid approach catches:
    - Exact duplicates (same template + research combination)
    - Semantically similar stories with different structure
    - Stories that "feel" the same even with different canonical cores

    Args:
        canonical_core: Story's canonical core (5 dimensions)
        research_used: List of research card IDs used
        story_data: Story data dict (title, body, semantic_summary, etc.)
        registry: StoryRegistry for signature lookup (optional)
        index: StoryFaissIndex for semantic search (optional)
        canonical_weight: Weight for canonical score (default 0.3)
        semantic_weight: Weight for semantic score (default 0.7)
        threshold: Hybrid score threshold for duplicate (default 0.85)

    Returns:
        HybridDedupResult with combined analysis
    """
    # Initialize scores
    canonical_score = 0.0
    canonical_match = False
    matching_story_id = None

    # 1. Check canonical signature match
    if registry is not None:
        try:
            signature = compute_story_signature(canonical_core, research_used)
            existing = registry.find_by_signature(signature)
            if existing:
                canonical_match = True
                canonical_score = 1.0
                matching_story_id = existing.get("id") or existing.get("story_id")
                logger.info(f"[HybridDedup] Exact signature match: {matching_story_id}")
        except Exception as e:
            logger.warning(f"[HybridDedup] Canonical check failed: {e}")

    # 2. Check semantic similarity
    semantic_result = check_semantic_duplicate(
        story_data=story_data,
        story_id=story_data.get("id") or story_data.get("story_id"),
        index=index,
    )
    semantic_score = semantic_result.similarity_score
    nearest_story_id = semantic_result.nearest_story_id

    # 3. Compute hybrid score
    hybrid_score = compute_hybrid_score(
        canonical_score=canonical_score,
        semantic_score=semantic_score,
        canonical_weight=canonical_weight,
        semantic_weight=semantic_weight,
    )

    # 4. Determine signal and duplicate status
    # If canonical match, always HIGH
    if canonical_match:
        signal = DedupSignal.HIGH
        is_duplicate = True
    else:
        signal = get_dedup_signal(hybrid_score)
        is_duplicate = hybrid_score >= threshold

    result = HybridDedupResult(
        canonical_match=canonical_match,
        canonical_score=canonical_score,
        semantic_score=semantic_score,
        hybrid_score=hybrid_score,
        signal=signal,
        is_duplicate=is_duplicate,
        nearest_story_id=nearest_story_id,
        matching_story_id=matching_story_id,
    )

    logger.info(
        f"[HybridDedup] Result: canonical={canonical_score:.2f}, "
        f"semantic={semantic_score:.4f}, hybrid={hybrid_score:.4f}, "
        f"signal={signal.value}, duplicate={is_duplicate}"
    )

    return result


def check_hybrid_duplicate_simple(
    story_data: dict,
    registry=None,
    index: Optional[StoryFaissIndex] = None,
) -> HybridDedupResult:
    """
    Simplified hybrid check when canonical_core and research_used are in story_data.

    Args:
        story_data: Story data dict with canonical_core and research_used
        registry: StoryRegistry for signature lookup
        index: StoryFaissIndex for semantic search

    Returns:
        HybridDedupResult with combined analysis
    """
    canonical_core = story_data.get("canonical_core", {})
    research_used = story_data.get("research_used", [])

    return check_hybrid_duplicate(
        canonical_core=canonical_core,
        research_used=research_used,
        story_data=story_data,
        registry=registry,
        index=index,
    )
