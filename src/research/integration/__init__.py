"""
Research Integration - Load and select research cards for story generation.

This module provides research context injection for the horror story generator.
Research influence is READ-ONLY: it guides but never blocks generation.
"""

from src import __version__

from .loader import load_research_cards, get_card_by_id
from .selector import (
    select_research_for_template,
    ResearchSelection,
    get_research_context_for_prompt,
)
from .phase_b_hooks import get_phase_b_status

__all__ = [
    "load_research_cards",
    "get_card_by_id",
    "select_research_for_template",
    "ResearchSelection",
    "get_research_context_for_prompt",
    "get_phase_b_status",
]
