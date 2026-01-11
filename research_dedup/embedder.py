"""
Embedding generation via Ollama local models.

Phase B+: Uses Ollama's embedding API for semantic vectors.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional

logger = logging.getLogger("horror_story_generator")

# Default Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_ENDPOINT = "/api/embed"

# Default embedding model
# Note: qwen3:30b supports embeddings via Ollama
DEFAULT_EMBED_MODEL = "qwen3:30b"

# Embedding dimension (will be detected from first embedding)
_embedding_dim: Optional[int] = None


class OllamaEmbedder:
    """
    Embedding generator using Ollama local models.

    Supports any Ollama model that can generate embeddings.
    """

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = 120
    ):
        """
        Initialize the embedder.

        Args:
            model: Ollama model name for embeddings
            base_url: Ollama API base URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._dimension: Optional[int] = None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector), or None on failure
        """
        if not text or not text.strip():
            logger.warning("[Embedder] Empty text provided")
            return None

        url = f"{self.base_url}{OLLAMA_EMBED_ENDPOINT}"

        payload = {
            "model": self.model,
            "input": text.strip()
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Ollama returns embeddings in 'embeddings' field (array of arrays)
            embeddings = result.get("embeddings", [])
            if not embeddings:
                # Fallback: try 'embedding' field (single vector)
                embedding = result.get("embedding", [])
                if embedding:
                    embeddings = [embedding]

            if embeddings and len(embeddings) > 0:
                embedding = embeddings[0]
                self._dimension = len(embedding)
                logger.debug(f"[Embedder] Generated embedding: dim={self._dimension}")
                return embedding

            logger.error(f"[Embedder] No embedding in response: {result}")
            return None

        except urllib.error.URLError as e:
            logger.error(f"[Embedder] Ollama connection failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"[Embedder] Invalid JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"[Embedder] Embedding generation failed: {e}")
            return None

    def get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (None for failed items)
        """
        results = []
        for text in texts:
            embedding = self.get_embedding(text)
            results.append(embedding)
        return results

    @property
    def dimension(self) -> Optional[int]:
        """Get embedding dimension (detected from first successful embedding)."""
        return self._dimension

    def is_available(self) -> bool:
        """Check if Ollama is available and model is loaded."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in result.get("models", [])]
                return self.model in models or any(self.model in m for m in models)
        except Exception:
            return False


# Global embedder instance
_embedder: Optional[OllamaEmbedder] = None


def get_embedder(model: str = DEFAULT_EMBED_MODEL) -> OllamaEmbedder:
    """
    Get or create global embedder instance.

    Args:
        model: Ollama model name

    Returns:
        OllamaEmbedder instance
    """
    global _embedder
    if _embedder is None or _embedder.model != model:
        _embedder = OllamaEmbedder(model=model)
    return _embedder


def get_embedding(text: str, model: str = DEFAULT_EMBED_MODEL) -> Optional[List[float]]:
    """
    Convenience function to get embedding for text.

    Args:
        text: Text to embed
        model: Ollama model name

    Returns:
        Embedding vector or None
    """
    embedder = get_embedder(model)
    return embedder.get_embedding(text)


def create_card_text_for_embedding(card_data: dict) -> str:
    """
    Create text representation of research card for embedding.

    Combines key fields into a single text for semantic comparison.

    Args:
        card_data: Research card JSON data

    Returns:
        Combined text for embedding
    """
    parts = []

    # Input topic
    if "input" in card_data:
        topic = card_data["input"].get("topic", "")
        if topic:
            parts.append(f"Topic: {topic}")

    # Output fields
    if "output" in card_data:
        output = card_data["output"]

        title = output.get("title", "")
        if title:
            parts.append(f"Title: {title}")

        summary = output.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary}")

        concepts = output.get("key_concepts", [])
        if concepts:
            parts.append(f"Concepts: {', '.join(concepts)}")

        applications = output.get("horror_applications", [])
        if applications:
            parts.append(f"Applications: {'; '.join(applications)}")

    return "\n".join(parts)
