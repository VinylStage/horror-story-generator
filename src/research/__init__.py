"""
Research module - research execution and integration.

Submodules:
- executor: Research card generation via Ollama
- integration: Research context selection for story generation
"""

# Re-export from integration submodule for backwards compatibility
from .integration import (
    load_research_cards,
    get_card_by_id,
    select_research_for_template,
    ResearchSelection,
    get_research_context_for_prompt,
    get_phase_b_status,
)

__all__ = [
    # integration exports
    "load_research_cards",
    "get_card_by_id",
    "select_research_for_template",
    "ResearchSelection",
    "get_research_context_for_prompt",
    "get_phase_b_status",
]
