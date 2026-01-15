"""
Story text embedding generation.

Reuses the research embedder infrastructure for story semantic similarity.
"""

import logging
from typing import List, Optional

# Reuse research embedder infrastructure
from src.dedup.research.embedder import (
    get_embedder,
    get_embedding,
    get_embedding_async,
    DEFAULT_EMBED_MODEL,
)

logger = logging.getLogger("horror_story_generator")

# Maximum characters to include from story body (to limit embedding size)
MAX_BODY_CHARS = 2000


def create_story_text_for_embedding(
    story_data: dict,
    include_body: bool = True,
    max_body_chars: int = MAX_BODY_CHARS
) -> str:
    """
    Create text representation of a story for embedding.

    Combines key fields into a single text for semantic comparison.
    Prioritizes title, summary, and beginning of story body.

    Args:
        story_data: Story data dict with title, summary, body, etc.
        include_body: Whether to include story body text
        max_body_chars: Maximum characters from body to include

    Returns:
        Combined text for embedding
    """
    parts = []

    # Title (highest signal)
    title = story_data.get("title", "")
    if title:
        parts.append(f"Title: {title}")

    # Semantic summary (if available from metadata)
    summary = story_data.get("semantic_summary", "")
    if summary:
        parts.append(f"Summary: {summary}")

    # Template info (provides thematic context)
    template_name = story_data.get("template_name", "")
    if template_name:
        parts.append(f"Theme: {template_name}")

    # Canonical core (if available)
    canonical_core = story_data.get("canonical_core", {})
    if canonical_core:
        core_parts = []
        if "setting_archetype" in canonical_core:
            core_parts.append(f"setting={canonical_core['setting_archetype']}")
        if "primary_fear" in canonical_core:
            core_parts.append(f"fear={canonical_core['primary_fear']}")
        if "antagonist_archetype" in canonical_core:
            core_parts.append(f"antagonist={canonical_core['antagonist_archetype']}")
        if core_parts:
            parts.append(f"Core: {', '.join(core_parts)}")

    # Story body (truncated)
    if include_body:
        body = story_data.get("body", "") or story_data.get("content", "")
        if body:
            # Take beginning of story (most distinctive part)
            truncated = body[:max_body_chars]
            if len(body) > max_body_chars:
                truncated += "..."
            parts.append(f"Content: {truncated}")

    return "\n".join(parts)


def create_story_text_from_file(
    story_content: str,
    title: Optional[str] = None,
    max_body_chars: int = MAX_BODY_CHARS
) -> str:
    """
    Create embedding text from raw story file content.

    Useful when processing .md story files directly.

    Args:
        story_content: Raw story markdown content
        title: Optional title (extracted from content if not provided)
        max_body_chars: Maximum characters from body to include

    Returns:
        Combined text for embedding
    """
    parts = []

    # Extract title from first line if not provided
    if not title:
        lines = story_content.strip().split("\n")
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip()

    if title:
        parts.append(f"Title: {title}")

    # Include truncated content
    content = story_content[:max_body_chars]
    if len(story_content) > max_body_chars:
        content += "..."
    parts.append(f"Content: {content}")

    return "\n".join(parts)


def get_story_embedding(
    text: str,
    model: str = DEFAULT_EMBED_MODEL
) -> Optional[List[float]]:
    """
    Get embedding vector for story text.

    Args:
        text: Story text to embed
        model: Ollama model name for embeddings

    Returns:
        Embedding vector or None on failure
    """
    if not text or not text.strip():
        logger.warning("[StoryEmbedder] Empty text provided")
        return None

    embedding = get_embedding(text, model=model)

    if embedding:
        logger.debug(f"[StoryEmbedder] Generated embedding: dim={len(embedding)}")
    else:
        logger.warning("[StoryEmbedder] Failed to generate embedding")

    return embedding


async def get_story_embedding_async(
    text: str,
    model: str = DEFAULT_EMBED_MODEL
) -> Optional[List[float]]:
    """
    Get embedding vector for story text asynchronously.

    Args:
        text: Story text to embed
        model: Ollama model name for embeddings

    Returns:
        Embedding vector or None on failure
    """
    if not text or not text.strip():
        logger.warning("[StoryEmbedder] Empty text provided")
        return None

    embedding = await get_embedding_async(text, model=model)

    if embedding:
        logger.debug(f"[StoryEmbedder] Generated async embedding: dim={len(embedding)}")
    else:
        logger.warning("[StoryEmbedder] Failed to generate async embedding")

    return embedding
