# Research Dedup Setup

**Date:** 2026-01-12
**Status:** ACTIVE

---

## Overview

The research deduplication system uses FAISS (Facebook AI Similarity Search) with Ollama embeddings to detect semantically similar research cards.

---

## Architecture

```mermaid
flowchart LR
    A["Research Card"] --> B["Embedder<br/>(Ollama)"]
    B --> C["FAISS Index"]
    C --> D["Similarity Score"]
    D --> E["Signal<br/>(LOW/MED/HIGH)"]
```

### Components

| Component | File | Description |
|-----------|------|-------------|
| Embedder | `src/dedup/research/embedder.py` | Generates embeddings via Ollama |
| FAISS Index | `src/dedup/research/index.py` | Stores and searches vectors |
| Dedup Logic | `src/dedup/research/dedup.py` | Orchestrates similarity checks |
| Vector Backend | `src/research/integration/vector_backend_hooks.py` | Unified vector operations (v1.4.0) |

---

## Ollama Model Requirements

### Embedding Model (Required)

```bash
# Install the embedding model
ollama pull nomic-embed-text
```

**Model Specifications:**
- Name: `nomic-embed-text`
- Embedding Dimension: 768
- API Endpoint: `/api/embed`

### Generation Model (Separate)

The research generation uses `qwen3:30b` for generating card content, which is separate from the embedding model.

```bash
# Generation model (already installed for research generation)
ollama pull qwen3:30b
```

---

## Configuration

### Default Settings (`src/dedup/research/embedder.py`)

```python
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_ENDPOINT = "/api/embed"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
```

### FAISS Index Settings (`src/dedup/research/index.py`)

```python
# Default embedding dimension (matches nomic-embed-text)
dimension: int = 768
```

---

## Signal Thresholds

| Signal | Similarity Score | Meaning |
|--------|-----------------|---------|
| `LOW` | < 0.70 | Unique content |
| `MEDIUM` | 0.70 - 0.85 | Some overlap |
| `HIGH` | ≥ 0.85 | High similarity (potential duplicate) |

---

## Usage

### Check Duplicate Before Research

```python
from src.dedup.research.dedup import check_duplicate

card_data = {
    "input": {"topic": "Korean apartment isolation horror"},
    "output": {"title": "...", "summary": "..."}
}

result = check_duplicate(card_data)
print(f"Signal: {result.signal.value}")
print(f"Similarity: {result.similarity_score:.4f}")
print(f"Nearest: {result.nearest_card_id}")
```

### Add Card to Index

```python
from src.dedup.research.dedup import add_card_to_index

success = add_card_to_index(card_data, card_id="RC-20260112-123456")
```

### Rebuild Index

```python
from src.dedup.research.index import get_index
from src.dedup.research.dedup import add_card_to_index
import json
from pathlib import Path

index = get_index()
for json_file in Path("data/research").glob("**/*.json"):
    card = json.load(open(json_file))
    add_card_to_index(card, card["card_id"], index=index, save=False)
index.save()
```

---

## Troubleshooting

### HTTP 501 Error

**Symptom:**
```
[Embedder] Ollama connection failed: HTTP Error 501: Not Implemented
```

**Cause:** Wrong model specified for embeddings. Generation models like `qwen3:30b` don't support the `/api/embed` endpoint.

**Solution:**
1. Install embedding model: `ollama pull nomic-embed-text`
2. Ensure `DEFAULT_EMBED_MODEL = "nomic-embed-text"` in embedder.py

### Empty Index After Rebuild

**Symptom:**
```
Rebuilt index with 0 cards (total: 0)
```

**Cause:** All embedding generations failed (usually due to wrong model).

**Solution:** Check Ollama is running and the correct model is configured.

### Test Embedder

```bash
# Test Ollama API directly
curl http://localhost:11434/api/embed -d '{
  "model": "nomic-embed-text",
  "input": "test embedding"
}'

# Test via Python
python -c "
from src.dedup.research.embedder import get_embedder
e = get_embedder()
print(f'Model: {e.model}')
print(f'Available: {e.is_available()}')
emb = e.get_embedding('test')
print(f'Dimension: {len(emb) if emb else None}')
"
```

---

## Index Storage

FAISS index files are stored in:
```
./data/research_index.faiss     # Vector index
./data/research_index_meta.json # Card ID mappings
```

---

## Vector Backend Hooks (v1.4.0)

The `vector_backend_hooks.py` module provides a unified interface for vector operations.

### Functions

| Function | Description |
|----------|-------------|
| `init_vector_backend()` | Initialize embedder and FAISS index |
| `generate_embedding(text)` | Generate embedding for text |
| `vector_search_research_cards(embedding, top_k)` | Search similar cards |
| `index_research_card(card_id, content, metadata)` | Add card to index |
| `compute_semantic_affinity(template_canonical, research_content)` | Compute template-research similarity |
| `cluster_research_cards(cards, n_clusters)` | K-means clustering on cards |

### Usage

```python
from src.research.integration import (
    init_vector_backend,
    search_similar_cards,
    compute_semantic_affinity,
)

# Initialize
init_vector_backend()

# Search by text
results = search_similar_cards("Korean apartment horror", top_k=5)
for r in results:
    print(f"{r['card_id']}: {r['similarity_score']:.4f}")

# Compute template-research affinity
template_canonical = {"setting_archetype": "apartment", "primary_fear": "isolation"}
affinity = compute_semantic_affinity(template_canonical, "A story about urban isolation...")
print(f"Affinity: {affinity:.4f}")
```

### Configuration

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `VECTOR_BACKEND_ENABLED` | `true` | Enable vector backend |

---

## History

| Date | Change |
|------|--------|
| 2026-01-15 | Added vector backend hooks (v1.4.0) |
| 2026-01-12 | Fixed embedding model from qwen3:30b to nomic-embed-text |
| 2026-01-11 | Initial implementation with FAISS |

---

**Author:** Claude Code (Opus 4.5)
