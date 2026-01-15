"""
Story deduplication module with semantic embedding support.

Provides embedding-based semantic similarity checking for stories,
complementing the existing canonical signature-based deduplication.
"""

from .embedder import (
    create_story_text_for_embedding,
    get_story_embedding,
    get_story_embedding_async,
)
from .index import (
    StoryFaissIndex,
    get_story_index,
    is_faiss_available,
)
from .semantic_dedup import (
    SemanticDedupResult,
    DedupSignal,
    check_semantic_duplicate,
    add_story_to_index,
    get_similar_stories,
)
from .hybrid_dedup import (
    HybridDedupResult,
    check_hybrid_duplicate,
)

__all__ = [
    # Embedder
    "create_story_text_for_embedding",
    "get_story_embedding",
    "get_story_embedding_async",
    # Index
    "StoryFaissIndex",
    "get_story_index",
    "is_faiss_available",
    # Semantic dedup
    "SemanticDedupResult",
    "DedupSignal",
    "check_semantic_duplicate",
    "add_story_to_index",
    "get_similar_stories",
    # Hybrid dedup
    "HybridDedupResult",
    "check_hybrid_duplicate",
]
