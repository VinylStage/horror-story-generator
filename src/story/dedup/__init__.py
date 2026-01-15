"""
Story-Level Deduplication Module

Provides signature-based deduplication to prevent structurally duplicated stories
from being generated, even when prompts or surface details differ.

v1.4.0: Added semantic/hybrid deduplication using embeddings.

This builds on:
- Research-level dedup (FAISS, HIGH threshold)
- Canonical Key (canonical_core)
- Research traceability (research_used)
- Semantic embeddings (story content similarity)
"""

from .story_signature import compute_story_signature, normalize_canonical_core
from .story_dedup_check import (
    check_story_duplicate,
    check_story_duplicate_hybrid,
    add_story_to_semantic_index,
    StoryDedupResult,
    ENABLE_STORY_DEDUP,
    STORY_DEDUP_STRICT,
    ENABLE_STORY_SEMANTIC_DEDUP,
)

__all__ = [
    "compute_story_signature",
    "normalize_canonical_core",
    "check_story_duplicate",
    "check_story_duplicate_hybrid",
    "add_story_to_semantic_index",
    "StoryDedupResult",
    "ENABLE_STORY_DEDUP",
    "STORY_DEDUP_STRICT",
    "ENABLE_STORY_SEMANTIC_DEDUP",
]
