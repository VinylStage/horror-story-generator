"""
Research Card Selector

Selects relevant research cards based on canonical affinity matching
with template skeletons. Filters out HIGH duplicates by default.

Phase 4 (Issue #21): Bi-directional matching support
- Forward: select_research_for_template() - Template → Research cards
- Reverse: select_templates_for_research() - Research card → Templates
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .repository import load_usable_research_cards, get_canonical_affinity, get_card_by_id
from .policy import DedupLevel

logger = logging.getLogger(__name__)

# Dimension weights for affinity scoring
DIMENSION_WEIGHTS = {
    "setting": 1.0,
    "primary_fear": 1.5,      # Primary fear weighted higher
    "antagonist": 1.2,
    "mechanism": 1.3,
}

# Minimum score threshold for selection (forward: template → research)
MIN_MATCH_SCORE = 0.25

# Minimum score threshold for reverse selection (research → template)
# Higher threshold for stricter filtering (Issue #21)
MIN_REVERSE_MATCH_SCORE = 0.5

# Maximum cards to return in selection
MAX_SELECTED_CARDS = 3

# Maximum templates to return in reverse selection
MAX_SELECTED_TEMPLATES = 5


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


# =============================================================================
# Issue #21: Reverse Matching (Research → Templates)
# =============================================================================


@dataclass
class TemplateSelection:
    """
    Result of template selection for a research card.

    Symmetric to ResearchSelection for bi-directional matching.

    Attributes:
        templates: List of selected template skeletons
        scores: List of match scores corresponding to templates
        match_details: Per-template match breakdown
        total_available: Total templates available
        reason: Human-readable selection reason
        template_ids: List of selected template IDs (for traceability)
    """
    templates: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    match_details: List[Dict[str, Any]] = field(default_factory=list)
    total_available: int = 0
    reason: str = ""
    template_ids: List[str] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        """Check if any templates were selected."""
        return len(self.templates) > 0

    @property
    def best_template(self) -> Optional[Dict[str, Any]]:
        """Get the highest-scoring template."""
        return self.templates[0] if self.templates else None

    @property
    def best_score(self) -> float:
        """Get the highest match score."""
        return self.scores[0] if self.scores else 0.0

    def to_traceability_dict(self) -> Dict[str, Any]:
        """Get dict for metadata traceability."""
        return {
            "matching_templates": self.template_ids,
            "best_match_score": self.best_score,
            "total_candidates": self.total_available,
            "selection_reason": self.reason,
        }


def compute_reverse_affinity_score(
    card_affinity: Dict[str, List[str]],
    template_canonical: Dict[str, str]
) -> tuple[float, Dict[str, Any]]:
    """
    Compute affinity match score from research card to template (reverse direction).

    Uses same weighted scoring as forward matching:
    - For each dimension, check if template's single value appears in card's affinity list
    - Apply dimension weight to matches
    - Normalize by total possible weighted score

    This is symmetric to compute_affinity_score() but with reversed argument order
    for semantic clarity.

    Args:
        card_affinity: Research card's canonical_affinity (lists)
        template_canonical: Template's canonical_core (single values)

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


def select_templates_for_research(
    card: Dict[str, Any],
    templates: Optional[List[Dict[str, Any]]] = None,
    max_templates: int = MAX_SELECTED_TEMPLATES,
    min_score: float = MIN_REVERSE_MATCH_SCORE,
) -> TemplateSelection:
    """
    Select template skeletons relevant to a research card (Issue #21).

    Reverse direction of select_research_for_template():
    Given a research card's canonical_affinity, find templates whose
    canonical_core values appear in the card's affinity lists.

    This function NEVER raises exceptions - always returns a valid
    TemplateSelection (possibly with empty templates list).

    Args:
        card: Research card with output.canonical_affinity
        templates: Optional list of template skeletons (loads from file if None)
        max_templates: Maximum templates to return
        min_score: Minimum score threshold (default 0.5 for stricter filtering)

    Returns:
        TemplateSelection with matched templates
    """
    card_id = card.get("card_id", "unknown")

    # Extract canonical_affinity from card
    card_affinity = get_canonical_affinity(card)

    logger.info(f"[ResearchContext] Selecting templates for card: {card_id}")
    logger.debug(f"[ResearchContext] Card affinity: {card_affinity}")

    # Load templates if not provided
    if templates is None:
        try:
            from src.story.template_loader import load_template_skeletons
            templates = load_template_skeletons()
        except Exception as e:
            logger.warning(f"[ResearchContext] Failed to load templates: {e}")
            return TemplateSelection(reason=f"Template load failed: {e}")

    if not templates:
        logger.info("[ResearchContext] No templates available")
        return TemplateSelection(reason="No templates available")

    # Score all templates
    scored_templates = []
    for template in templates:
        template_canonical = template.get("canonical_core", {})
        score, details = compute_reverse_affinity_score(card_affinity, template_canonical)

        if score >= min_score:
            scored_templates.append({
                "template": template,
                "score": score,
                "details": details,
            })

    # Sort by score (highest first)
    scored_templates.sort(key=lambda x: x["score"], reverse=True)

    # Apply limit
    selected = scored_templates[:max_templates]

    if not selected:
        logger.info(f"[ResearchContext] No templates above threshold {min_score}")
        return TemplateSelection(
            total_available=len(templates),
            reason=f"No templates scored above {min_score} threshold"
        )

    # Build result
    result_templates = [s["template"] for s in selected]
    scores = [s["score"] for s in selected]
    match_details = [s["details"] for s in selected]
    template_ids = [t.get("template_id", "unknown") for t in result_templates]

    # Log selection
    for i, s in enumerate(selected):
        template_id = s["template"].get("template_id", "unknown")
        template_name = s["template"].get("template_name", "Unknown")
        logger.info(
            f"[ResearchContext] Matched #{i+1}: {template_id} ({template_name}) "
            f"score={s['score']:.2f}"
        )

    reason = f"Selected {len(result_templates)}/{len(templates)} templates for {card_id}"
    logger.info(f"[ResearchContext] {reason}")

    return TemplateSelection(
        templates=result_templates,
        scores=scores,
        match_details=match_details,
        total_available=len(templates),
        reason=reason,
        template_ids=template_ids,
    )


def select_best_template_for_research(
    card: Dict[str, Any],
    templates: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Select the single best matching template for a research card.

    Convenience function for getting top template match.

    Args:
        card: Research card with output.canonical_affinity
        templates: Optional list of template skeletons (loads from file if None)

    Returns:
        Best matching template or None
    """
    selection = select_templates_for_research(
        card=card,
        templates=templates,
        max_templates=1,
    )
    return selection.best_template
