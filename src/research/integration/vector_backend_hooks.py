"""
Vector Backend Hooks

This module provides vector-based semantic search capabilities for research cards.
Implements the hooks defined in Issue #27 using existing infrastructure:
- Ollama embeddings (nomic-embed-text)
- FAISS vector index

v1.4.0: Implemented using existing dedup infrastructure.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Feature Flags
# =============================================================================

# Enable via environment variable (default: true since we have infrastructure)
VECTOR_BACKEND_ENABLED = os.getenv(
    "VECTOR_BACKEND_ENABLED", "true"
).lower() == "true"

# Track initialization state
_initialized = False
_embedder = None
_index = None

# =============================================================================
# Lazy Imports (avoid circular imports)
# =============================================================================


def _get_embedder():
    """Lazy import and get embedder instance."""
    global _embedder
    if _embedder is None:
        try:
            from src.dedup.research.embedder import get_embedder
            _embedder = get_embedder()
        except ImportError as e:
            logger.warning(f"[VectorBackend] Embedder import failed: {e}")
            return None
    return _embedder


def _get_index():
    """Lazy import and get FAISS index instance."""
    global _index
    if _index is None:
        try:
            from src.dedup.research.index import get_index
            _index = get_index()
        except ImportError as e:
            logger.warning(f"[VectorBackend] Index import failed: {e}")
            return None
    return _index


def _is_faiss_available() -> bool:
    """Check if FAISS is available."""
    try:
        from src.dedup.research.index import is_faiss_available
        return is_faiss_available()
    except ImportError:
        return False


# =============================================================================
# Hook Implementations
# =============================================================================


def init_vector_backend() -> bool:
    """
    Initialize vector backend for semantic search.

    Uses existing Ollama embedder and FAISS index infrastructure.

    Returns:
        bool: True if backend initialized successfully
    """
    global _initialized

    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Vector backend disabled")
        return False

    if _initialized:
        return True

    try:
        # Check embedder availability
        embedder = _get_embedder()
        if embedder is None:
            logger.warning("[VectorBackend] Embedder not available")
            return False

        if not embedder.is_available():
            logger.warning("[VectorBackend] Ollama not running or model not loaded")
            return False

        # Check FAISS availability
        if not _is_faiss_available():
            logger.warning("[VectorBackend] FAISS not available")
            return False

        # Get index (creates if needed)
        index = _get_index()
        if index is None:
            logger.warning("[VectorBackend] Failed to initialize index")
            return False

        _initialized = True
        logger.info(
            f"[VectorBackend] Initialized: embedder={embedder.model}, "
            f"index_size={index.size}"
        )
        return True

    except Exception as e:
        logger.error(f"[VectorBackend] Initialization failed: {e}")
        return False


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding vector for text.

    Uses Ollama with nomic-embed-text model.

    Args:
        text: Text to embed

    Returns:
        List of floats (embedding vector) or None
    """
    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Embedding generation disabled")
        return None

    if not text or not text.strip():
        logger.warning("[VectorBackend] Empty text provided")
        return None

    try:
        embedder = _get_embedder()
        if embedder is None:
            return None

        embedding = embedder.get_embedding(text)
        if embedding:
            logger.debug(f"[VectorBackend] Generated embedding: dim={len(embedding)}")
        return embedding

    except Exception as e:
        logger.error(f"[VectorBackend] Embedding generation failed: {e}")
        return None


def vector_search_research_cards(
    query_embedding: List[float],
    top_k: int = 5,
    filter_criteria: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Search research cards using vector similarity.

    Uses FAISS index for fast similarity search.

    Args:
        query_embedding: Query embedding vector
        top_k: Number of results to return
        filter_criteria: Optional metadata filters (not yet implemented)

    Returns:
        List of matching research cards with similarity scores
    """
    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Vector search disabled")
        return []

    if not query_embedding:
        logger.warning("[VectorBackend] Empty query embedding")
        return []

    try:
        index = _get_index()
        if index is None:
            return []

        if index.size == 0:
            logger.debug("[VectorBackend] Index is empty")
            return []

        # Search FAISS index
        results = index.search(query_embedding, k=top_k)

        # Format results
        formatted_results = []
        for card_id, score in results:
            formatted_results.append({
                "card_id": card_id,
                "similarity_score": score,
            })

        logger.debug(f"[VectorBackend] Found {len(formatted_results)} results")

        # Note: filter_criteria not implemented yet
        if filter_criteria:
            logger.debug(
                "[VectorBackend] filter_criteria provided but not yet implemented"
            )

        return formatted_results

    except Exception as e:
        logger.error(f"[VectorBackend] Vector search failed: {e}")
        return []


def index_research_card(
    card_id: str,
    content: str,
    metadata: Dict[str, Any]
) -> bool:
    """
    Index a research card in the vector store.

    Generates embedding and adds to FAISS index.

    Args:
        card_id: Unique card identifier
        content: Text content to embed and index
        metadata: Additional metadata (stored separately, not in FAISS)

    Returns:
        bool: True if indexed successfully
    """
    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Card indexing disabled")
        return False

    if not card_id or not content:
        logger.warning("[VectorBackend] Missing card_id or content")
        return False

    try:
        # Generate embedding
        embedding = generate_embedding(content)
        if embedding is None:
            logger.warning(f"[VectorBackend] Failed to generate embedding for {card_id}")
            return False

        # Add to index
        index = _get_index()
        if index is None:
            return False

        success = index.add(card_id, embedding)
        if success:
            # Save index
            index.save()
            logger.info(f"[VectorBackend] Indexed card: {card_id}")

        return success

    except Exception as e:
        logger.error(f"[VectorBackend] Card indexing failed: {e}")
        return False


def compute_semantic_affinity(
    template_canonical: Dict[str, str],
    research_content: str
) -> float:
    """
    Compute semantic affinity between template and research.

    Uses embedding similarity between template description and research content.

    Args:
        template_canonical: Template's canonical_core
        research_content: Research card content

    Returns:
        float: Semantic affinity score (0.0 to 1.0)
    """
    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Semantic affinity disabled")
        return 0.0

    if not template_canonical or not research_content:
        return 0.0

    try:
        # Create template text from canonical dimensions
        template_parts = []
        for key, value in template_canonical.items():
            if value:
                # Convert snake_case to readable form
                readable_key = key.replace("_", " ")
                template_parts.append(f"{readable_key}: {value}")

        template_text = "; ".join(template_parts)
        if not template_text:
            return 0.0

        # Generate embeddings
        template_embedding = generate_embedding(template_text)
        research_embedding = generate_embedding(research_content)

        if template_embedding is None or research_embedding is None:
            return 0.0

        # Compute cosine similarity
        template_vec = np.array(template_embedding, dtype=np.float32)
        research_vec = np.array(research_embedding, dtype=np.float32)

        # Normalize
        template_norm = np.linalg.norm(template_vec)
        research_norm = np.linalg.norm(research_vec)

        if template_norm == 0 or research_norm == 0:
            return 0.0

        template_vec = template_vec / template_norm
        research_vec = research_vec / research_norm

        # Cosine similarity
        similarity = float(np.dot(template_vec, research_vec))

        # Clamp to [0, 1]
        similarity = max(0.0, min(1.0, similarity))

        logger.debug(
            f"[VectorBackend] Semantic affinity: {similarity:.4f}"
        )
        return similarity

    except Exception as e:
        logger.error(f"[VectorBackend] Semantic affinity failed: {e}")
        return 0.0


def cluster_research_cards(
    cards: List[Dict[str, Any]],
    n_clusters: int = 5
) -> Dict[int, List[str]]:
    """
    Cluster research cards by semantic similarity.

    Uses k-means clustering on card embeddings.

    Args:
        cards: List of research cards (must have 'card_id' and text content)
        n_clusters: Number of clusters to create

    Returns:
        Dict mapping cluster ID to list of card IDs
    """
    if not VECTOR_BACKEND_ENABLED:
        logger.debug("[VectorBackend] Clustering disabled")
        return {}

    if not cards or len(cards) < n_clusters:
        logger.warning(
            f"[VectorBackend] Not enough cards ({len(cards) if cards else 0}) "
            f"for {n_clusters} clusters"
        )
        return {}

    try:
        from src.dedup.research.embedder import create_card_text_for_embedding

        # Generate embeddings for all cards
        embeddings = []
        card_ids = []

        for card in cards:
            card_id = card.get("card_id") or card.get("id")
            if not card_id:
                continue

            # Create text for embedding
            text = create_card_text_for_embedding(card)
            if not text:
                continue

            embedding = generate_embedding(text)
            if embedding is None:
                continue

            embeddings.append(embedding)
            card_ids.append(card_id)

        if len(embeddings) < n_clusters:
            logger.warning(
                f"[VectorBackend] Only {len(embeddings)} valid embeddings, "
                f"need at least {n_clusters}"
            )
            return {}

        # Convert to numpy array
        X = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine distance
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        X = X / norms

        # Simple k-means implementation
        # (avoiding sklearn dependency, using numpy only)
        n_samples = len(X)
        actual_clusters = min(n_clusters, n_samples)

        # Initialize centroids using k-means++
        centroids = _kmeans_plusplus_init(X, actual_clusters)

        # Iterate
        max_iter = 100
        for _ in range(max_iter):
            # Assign points to nearest centroid
            distances = _compute_distances(X, centroids)
            labels = np.argmin(distances, axis=1)

            # Update centroids
            new_centroids = np.zeros_like(centroids)
            for k in range(actual_clusters):
                mask = labels == k
                if np.any(mask):
                    new_centroids[k] = X[mask].mean(axis=0)
                else:
                    new_centroids[k] = centroids[k]

            # Check convergence
            if np.allclose(centroids, new_centroids):
                break

            centroids = new_centroids

        # Build result dict
        clusters: Dict[int, List[str]] = {}
        for idx, label in enumerate(labels):
            cluster_id = int(label)
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(card_ids[idx])

        logger.info(
            f"[VectorBackend] Clustered {len(card_ids)} cards into "
            f"{len(clusters)} clusters"
        )
        return clusters

    except Exception as e:
        logger.error(f"[VectorBackend] Clustering failed: {e}")
        return {}


def _kmeans_plusplus_init(X: np.ndarray, n_clusters: int) -> np.ndarray:
    """Initialize centroids using k-means++."""
    n_samples = len(X)
    centroids = []

    # First centroid: random
    idx = np.random.randint(n_samples)
    centroids.append(X[idx])

    # Remaining centroids: probability proportional to distance^2
    for _ in range(1, n_clusters):
        distances = _compute_distances(X, np.array(centroids))
        min_distances = distances.min(axis=1)
        probs = min_distances ** 2
        probs = probs / probs.sum()
        idx = np.random.choice(n_samples, p=probs)
        centroids.append(X[idx])

    return np.array(centroids)


def _compute_distances(X: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Compute distances between points and centroids."""
    # Using squared Euclidean distance (equivalent to 1 - cosine for normalized vectors)
    # X: (n_samples, dim), centroids: (n_clusters, dim)
    # Result: (n_samples, n_clusters)
    distances = np.zeros((len(X), len(centroids)))
    for i, centroid in enumerate(centroids):
        diff = X - centroid
        distances[:, i] = np.sum(diff ** 2, axis=1)
    return distances


# =============================================================================
# Status Check
# =============================================================================


def get_vector_backend_status() -> Dict[str, Any]:
    """
    Get current vector backend feature status.

    Returns:
        Dict with feature availability information
    """
    embedder = _get_embedder()
    index = _get_index()

    embedder_available = embedder is not None and embedder.is_available()
    faiss_available = _is_faiss_available()

    return {
        "vector_backend_enabled": VECTOR_BACKEND_ENABLED,
        "vector_backend_available": embedder_available and faiss_available,
        "initialized": _initialized,
        "embedder": {
            "available": embedder_available,
            "model": embedder.model if embedder else None,
        },
        "index": {
            "available": faiss_available,
            "size": index.size if index else 0,
        },
        "features": {
            "embedding_generation": VECTOR_BACKEND_ENABLED and embedder_available,
            "vector_search": VECTOR_BACKEND_ENABLED and faiss_available,
            "semantic_affinity": VECTOR_BACKEND_ENABLED and embedder_available,
            "clustering": VECTOR_BACKEND_ENABLED and embedder_available,
            "card_indexing": (
                VECTOR_BACKEND_ENABLED and embedder_available and faiss_available
            ),
        },
    }


# =============================================================================
# Convenience Functions
# =============================================================================


def search_similar_cards(
    query_text: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for similar research cards by text query.

    Convenience function that generates embedding and searches.

    Args:
        query_text: Text to search for
        top_k: Number of results

    Returns:
        List of matching cards with similarity scores
    """
    embedding = generate_embedding(query_text)
    if embedding is None:
        return []

    return vector_search_research_cards(embedding, top_k=top_k)
