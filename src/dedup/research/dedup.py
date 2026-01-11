"""
Deduplication logic for research cards.

Phase B+: Semantic similarity checking with configurable thresholds.

IMPORTANT: High similarity does NOT block research.
It only provides a signal for the caller to decide.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from .embedder import get_embedding, create_card_text_for_embedding, DEFAULT_EMBED_MODEL
from .index import get_index, FaissIndex

logger = logging.getLogger("horror_story_generator")


class DedupSignal(Enum):
    """
    Deduplication signal levels.

    LOW: Similarity < 0.7 - Card is likely unique
    MEDIUM: 0.7 <= Similarity < 0.85 - Some overlap, worth noting
    HIGH: Similarity >= 0.85 - Very similar to existing card
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# Threshold configuration
THRESHOLD_MEDIUM = 0.70  # Below this = LOW
THRESHOLD_HIGH = 0.85    # Above or equal = HIGH


@dataclass
class DedupResult:
    """
    Result of deduplication check.

    Attributes:
        similarity_score: Cosine similarity (0.0 to 1.0)
        nearest_card_id: ID of the most similar existing card (None if index empty)
        signal: Deduplication signal level
        is_duplicate: True if signal is HIGH (convenience flag)
    """
    similarity_score: float
    nearest_card_id: Optional[str]
    signal: DedupSignal

    @property
    def is_duplicate(self) -> bool:
        """Check if this is a high-similarity duplicate."""
        return self.signal == DedupSignal.HIGH

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "similarity_score": round(self.similarity_score, 4),
            "nearest_card_id": self.nearest_card_id,
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


def check_duplicate(
    card_data: dict,
    index: Optional[FaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> DedupResult:
    """
    Check if a research card is a semantic duplicate of existing cards.

    This function:
    1. Extracts text from card data
    2. Generates embedding via Ollama
    3. Searches FAISS index for similar cards
    4. Returns similarity score and signal level

    IMPORTANT: This NEVER blocks. It only provides information.

    Args:
        card_data: Research card JSON data
        index: FAISS index to search (uses global if not provided)
        model: Ollama model for embeddings

    Returns:
        DedupResult with similarity info
    """
    # Default result for failures
    default_result = DedupResult(
        similarity_score=0.0,
        nearest_card_id=None,
        signal=DedupSignal.LOW
    )

    # Get or create index
    if index is None:
        index = get_index()

    # If index is empty, nothing to compare
    if index.size == 0:
        logger.debug("[Dedup] Index empty - no comparison possible")
        return default_result

    # Extract text for embedding
    text = create_card_text_for_embedding(card_data)
    if not text:
        logger.warning("[Dedup] Empty text extracted from card")
        return default_result

    # Get embedding
    embedding = get_embedding(text, model=model)
    if embedding is None:
        logger.warning("[Dedup] Failed to generate embedding")
        return default_result

    # Get card ID for exclusion (if checking existing card)
    card_id = card_data.get("metadata", {}).get("card_id")

    # Find nearest card
    nearest = index.get_nearest(embedding, exclude_card_id=card_id)

    if nearest is None:
        logger.debug("[Dedup] No similar cards found")
        return default_result

    nearest_id, score = nearest
    signal = get_dedup_signal(score)

    result = DedupResult(
        similarity_score=score,
        nearest_card_id=nearest_id,
        signal=signal
    )

    logger.info(
        f"[Dedup] Similarity check: score={score:.4f}, "
        f"nearest={nearest_id}, signal={signal.value}"
    )

    return result


def add_card_to_index(
    card_data: dict,
    card_id: str,
    index: Optional[FaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL,
    save: bool = True
) -> bool:
    """
    Add a research card to the FAISS index.

    Should be called after a card is successfully created.

    Args:
        card_data: Research card JSON data
        card_id: Unique card identifier
        index: FAISS index (uses global if not provided)
        model: Ollama model for embeddings
        save: Whether to save index to disk after adding

    Returns:
        True if added successfully, False otherwise
    """
    # Get or create index
    if index is None:
        index = get_index()

    # Skip if already indexed
    if index.contains(card_id):
        logger.debug(f"[Dedup] Card already indexed: {card_id}")
        return True

    # Extract text for embedding
    text = create_card_text_for_embedding(card_data)
    if not text:
        logger.warning(f"[Dedup] Empty text for card {card_id}")
        return False

    # Get embedding
    embedding = get_embedding(text, model=model)
    if embedding is None:
        logger.warning(f"[Dedup] Failed to generate embedding for {card_id}")
        return False

    # Add to index
    success = index.add(card_id, embedding)

    if success and save:
        index.save()

    return success


def batch_index_cards(
    cards: List[dict],
    index: Optional[FaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> int:
    """
    Add multiple research cards to the index.

    Useful for initial index building from existing cards.

    Args:
        cards: List of research card data with card_id in metadata
        index: FAISS index (uses global if not provided)
        model: Ollama model for embeddings

    Returns:
        Number of successfully added cards
    """
    if index is None:
        index = get_index()

    added = 0
    for card in cards:
        card_id = card.get("metadata", {}).get("card_id")
        if not card_id:
            logger.warning("[Dedup] Card missing card_id in metadata")
            continue

        # Add without saving each time
        if add_card_to_index(card, card_id, index=index, model=model, save=False):
            added += 1

    # Save once at the end
    if added > 0:
        index.save()
        logger.info(f"[Dedup] Batch indexed {added}/{len(cards)} cards")

    return added


def get_similar_cards(
    card_data: dict,
    k: int = 5,
    index: Optional[FaissIndex] = None,
    model: str = DEFAULT_EMBED_MODEL
) -> List[tuple]:
    """
    Find cards similar to the given card.

    Args:
        card_data: Research card JSON data
        k: Number of similar cards to return
        index: FAISS index (uses global if not provided)
        model: Ollama model for embeddings

    Returns:
        List of (card_id, similarity_score) tuples
    """
    if index is None:
        index = get_index()

    if index.size == 0:
        return []

    # Extract text for embedding
    text = create_card_text_for_embedding(card_data)
    if not text:
        return []

    # Get embedding
    embedding = get_embedding(text, model=model)
    if embedding is None:
        return []

    # Get card ID for exclusion
    card_id = card_data.get("metadata", {}).get("card_id")

    return index.search(embedding, k=k, exclude_card_id=card_id)
