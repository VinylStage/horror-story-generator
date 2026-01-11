"""
Research Context Module

Unified interface for research card selection, filtering, and prompt injection.
Used by both CLI (story generator) and API for consistent data flow.
"""

from .repository import (
    load_usable_research_cards,
    get_card_by_id,
    get_canonical_affinity,
)
from .policy import (
    DedupLevel,
    is_usable_card,
    get_dedup_level,
    DEDUP_THRESHOLD_MEDIUM,
    DEDUP_THRESHOLD_HIGH,
)
from .selector import (
    ResearchSelection,
    select_research_for_template,
    select_best_match,
)
from .formatter import (
    format_research_for_prompt,
    build_research_context,
    format_research_for_metadata,
)

__all__ = [
    # Repository
    "load_usable_research_cards",
    "get_card_by_id",
    "get_canonical_affinity",
    # Policy
    "DedupLevel",
    "is_usable_card",
    "get_dedup_level",
    "DEDUP_THRESHOLD_MEDIUM",
    "DEDUP_THRESHOLD_HIGH",
    # Selector
    "ResearchSelection",
    "select_research_for_template",
    "select_best_match",
    # Formatter
    "format_research_for_prompt",
    "build_research_context",
    "format_research_for_metadata",
]
