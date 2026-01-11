"""
Research Deduplication Module.

Phase B+: FAISS-based semantic deduplication for research cards.

This module provides:
- Local embedding generation via Ollama
- FAISS index management for vector storage
- Similarity-based deduplication checks

All operations are LOCAL-FIRST and non-blocking.
High similarity does NOT block - only warns and logs.
"""

from .embedder import get_embedding, OllamaEmbedder
from .index import FaissIndex
from .dedup import (
    check_duplicate,
    add_card_to_index,
    get_dedup_signal,
    DedupResult,
)

__all__ = [
    "get_embedding",
    "OllamaEmbedder",
    "FaissIndex",
    "check_duplicate",
    "add_card_to_index",
    "get_dedup_signal",
    "DedupResult",
]
