"""
Semantic deduplication for stories using embedding similarity.

Provides FAISS-based semantic similarity checking, complementing
the existing signature-based exact match deduplication.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from .embedder import (
    create_story_text_for_embedding,
    get_story_embedding,
    DEFAULT_EMBED_MODEL,
)
from .index import get_story_index, StoryFaissIndex

logger = logging.getLogger("horror_story_generator")


class DedupSignal(Enum):
    """
    Deduplication signal levels.

    LOW: Similarity < 0.7 - Story is likely unique
    MEDIUM: 0.7 <= Similarity < 0.85 - Some thematic overlap
    HIGH: Similarity >= 0.85 - Very similar to existing story
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# Threshold configuration (can be overridden via environment)
THRESHOLD_MEDIUM = float(os.getenv("STORY_SEMANTIC_THRESHOLD_MEDIUM", "0.70"))
THRESHOLD_HIGH = float(os.getenv("STORY_SEMANTIC_THRESHOLD_HIGH", "0.85"))

# Feature flag
ENABLE_STORY_SEMANTIC_DEDUP = os.getenv(
    "ENABLE_STORY_SEMANTIC_DEDUP", "true"
).lower() == "true"


@dataclass
class SemanticDedupResult:
    """
    Result of semantic deduplication check.

    Attributes:
        similarity_score: Cosine similarity (0.0 to 1.0)
        nearest_story_id: ID of the most similar existing story (None if index empty)
        signal: Deduplication signal level
        is_duplicate: True if signal is HIGH (convenience flag)
    """
    similarity_score: float
    nearest_story_id: Optional[str]
    signal: DedupSignal

    @property
    def is_duplicate(self) -> bool:
        """Check if this is a high-similarity duplicate."""
        return self.signal == DedupSignal.HIGH

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "similarity_score": round(self.similarity_score, 4),
            "nearest_story_id": self.nearest_story_id,
            "signal": self.signal.value,
            "is_duplicate": self.is_duplicate,
        }


def get_dedup_signal(similarity: float) -> DedupSignal:
    """
    Determine dedup signal level from similarity score.

    Args:
        similarity: Cosine similarity score (0.0 to 1.0)

    Returns:
        DedupSignal level
    """
    if similarity >= THRESHOLD_HIGH:
        return DedupSignal.HIGH
    elif similarity >= THRESHOLD_MEDIUM:
        return DedupSignal.MEDIUM
    else:
        return DedupSignal.LOW


def check_semantic_duplicate(
    story_data: dict,
    story_id: Optional[str] = None,
    index: Optional[StoryFaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> SemanticDedupResult:
    """
    Check if a story is semantically similar to existing stories.

    This function:
    1. Extracts text from story data
    2. Generates embedding via Ollama
    3. Searches FAISS index for similar stories
    4. Returns similarity score and signal level

    IMPORTANT: This NEVER blocks. It only provides information.

    Args:
        story_data: Story data dict (title, body, etc.)
        story_id: Optional story ID to exclude from search (for self-comparison)
        index: FAISS index to search (uses global if not provided)
        model: Ollama model for embeddings

    Returns:
        SemanticDedupResult with similarity info
    """
    # Default result for failures or disabled state
    default_result = SemanticDedupResult(
        similarity_score=0.0,
        nearest_story_id=None,
        signal=DedupSignal.LOW
    )

    # Check if semantic dedup is enabled
    if not ENABLE_STORY_SEMANTIC_DEDUP:
        logger.debug("[SemanticDedup] Semantic dedup disabled")
        return default_result

    # Get or create index
    if index is None:
        index = get_story_index()

    # If index is empty, nothing to compare
    if index.size == 0:
        logger.debug("[SemanticDedup] Index empty - no comparison possible")
        return default_result

    # Extract text for embedding
    text = create_story_text_for_embedding(story_data)
    if not text:
        logger.warning("[SemanticDedup] Empty text extracted from story")
        return default_result

    # Get embedding
    embedding = get_story_embedding(text, model=model)
    if embedding is None:
        logger.warning("[SemanticDedup] Failed to generate embedding")
        return default_result

    # Find nearest story
    nearest = index.get_nearest(embedding, exclude_story_id=story_id)

    if nearest is None:
        logger.debug("[SemanticDedup] No similar stories found")
        return default_result

    nearest_id, score = nearest
    signal = get_dedup_signal(score)

    result = SemanticDedupResult(
        similarity_score=score,
        nearest_story_id=nearest_id,
        signal=signal
    )

    logger.info(
        f"[SemanticDedup] Similarity check: score={score:.4f}, "
        f"nearest={nearest_id}, signal={signal.value}"
    )

    return result


def check_semantic_duplicate_by_text(
    story_text: str,
    story_id: Optional[str] = None,
    index: Optional[StoryFaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> SemanticDedupResult:
    """
    Check semantic similarity using raw story text.

    Convenience function when story data dict is not available.

    Args:
        story_text: Raw story text
        story_id: Optional story ID to exclude from search
        index: FAISS index to search
        model: Ollama model for embeddings

    Returns:
        SemanticDedupResult with similarity info
    """
    # Create a minimal story data dict
    story_data = {"body": story_text}
    return check_semantic_duplicate(
        story_data=story_data,
        story_id=story_id,
        index=index,
        model=model
    )


def add_story_to_index(
    story_data: dict,
    story_id: str,
    index: Optional[StoryFaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL,
    save: bool = True
) -> bool:
    """
    Add a story to the FAISS index.

    Should be called after a story is successfully generated and accepted.

    Args:
        story_data: Story data dict (title, body, etc.)
        story_id: Unique story identifier
        index: FAISS index (uses global if not provided)
        model: Ollama model for embeddings
        save: Whether to save index to disk after adding

    Returns:
        True if added successfully, False otherwise
    """
    # Check if semantic dedup is enabled
    if not ENABLE_STORY_SEMANTIC_DEDUP:
        logger.debug("[SemanticDedup] Semantic dedup disabled - skipping index add")
        return False

    # Get or create index
    if index is None:
        index = get_story_index()

    # Skip if already indexed
    if index.contains(story_id):
        logger.debug(f"[SemanticDedup] Story already indexed: {story_id}")
        return True

    # Extract text for embedding
    text = create_story_text_for_embedding(story_data)
    if not text:
        logger.warning(f"[SemanticDedup] Empty text for story {story_id}")
        return False

    # Get embedding
    embedding = get_story_embedding(text, model=model)
    if embedding is None:
        logger.warning(f"[SemanticDedup] Failed to generate embedding for {story_id}")
        return False

    # Add to index
    success = index.add(story_id, embedding)

    if success and save:
        index.save()

    return success


def get_similar_stories(
    story_data: dict,
    k: int = 5,
    index: Optional[StoryFaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> List[Tuple[str, float]]:
    """
    Find stories similar to the given story.

    Args:
        story_data: Story data dict (title, body, etc.)
        k: Number of similar stories to return
        index: FAISS index (uses global if not provided)
        model: Ollama model for embeddings

    Returns:
        List of (story_id, similarity_score) tuples
    """
    if not ENABLE_STORY_SEMANTIC_DEDUP:
        return []

    if index is None:
        index = get_story_index()

    if index.size == 0:
        return []

    # Extract text for embedding
    text = create_story_text_for_embedding(story_data)
    if not text:
        return []

    # Get embedding
    embedding = get_story_embedding(text, model=model)
    if embedding is None:
        return []

    # Get story ID for exclusion
    story_id = story_data.get("story_id") or story_data.get("id")

    return index.search(embedding, k=k, exclude_story_id=story_id)
