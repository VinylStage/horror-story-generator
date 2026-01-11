# Future Vector Backend

> **STATUS: TODO — Not implemented in Phase B**

This document outlines the planned vector embedding backend for semantic search and similarity computation. Implementation is deferred to a future phase.

## Current State (Phase B)

### Similarity Computation
- Uses canonical dimension matching only
- No semantic understanding
- Based on exact string matches of:
  - setting
  - primary_fear
  - antagonist
  - mechanism
  - twist

### Limitations
- Cannot detect thematic similarity
- Misses conceptual overlap
- No cross-lingual understanding

## Planned Vector Backend

### Purpose
Replace or augment canonical matching with embedding-based semantic similarity.

### Components (TODO)

```
research_integration/
├── vector_backend/
│   ├── __init__.py
│   ├── embedder.py        # Text → Vector conversion
│   ├── index.py           # Vector storage and search
│   ├── similarity.py      # Cosine/dot product similarity
│   └── config.py          # Model and index configuration
```

### Embedding Model Options (TODO)

| Model | Dimension | Language | Notes |
|-------|-----------|----------|-------|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | Multilingual | Good Korean support |
| `jhgan/ko-sroberta-multitask` | 768 | Korean | Korean-optimized |
| `intfloat/multilingual-e5-small` | 384 | Multilingual | Efficient |

### Index Backend Options (TODO)

| Backend | Pros | Cons |
|---------|------|------|
| FAISS | Fast, local | Requires installation |
| ChromaDB | Easy API | Additional dependency |
| SQLite + numpy | Minimal deps | Slower at scale |
| Qdrant | Production-ready | Heavier setup |

## Integration Points (TODO)

### Research Card Embedding
```python
# TODO: Future implementation
def embed_research_card(card: ResearchCard) -> np.ndarray:
    """
    Create embedding from research card content.

    Embeds:
    - title
    - summary
    - key_concepts (joined)
    - horror_applications (joined)
    """
    pass
```

### Similarity Search
```python
# TODO: Future implementation
def find_similar_cards(query_embedding: np.ndarray, k: int = 5) -> List[ResearchCard]:
    """
    Find k most similar research cards.
    """
    pass
```

### Story Deduplication
```python
# TODO: Future implementation
def compute_story_similarity(new_story: str, existing_stories: List[str]) -> float:
    """
    Compute semantic similarity between stories.
    """
    pass
```

## Migration Path

### Phase B (Current)
- Canonical matching only
- No embeddings

### Phase C (Planned)
- Add embedding generation on research card creation
- Store embeddings in JSON sidecar or SQLite
- Hybrid similarity: canonical + embedding

### Phase D (Future)
- Full vector index
- Fast k-NN search
- Embedding-based deduplication

## Technical Considerations (TODO)

### Embedding Storage
```json
{
  "card_id": "RC-20260111-143052",
  "embedding": [0.123, -0.456, ...],
  "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
  "embedded_at": "2026-01-11T14:31:00"
}
```

### Index Persistence
- JSONL for small scale (< 1000 cards)
- SQLite for medium scale (1000-10000)
- Dedicated vector DB for large scale (> 10000)

### Incremental Updates
- New cards embedded on creation
- Re-embedding on model change
- Batch re-indexing command

## Dependencies (TODO)

```txt
# requirements-vector.txt (future)
sentence-transformers>=2.2.0
numpy>=1.21.0
faiss-cpu>=1.7.0  # or chromadb>=0.4.0
```

## Non-Goals

The vector backend will NOT:
- Replace canonical matching entirely
- Require GPU for inference
- Block generation on embedding failure
- Store embeddings remotely

---

**Implementation Status: NOT STARTED**

This document serves as a design reference for future implementation. No code changes are required for Phase B.
