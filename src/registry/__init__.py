"""
Registry module - SQLite-based persistent storage for stories, seeds, and research.
"""

from .story_registry import (
    StoryRegistry,
    StoryRegistryRecord,
    init_registry as init_story_registry,
    get_registry as get_story_registry,
    close_registry as close_story_registry,
)

from .seed_registry import (
    SeedRegistry,
    SeedRecord,
    get_seed_registry,
)

from .research_registry import (
    ResearchRegistry,
    ResearchCardRecord,
    get_registry as get_research_registry,
)

__all__ = [
    # story_registry
    "StoryRegistry",
    "StoryRegistryRecord",
    "init_story_registry",
    "get_story_registry",
    "close_story_registry",
    # seed_registry
    "SeedRegistry",
    "SeedRecord",
    "get_seed_registry",
    # research_registry
    "ResearchRegistry",
    "ResearchCardRecord",
    "get_research_registry",
]
