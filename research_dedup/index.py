"""
FAISS index management for research card vectors.

Phase B+: Local vector storage and similarity search.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("horror_story_generator")

# Try to import FAISS
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("[FaissIndex] FAISS not available - similarity search disabled")


class FaissIndex:
    """
    FAISS-based vector index for research cards.

    Stores embeddings and metadata for semantic similarity search.
    Supports persistence to disk.
    """

    def __init__(
        self,
        index_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
        dimension: int = 4096  # Default for qwen3:30b
    ):
        """
        Initialize the FAISS index.

        Args:
            index_path: Path to save/load FAISS index
            metadata_path: Path to save/load metadata JSON
            dimension: Embedding dimension (auto-detected on first add)
        """
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dimension = dimension

        # FAISS index (inner product for cosine similarity with normalized vectors)
        self._index: Optional["faiss.IndexFlatIP"] = None

        # Metadata: maps internal vector ID to card ID
        self._id_to_card: Dict[int, str] = {}
        self._card_to_id: Dict[str, int] = {}

        # Load existing index if paths provided
        if index_path and metadata_path:
            self._load()

    def _ensure_index(self, dim: Optional[int] = None) -> bool:
        """
        Ensure FAISS index is initialized.

        Args:
            dim: Embedding dimension (uses self.dimension if not provided)

        Returns:
            True if index is ready, False if FAISS unavailable
        """
        if not FAISS_AVAILABLE:
            return False

        if self._index is None:
            actual_dim = dim or self.dimension
            self._index = faiss.IndexFlatIP(actual_dim)
            self.dimension = actual_dim
            logger.debug(f"[FaissIndex] Initialized index with dimension {actual_dim}")

        return True

    def add(self, card_id: str, embedding: List[float]) -> bool:
        """
        Add a research card embedding to the index.

        Args:
            card_id: Unique card identifier (e.g., "RC-2026-01-11-001")
            embedding: Embedding vector

        Returns:
            True if added successfully, False otherwise
        """
        if not embedding:
            logger.warning(f"[FaissIndex] Empty embedding for {card_id}")
            return False

        # Skip if already indexed
        if card_id in self._card_to_id:
            logger.debug(f"[FaissIndex] Card already indexed: {card_id}")
            return True

        # Ensure index exists with correct dimension
        if not self._ensure_index(len(embedding)):
            logger.warning("[FaissIndex] FAISS not available")
            return False

        try:
            # Normalize for cosine similarity
            vec = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(vec)

            # Add to index
            vector_id = self._index.ntotal
            self._index.add(vec)

            # Update metadata
            self._id_to_card[vector_id] = card_id
            self._card_to_id[card_id] = vector_id

            logger.debug(f"[FaissIndex] Added card {card_id} at index {vector_id}")
            return True

        except Exception as e:
            logger.error(f"[FaissIndex] Failed to add {card_id}: {e}")
            return False

    def search(
        self,
        embedding: List[float],
        k: int = 5,
        exclude_card_id: Optional[str] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for similar cards.

        Args:
            embedding: Query embedding vector
            k: Number of results to return
            exclude_card_id: Card ID to exclude from results (for self-comparison)

        Returns:
            List of (card_id, similarity_score) tuples, sorted by similarity
        """
        if not FAISS_AVAILABLE or self._index is None:
            return []

        if self._index.ntotal == 0:
            return []

        try:
            # Normalize query vector
            vec = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(vec)

            # Search (get extra results to account for exclusion)
            search_k = min(k + 1, self._index.ntotal)
            scores, indices = self._index.search(vec, search_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:  # FAISS returns -1 for invalid indices
                    continue

                card_id = self._id_to_card.get(int(idx))
                if card_id is None:
                    continue

                if exclude_card_id and card_id == exclude_card_id:
                    continue

                # Score is already cosine similarity (0.0 to 1.0 for normalized vectors)
                results.append((card_id, float(score)))

                if len(results) >= k:
                    break

            return results

        except Exception as e:
            logger.error(f"[FaissIndex] Search failed: {e}")
            return []

    def get_nearest(
        self,
        embedding: List[float],
        exclude_card_id: Optional[str] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Get the nearest card to the given embedding.

        Args:
            embedding: Query embedding vector
            exclude_card_id: Card ID to exclude from results

        Returns:
            (card_id, similarity_score) tuple, or None if no results
        """
        results = self.search(embedding, k=1, exclude_card_id=exclude_card_id)
        return results[0] if results else None

    def contains(self, card_id: str) -> bool:
        """Check if a card is already indexed."""
        return card_id in self._card_to_id

    @property
    def size(self) -> int:
        """Get the number of indexed cards."""
        return len(self._card_to_id)

    def save(self) -> bool:
        """
        Save index and metadata to disk.

        Returns:
            True if saved successfully, False otherwise
        """
        if not FAISS_AVAILABLE or self._index is None:
            return False

        if not self.index_path or not self.metadata_path:
            logger.warning("[FaissIndex] No paths configured for saving")
            return False

        try:
            # Ensure parent directories exist
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            faiss.write_index(self._index, str(self.index_path))

            # Save metadata
            metadata = {
                "dimension": self.dimension,
                "id_to_card": {str(k): v for k, v in self._id_to_card.items()},
                "card_to_id": self._card_to_id,
            }
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"[FaissIndex] Saved {self.size} vectors to {self.index_path}")
            return True

        except Exception as e:
            logger.error(f"[FaissIndex] Save failed: {e}")
            return False

    def _load(self) -> bool:
        """
        Load index and metadata from disk.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not FAISS_AVAILABLE:
            return False

        if not self.index_path or not self.metadata_path:
            return False

        if not self.index_path.exists() or not self.metadata_path.exists():
            logger.debug("[FaissIndex] No existing index found")
            return False

        try:
            # Load FAISS index
            self._index = faiss.read_index(str(self.index_path))

            # Load metadata
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            self.dimension = metadata.get("dimension", self.dimension)
            self._id_to_card = {int(k): v for k, v in metadata.get("id_to_card", {}).items()}
            self._card_to_id = metadata.get("card_to_id", {})

            logger.info(f"[FaissIndex] Loaded {self.size} vectors from {self.index_path}")
            return True

        except Exception as e:
            logger.error(f"[FaissIndex] Load failed: {e}")
            self._index = None
            self._id_to_card = {}
            self._card_to_id = {}
            return False

    def clear(self) -> None:
        """Clear all indexed data."""
        self._index = None
        self._id_to_card = {}
        self._card_to_id = {}
        logger.debug("[FaissIndex] Index cleared")


# Global index instance
_global_index: Optional[FaissIndex] = None


def get_index(
    index_path: Optional[Path] = None,
    metadata_path: Optional[Path] = None
) -> FaissIndex:
    """
    Get or create global FAISS index instance.

    If paths are not provided, uses default paths from data_paths module.

    Args:
        index_path: Optional custom index path
        metadata_path: Optional custom metadata path

    Returns:
        FaissIndex instance
    """
    global _global_index

    # Use default paths if not provided
    if index_path is None or metadata_path is None:
        try:
            from src.infra.data_paths import get_faiss_index_path, get_vector_metadata_path
            index_path = index_path or get_faiss_index_path()
            metadata_path = metadata_path or get_vector_metadata_path()
        except ImportError:
            pass

    if _global_index is None:
        _global_index = FaissIndex(
            index_path=index_path,
            metadata_path=metadata_path
        )

    return _global_index


def is_faiss_available() -> bool:
    """Check if FAISS is available."""
    return FAISS_AVAILABLE
