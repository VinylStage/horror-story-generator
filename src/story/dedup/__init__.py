"""
Story-Level Deduplication Module

Provides signature-based deduplication to prevent structurally duplicated stories
from being generated, even when prompts or surface details differ.

This builds on:
- Research-level dedup (FAISS, HIGH threshold)
- Canonical Key (canonical_core)
- Research traceability (research_used)
"""

from .story_signature import compute_story_signature, normalize_canonical_core
from .story_dedup_check import (
    check_story_duplicate,
    StoryDedupResult,
    ENABLE_STORY_DEDUP,
    STORY_DEDUP_STRICT,
)

__all__ = [
    "compute_story_signature",
    "normalize_canonical_core",
    "check_story_duplicate",
    "StoryDedupResult",
    "ENABLE_STORY_DEDUP",
    "STORY_DEDUP_STRICT",
]
