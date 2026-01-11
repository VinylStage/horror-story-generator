"""
Dedup service - business logic for dedup operations.

Uses story_registry.py for similarity checks against existing stories.
"""

import logging
from typing import Dict, Any, Optional, List

# Import story registry from src.registry
from src.registry.story_registry import StoryRegistry

logger = logging.getLogger(__name__)


def compute_signal(similarity_score: float) -> str:
    """
    Compute dedup signal from similarity score.

    Args:
        similarity_score: Score between 0.0 and 1.0

    Returns:
        Signal string: LOW, MEDIUM, or HIGH
    """
    if similarity_score < 0.3:
        return "LOW"
    elif similarity_score < 0.6:
        return "MEDIUM"
    else:
        return "HIGH"


def compute_canonical_similarity(
    new_core: Dict[str, str],
    existing_core: Dict[str, str]
) -> float:
    """
    Compute similarity between two canonical cores.

    Uses dimension matching with weighted scoring.

    Args:
        new_core: New story's canonical dimensions
        existing_core: Existing story's canonical dimensions

    Returns:
        Similarity score between 0.0 and 1.0
    """
    dimensions = ["setting", "primary_fear", "antagonist", "mechanism", "twist"]
    weights = {
        "setting": 0.15,
        "primary_fear": 0.25,
        "antagonist": 0.25,
        "mechanism": 0.20,
        "twist": 0.15,
    }

    total_weight = 0.0
    matched_weight = 0.0

    for dim in dimensions:
        weight = weights.get(dim, 0.2)
        total_weight += weight

        new_val = new_core.get(dim, "").lower().strip()
        existing_val = existing_core.get(dim, "").lower().strip()

        if new_val and existing_val and new_val == existing_val:
            matched_weight += weight

    if total_weight == 0:
        return 0.0

    return matched_weight / total_weight


async def evaluate_dedup(
    template_id: Optional[str] = None,
    canonical_core: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate deduplication signal against existing stories.

    Args:
        template_id: Template ID being used
        canonical_core: Canonical dimensions for comparison
        title: Story title for similarity check

    Returns:
        Dedup evaluation result dict
    """
    similar_stories: List[Dict[str, Any]] = []
    max_similarity = 0.0

    try:
        # Initialize registry (read-only)
        registry = StoryRegistry()
        recent_stories = registry.load_recent_accepted(limit=100)
        registry.close()

        if not recent_stories:
            return {
                "signal": "LOW",
                "similarity_score": 0.0,
                "similar_stories": [],
                "message": "No existing stories to compare against",
            }

        # Check for template match
        template_matches = []
        if template_id:
            template_matches = [
                s for s in recent_stories
                if s.template_id == template_id
            ]
            if len(template_matches) >= 3:
                # Recent heavy use of same template
                max_similarity = max(max_similarity, 0.4)

        # Check canonical similarity if provided
        if canonical_core:
            for story in recent_stories:
                # Parse existing story's canonical core from semantic_summary
                # (In a real implementation, we'd store this separately)
                existing_core = parse_semantic_summary(story.semantic_summary)

                sim = compute_canonical_similarity(canonical_core, existing_core)

                if sim > 0.3:
                    matched_dims = get_matched_dimensions(canonical_core, existing_core)
                    similar_stories.append({
                        "story_id": story.id,
                        "template_id": story.template_id or "",
                        "similarity_score": sim,
                        "matched_dimensions": matched_dims,
                    })

                max_similarity = max(max_similarity, sim)

        # Sort by similarity
        similar_stories.sort(key=lambda x: x["similarity_score"], reverse=True)
        similar_stories = similar_stories[:5]  # Top 5

        signal = compute_signal(max_similarity)

        message = None
        if signal == "HIGH":
            message = "High similarity detected - consider regenerating or modifying"
        elif signal == "MEDIUM":
            message = "Moderate similarity - review recommended"

        return {
            "signal": signal,
            "similarity_score": max_similarity,
            "similar_stories": similar_stories,
            "message": message,
        }

    except Exception as e:
        logger.error(f"[DedupService] Error evaluating dedup: {e}")
        return {
            "signal": "LOW",
            "similarity_score": 0.0,
            "similar_stories": [],
            "message": f"Dedup evaluation error: {str(e)}",
        }


def parse_semantic_summary(summary: str) -> Dict[str, str]:
    """
    Parse canonical dimensions from semantic summary.

    This is a simplified parser - real implementation would
    store canonical core separately in the registry.
    """
    # Placeholder - returns empty dict
    # In production, semantic_summary should be structured or
    # canonical_core should be stored as separate columns
    return {}


def get_matched_dimensions(
    new_core: Dict[str, str],
    existing_core: Dict[str, str]
) -> List[str]:
    """
    Get list of matching dimension names.
    """
    matched = []
    dimensions = ["setting", "primary_fear", "antagonist", "mechanism", "twist"]

    for dim in dimensions:
        new_val = new_core.get(dim, "").lower().strip()
        existing_val = existing_core.get(dim, "").lower().strip()

        if new_val and existing_val and new_val == existing_val:
            matched.append(dim)

    return matched
