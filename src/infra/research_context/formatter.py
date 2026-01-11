"""
Research Context Formatter

Formats selected research cards for prompt injection.
"""

import logging
from typing import Dict, Any, List, Optional

from .selector import ResearchSelection

logger = logging.getLogger(__name__)

# Default limits
MAX_CONCEPTS = 5
MAX_APPLICATIONS = 3


def build_research_context(
    selection: ResearchSelection,
    max_concepts: int = MAX_CONCEPTS,
    max_applications: int = MAX_APPLICATIONS
) -> Optional[Dict[str, Any]]:
    """
    Build research context from selection for metadata and formatting.

    Aggregates content from selected cards into a structured format.
    Returns None if no cards are selected.

    Args:
        selection: ResearchSelection result
        max_concepts: Max key_concepts to include
        max_applications: Max horror_applications to include

    Returns:
        Dict with research context, or None
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
        "source_cards": selection.card_ids,
        "match_score": selection.best_score,
        "key_concepts": selected_concepts,
        "horror_applications": selected_applications,
        "card_titles": card_summaries,
    }

    logger.debug(
        f"[ResearchContext] Context: {len(selected_concepts)} concepts, "
        f"{len(selected_applications)} applications"
    )

    return context


def format_research_for_prompt(context: Optional[Dict[str, Any]]) -> str:
    """
    Format research context as a system prompt section.

    Args:
        context: Research context from build_research_context

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

    lines.append(
        "*These are suggestions to inspire your writing. "
        "You may incorporate, adapt, or disregard as creatively appropriate.*"
    )

    return "\n".join(lines)


def format_research_for_metadata(
    selection: ResearchSelection,
    injection_mode: str = "auto"
) -> Dict[str, Any]:
    """
    Format research selection for story metadata traceability.

    Args:
        selection: ResearchSelection result
        injection_mode: "auto" | "manual" | "none"

    Returns:
        Dict for inclusion in story metadata
    """
    if not selection.has_matches:
        return {
            "research_used": [],
            "research_injection_mode": injection_mode,
            "research_selection_reason": selection.reason,
        }

    return {
        "research_used": selection.card_ids,
        "research_injection_mode": injection_mode,
        "research_selection_score": selection.best_score,
        "research_total_candidates": selection.total_available,
        "research_selection_reason": selection.reason,
    }
