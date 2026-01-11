"""
Story module - story generation pipeline components.

This module provides the complete story generation pipeline:
- Template loading and selection
- Prompt building
- Claude API integration
- Seed integration for thematic guidance
"""

from .generator import (
    generate_horror_story,
    generate_with_dedup_control,
    customize_template,
)

from .template_loader import (
    load_template_skeletons,
    select_random_template,
    SYSTEMIC_INEVITABILITY_CLUSTER,
    PHASE3B_LOOKBACK_WINDOW,
)

from .prompt_builder import (
    build_system_prompt,
    build_user_prompt,
)

from .api_client import (
    call_claude_api,
    generate_semantic_summary,
)

from .story_seed import (
    StorySeed,
    load_seed,
    list_seeds,
    generate_and_save_seed,
)

from .seed_integration import (
    SeedSelection,
    select_seed_for_story,
    format_seed_for_prompt,
)

__all__ = [
    # generator
    "generate_horror_story",
    "generate_with_dedup_control",
    "customize_template",
    # template_loader
    "load_template_skeletons",
    "select_random_template",
    "SYSTEMIC_INEVITABILITY_CLUSTER",
    "PHASE3B_LOOKBACK_WINDOW",
    # prompt_builder
    "build_system_prompt",
    "build_user_prompt",
    # api_client
    "call_claude_api",
    "generate_semantic_summary",
    # story_seed
    "StorySeed",
    "load_seed",
    "list_seeds",
    "generate_and_save_seed",
    # seed_integration
    "SeedSelection",
    "select_seed_for_story",
    "format_seed_for_prompt",
]
