"""
Deduplication module - story similarity and research dedup logic.

Contains two separate dedup systems:
1. Story similarity (in-memory, process-scoped) - for story generation
2. Research dedup (FAISS-based, persistent) - for research cards
"""

# Story similarity (in-memory) - always available
from .similarity import (
    GenerationRecord,
    compute_text_similarity,
    observe_similarity,
    add_to_generation_memory,
    load_past_stories_into_memory,
    get_similarity_signal,
    should_accept_story,
)

# Research dedup (FAISS-based) - may not be available if numpy/faiss not installed
try:
    from .research import (
        get_embedding,
        get_embedding_async,
        OllamaEmbedder,
        FaissIndex,
        check_duplicate,
        add_card_to_index,
        get_dedup_signal,
        DedupResult,
    )
    RESEARCH_DEDUP_AVAILABLE = True
except ImportError:
    RESEARCH_DEDUP_AVAILABLE = False

__all__ = [
    # Story similarity
    "GenerationRecord",
    "compute_text_similarity",
    "observe_similarity",
    "add_to_generation_memory",
    "load_past_stories_into_memory",
    "get_similarity_signal",
    "should_accept_story",
    # Availability flag
    "RESEARCH_DEDUP_AVAILABLE",
]

# Add research dedup exports only if available
if RESEARCH_DEDUP_AVAILABLE:
    __all__.extend([
        "get_embedding",
        "get_embedding_async",
        "OllamaEmbedder",
        "FaissIndex",
        "check_duplicate",
        "add_card_to_index",
        "get_dedup_signal",
        "DedupResult",
    ])
