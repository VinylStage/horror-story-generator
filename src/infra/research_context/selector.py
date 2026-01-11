"""
Research Card Selector

Selects relevant research cards based on canonical affinity matching
with template skeletons. Filters out HIGH duplicates by default.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .repository import load_usable_research_cards, get_canonical_affinity
from .policy import DedupLevel

logger = logging.getLogger(__name__)

# Dimension weights for affinity scoring
DIMENSION_WEIGHTS = {
    "setting": 1.0,
    "primary_fear": 1.5,      # Primary fear weighted higher
    "antagonist": 1.2,
    "mechanism": 1.3,
}

# Minimum score threshold for selection
MIN_MATCH_SCORE = 0.25

# Maximum cards to return in selection
MAX_SELECTED_CARDS = 3


@dataclass
class ResearchSelection:
    """
    Result of research card selection.

    Attributes:
        cards: List of selected research cards (full data)
        scores: List of match scores corresponding to cards
        match_details: Per-card match breakdown
        total_available: Total cards available before filtering
        reason: Human-readable selection reason
        card_ids: List of selected card IDs (for traceability)
    """
    cards: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    match_details: List[Dict[str, Any]] = field(default_factory=list)
    total_available: int = 0
    reason: str = ""
    card_ids: List[str] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        """Check if any cards were selected."""
        return len(self.cards) > 0

    @property
    def best_card(self) -> Optional[Dict[str, Any]]:
        """Get the highest-scoring card."""
        return self.cards[0] if self.cards else None

    @property
    def best_score(self) -> float:
        """Get the highest match score."""
        return self.scores[0] if self.scores else 0.0

    def to_traceability_dict(self) -> Dict[str, Any]:
        """Get dict for story metadata traceability."""
        return {
            "research_used": self.card_ids,
            "selection_score": self.best_score,
            "total_candidates": self.total_available,
            "selection_reason": self.reason,
        }


def compute_affinity_score(
    template_canonical: Dict[str, str],
    card_affinity: Dict[str, List[str]]
) -> tuple[float, Dict[str, Any]]:
    """
    Compute affinity match score between template and research card.

    Uses weighted set intersection:
    - For each dimension, check if template value appears in card's affinity list
    - Apply dimension weight to matches
    - Normalize by total possible weighted score

    Args:
        template_canonical: Template's canonical_core (single values)
        card_affinity: Research card's canonical_affinity (lists)

    Returns:
        Tuple of (score, match_details)
    """
    total_weight = 0.0
    matched_weight = 0.0
    details = {}

    for dim, weight in DIMENSION_WEIGHTS.items():
        template_value = template_canonical.get(dim, "")
        card_values = set(card_affinity.get(dim, []))

        match = template_value in card_values if template_value else False

        details[dim] = {
            "template_value": template_value,
            "card_values": list(card_values),
            "match": match,
            "weight": weight,
        }

        if template_value:
            total_weight += weight
            if match:
                matched_weight += weight

    score = matched_weight / total_weight if total_weight > 0 else 0.0
    details["_score"] = score

    return score, details


def select_research_for_template(
    skeleton: Dict[str, Any],
    base_dir: str = "./data/research",
    max_cards: int = MAX_SELECTED_CARDS,
    min_score: float = MIN_MATCH_SCORE,
    exclude_level: DedupLevel = DedupLevel.HIGH
) -> ResearchSelection:
    """
    Select research cards relevant to a template skeleton.

    Selection is based on canonical_affinity matching.
    HIGH duplicates are excluded by default.

    This function NEVER raises exceptions - always returns a valid
    ResearchSelection (possibly with empty cards list).

    Args:
        skeleton: Template skeleton with canonical_core
        base_dir: Research cards directory
        max_cards: Maximum cards to return
        min_score: Minimum score threshold (0.0 to 1.0)
        exclude_level: Dedup level at or above which cards are excluded

    Returns:
        ResearchSelection with matched cards
    """
    template_name = skeleton.get("template_name", "Unknown")
    template_id = skeleton.get("template_id", "")
    canonical = skeleton.get("canonical_core", {})

    logger.info(f"[ResearchContext] Selecting for template: {template_name}")
    logger.debug(f"[ResearchContext] Template canonical: {canonical}")

    # Load usable cards (excludes HIGH duplicates)
    try:
        all_cards = load_usable_research_cards(
            base_dir=base_dir,
            exclude_level=exclude_level
        )
    except Exception as e:
        logger.warning(f"[ResearchContext] Failed to load cards: {e}")
        return ResearchSelection(reason=f"Load failed: {e}")

    if not all_cards:
        logger.info("[ResearchContext] No usable research cards available")
        return ResearchSelection(reason="No usable research cards available")

    # Score all cards
    scored_cards = []
    for card in all_cards:
        card_affinity = get_canonical_affinity(card)
        score, details = compute_affinity_score(canonical, card_affinity)

        if score >= min_score:
            scored_cards.append({
                "card": card,
                "score": score,
                "details": details,
            })

    # Sort by score (highest first)
    scored_cards.sort(key=lambda x: x["score"], reverse=True)

    # Apply limit
    selected = scored_cards[:max_cards]

    if not selected:
        logger.info(f"[ResearchContext] No cards above threshold {min_score}")
        return ResearchSelection(
            total_available=len(all_cards),
            reason=f"No cards scored above {min_score} threshold"
        )

    # Build result
    cards = [s["card"] for s in selected]
    scores = [s["score"] for s in selected]
    match_details = [s["details"] for s in selected]
    card_ids = [c.get("card_id", "unknown") for c in cards]

    # Log selection
    for i, s in enumerate(selected):
        card_id = s["card"].get("card_id", "unknown")
        logger.info(f"[ResearchContext] Selected #{i+1}: {card_id} (score={s['score']:.2f})")

    reason = f"Selected {len(cards)}/{len(all_cards)} cards for {template_name}"
    logger.info(f"[ResearchContext] {reason}")

    return ResearchSelection(
        cards=cards,
        scores=scores,
        match_details=match_details,
        total_available=len(all_cards),
        reason=reason,
        card_ids=card_ids,
    )


def select_best_match(
    skeleton: Dict[str, Any],
    base_dir: str = "./data/research",
    exclude_level: DedupLevel = DedupLevel.HIGH
) -> Optional[Dict[str, Any]]:
    """
    Select the single best matching research card.

    Convenience function for getting top match.

    Args:
        skeleton: Template skeleton with canonical_core
        base_dir: Research cards directory
        exclude_level: Dedup level at or above which cards are excluded

    Returns:
        Best matching card or None
    """
    selection = select_research_for_template(
        skeleton=skeleton,
        base_dir=base_dir,
        max_cards=1,
        exclude_level=exclude_level
    )
    return selection.best_card
