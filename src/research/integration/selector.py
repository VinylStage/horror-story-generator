"""
Research Card Selector

Selects relevant research cards based on canonical affinity matching
with template skeletons.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set

from .loader import load_research_cards, get_canonical_affinity, get_card_summary

logger = logging.getLogger(__name__)

# Dimension weights for affinity scoring
# Higher weight = more important for matching
DIMENSION_WEIGHTS = {
    "setting": 1.0,
    "primary_fear": 1.5,      # Primary fear is weighted higher
    "antagonist": 1.2,
    "mechanism": 1.3,
}

# Minimum score threshold for selection (0.0 to 1.0)
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
    """
    cards: List[Dict[str, Any]]
    scores: List[float]
    match_details: List[Dict[str, Any]]
    total_available: int
    reason: str

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
        score: 0.0 to 1.0 normalized match score
        match_details: Per-dimension match breakdown
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

        if template_value:  # Only count if template has a value
            total_weight += weight
            if match:
                matched_weight += weight

    score = matched_weight / total_weight if total_weight > 0 else 0.0
    details["_score"] = score
    details["_matched_weight"] = matched_weight
    details["_total_weight"] = total_weight

    return score, details


def select_research_for_template(
    skeleton: Dict[str, Any],
    base_dir: str = "./data/research",
    max_cards: int = MAX_SELECTED_CARDS,
    min_score: float = MIN_MATCH_SCORE,
    quality_filter: bool = True
) -> ResearchSelection:
    """
    Select research cards relevant to a template skeleton.

    Selection is based on canonical_affinity matching:
    - Cards with higher affinity overlap score higher
    - Only cards above min_score threshold are included
    - Results sorted by score (highest first)

    This function NEVER raises exceptions - always returns a valid
    ResearchSelection (possibly with empty cards list).

    Args:
        skeleton: Template skeleton with canonical_core
        base_dir: Research cards directory
        max_cards: Maximum cards to return
        min_score: Minimum score threshold (0.0 to 1.0)
        quality_filter: If True, only load good/partial quality cards

    Returns:
        ResearchSelection with matched cards
    """
    template_name = skeleton.get("template_name", "Unknown")
    template_id = skeleton.get("template_id", "")
    canonical = skeleton.get("canonical_core", {})

    logger.info(f"[ResearchInject] Selecting research for template: {template_name}")
    logger.debug(f"[ResearchInject] Template canonical: {canonical}")

    # Load available cards
    try:
        all_cards = load_research_cards(
            base_dir=base_dir,
            quality_filter=quality_filter
        )
    except Exception as e:
        logger.warning(f"[ResearchInject] Failed to load cards: {e}")
        return ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=0,
            reason=f"Load failed: {e}"
        )

    if not all_cards:
        logger.info("[ResearchInject] No research cards available")
        return ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=0,
            reason="No research cards available"
        )

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
        logger.info(f"[ResearchInject] No cards above threshold {min_score}")
        return ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=len(all_cards),
            reason=f"No cards scored above {min_score} threshold"
        )

    # Build result
    cards = [s["card"] for s in selected]
    scores = [s["score"] for s in selected]
    match_details = [s["details"] for s in selected]

    # Log selection
    for i, s in enumerate(selected):
        card_id = s["card"].get("card_id", "unknown")
        logger.info(f"[ResearchInject] Selected #{i+1}: {card_id} (score={s['score']:.2f})")

    reason = f"Selected {len(cards)}/{len(all_cards)} cards for {template_name}"
    logger.info(f"[ResearchInject] {reason}")

    return ResearchSelection(
        cards=cards,
        scores=scores,
        match_details=match_details,
        total_available=len(all_cards),
        reason=reason
    )


def get_research_context_for_prompt(
    selection: ResearchSelection,
    max_concepts: int = 5,
    max_applications: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Format selected research for prompt injection.

    Aggregates content from selected cards into a prompt-friendly format.
    Returns None if no cards are selected.

    Args:
        selection: ResearchSelection result
        max_concepts: Max key_concepts to include (across all cards)
        max_applications: Max horror_applications to include

    Returns:
        Dict with research context for prompt, or None
    """
    if not selection.has_matches:
        return None

    # Aggregate from selected cards
    all_concepts: List[str] = []
    all_applications: List[str] = []
    card_summaries: List[str] = []

    for card in selection.cards:
        output = card.get("output", {})

        # Collect concepts (deduplicated)
        for concept in output.get("key_concepts", []):
            if concept not in all_concepts:
                all_concepts.append(concept)

        # Collect applications (deduplicated)
        for app in output.get("horror_applications", []):
            if app not in all_applications:
                all_applications.append(app)

        # Build card summary
        card_id = card.get("card_id", "unknown")
        title = output.get("title", "")
        if title:
            card_summaries.append(f"{card_id}: {title}")

    # Apply limits
    selected_concepts = all_concepts[:max_concepts]
    selected_applications = all_applications[:max_applications]

    context = {
        "source_cards": [c.get("card_id") for c in selection.cards],
        "match_score": selection.best_score,
        "key_concepts": selected_concepts,
        "horror_applications": selected_applications,
        "card_titles": card_summaries,
    }

    logger.debug(f"[ResearchInject] Context: {len(selected_concepts)} concepts, "
                 f"{len(selected_applications)} applications")

    return context


def format_research_for_system_prompt(context: Dict[str, Any]) -> str:
    """
    Format research context as a system prompt section.

    Args:
        context: Research context from get_research_context_for_prompt

    Returns:
        Formatted string for insertion into system prompt
    """
    if not context:
        return ""

    lines = [
        "",
        "## Research Context (from prior analysis)",
        "",
    ]

    concepts = context.get("key_concepts", [])
    if concepts:
        lines.append("**Relevant concepts to consider:**")
        for concept in concepts:
            lines.append(f"- {concept}")
        lines.append("")

    applications = context.get("horror_applications", [])
    if applications:
        lines.append("**Horror application ideas:**")
        for app in applications:
            lines.append(f"- {app}")
        lines.append("")

    lines.append("*These are suggestions to inspire your writing. "
                 "You may incorporate, adapt, or disregard as creatively appropriate.*")

    return "\n".join(lines)
