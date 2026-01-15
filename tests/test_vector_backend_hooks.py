"""
Tests for vector backend hooks.

Issue #27: Tests for embedding generation, vector search, and clustering.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np


class TestVectorBackendStatus:
    """Test vector backend status reporting."""

    def test_get_status_returns_dict(self):
        """Test status returns expected structure."""
        from src.research.integration.vector_backend_hooks import (
            get_vector_backend_status
        )

        status = get_vector_backend_status()

        assert isinstance(status, dict)
        assert "vector_backend_enabled" in status
        assert "vector_backend_available" in status
        assert "features" in status
        assert isinstance(status["features"], dict)

    def test_status_features_keys(self):
        """Test all expected feature keys are present."""
        from src.research.integration.vector_backend_hooks import (
            get_vector_backend_status
        )

        status = get_vector_backend_status()
        features = status["features"]

        expected_keys = [
            "embedding_generation",
            "vector_search",
            "semantic_affinity",
            "clustering",
            "card_indexing",
        ]
        for key in expected_keys:
            assert key in features


class TestGenerateEmbedding:
    """Test embedding generation."""

    def test_empty_text_returns_none(self):
        """Test empty text returns None."""
        from src.research.integration.vector_backend_hooks import generate_embedding

        assert generate_embedding("") is None
        assert generate_embedding("   ") is None

    @patch("src.research.integration.vector_backend_hooks._get_embedder")
    def test_embedding_success(self, mock_get_embedder):
        """Test successful embedding generation."""
        from src.research.integration.vector_backend_hooks import generate_embedding

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.get_embedding.return_value = [0.1] * 768
        mock_get_embedder.return_value = mock_embedder

        result = generate_embedding("test text")

        assert result is not None
        assert len(result) == 768
        mock_embedder.get_embedding.assert_called_once()

    @patch("src.research.integration.vector_backend_hooks._get_embedder")
    def test_embedding_failure_returns_none(self, mock_get_embedder):
        """Test embedding failure returns None."""
        from src.research.integration.vector_backend_hooks import generate_embedding

        mock_embedder = MagicMock()
        mock_embedder.get_embedding.return_value = None
        mock_get_embedder.return_value = mock_embedder

        result = generate_embedding("test text")
        assert result is None

    @patch("src.research.integration.vector_backend_hooks.VECTOR_BACKEND_ENABLED", False)
    def test_disabled_returns_none(self):
        """Test disabled backend returns None."""
        from src.research.integration.vector_backend_hooks import generate_embedding

        # Need to reload the module to pick up the patched value
        result = generate_embedding("test text")
        # When disabled, should return None
        assert result is None


class TestVectorSearch:
    """Test vector search functionality."""

    def test_empty_embedding_returns_empty(self):
        """Test empty embedding returns empty list."""
        from src.research.integration.vector_backend_hooks import (
            vector_search_research_cards
        )

        assert vector_search_research_cards([]) == []
        assert vector_search_research_cards(None) == []

    @patch("src.research.integration.vector_backend_hooks._get_index")
    def test_empty_index_returns_empty(self, mock_get_index):
        """Test search on empty index returns empty."""
        from src.research.integration.vector_backend_hooks import (
            vector_search_research_cards
        )

        mock_index = MagicMock()
        mock_index.size = 0
        mock_get_index.return_value = mock_index

        result = vector_search_research_cards([0.1] * 768, top_k=5)
        assert result == []

    @patch("src.research.integration.vector_backend_hooks._get_index")
    def test_search_returns_formatted_results(self, mock_get_index):
        """Test search returns properly formatted results."""
        from src.research.integration.vector_backend_hooks import (
            vector_search_research_cards
        )

        mock_index = MagicMock()
        mock_index.size = 10
        mock_index.search.return_value = [
            ("RC-001", 0.95),
            ("RC-002", 0.85),
        ]
        mock_get_index.return_value = mock_index

        result = vector_search_research_cards([0.1] * 768, top_k=5)

        assert len(result) == 2
        assert result[0]["card_id"] == "RC-001"
        assert result[0]["similarity_score"] == 0.95
        assert result[1]["card_id"] == "RC-002"


class TestIndexResearchCard:
    """Test research card indexing."""

    def test_missing_card_id_returns_false(self):
        """Test missing card_id returns False."""
        from src.research.integration.vector_backend_hooks import index_research_card

        assert index_research_card("", "content", {}) is False
        assert index_research_card(None, "content", {}) is False

    def test_missing_content_returns_false(self):
        """Test missing content returns False."""
        from src.research.integration.vector_backend_hooks import index_research_card

        assert index_research_card("RC-001", "", {}) is False
        assert index_research_card("RC-001", None, {}) is False

    @patch("src.research.integration.vector_backend_hooks._get_index")
    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_successful_indexing(self, mock_gen_embed, mock_get_index):
        """Test successful card indexing."""
        from src.research.integration.vector_backend_hooks import index_research_card

        mock_gen_embed.return_value = [0.1] * 768
        mock_index = MagicMock()
        mock_index.add.return_value = True
        mock_get_index.return_value = mock_index

        result = index_research_card("RC-001", "test content", {"tag": "horror"})

        assert result is True
        mock_index.add.assert_called_once()
        mock_index.save.assert_called_once()


class TestSemanticAffinity:
    """Test semantic affinity computation."""

    def test_empty_inputs_return_zero(self):
        """Test empty inputs return 0.0."""
        from src.research.integration.vector_backend_hooks import (
            compute_semantic_affinity
        )

        assert compute_semantic_affinity({}, "content") == 0.0
        assert compute_semantic_affinity({"key": "value"}, "") == 0.0

    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_affinity_calculation(self, mock_gen_embed):
        """Test affinity calculation between template and research."""
        from src.research.integration.vector_backend_hooks import (
            compute_semantic_affinity
        )

        # Create two similar embeddings
        template_embed = [1.0, 0.0, 0.0, 0.0]
        research_embed = [0.9, 0.1, 0.0, 0.0]

        mock_gen_embed.side_effect = [template_embed, research_embed]

        template_canonical = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
        }

        score = compute_semantic_affinity(template_canonical, "test research content")

        # Should be high similarity (close to 1.0)
        assert score > 0.9

    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_dissimilar_returns_lower_score(self, mock_gen_embed):
        """Test dissimilar content returns lower score."""
        from src.research.integration.vector_backend_hooks import (
            compute_semantic_affinity
        )

        # Create orthogonal embeddings
        template_embed = [1.0, 0.0, 0.0, 0.0]
        research_embed = [0.0, 1.0, 0.0, 0.0]

        mock_gen_embed.side_effect = [template_embed, research_embed]

        template_canonical = {"setting_archetype": "hospital"}
        score = compute_semantic_affinity(template_canonical, "different content")

        # Should be zero (orthogonal vectors)
        assert score == 0.0


class TestClusterResearchCards:
    """Test research card clustering."""

    def test_empty_cards_returns_empty(self):
        """Test empty cards list returns empty dict."""
        from src.research.integration.vector_backend_hooks import cluster_research_cards

        assert cluster_research_cards([]) == {}
        assert cluster_research_cards(None) == {}

    def test_too_few_cards_returns_empty(self):
        """Test too few cards returns empty dict."""
        from src.research.integration.vector_backend_hooks import cluster_research_cards

        cards = [{"card_id": "RC-001"}]
        result = cluster_research_cards(cards, n_clusters=5)
        assert result == {}

    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_clustering_with_mocked_embeddings(self, mock_gen_embed):
        """Test clustering with mocked embeddings."""
        from src.research.integration.vector_backend_hooks import cluster_research_cards

        # Create 6 cards with distinct embeddings
        cards = []
        embeddings = []
        for i in range(6):
            cards.append({
                "card_id": f"RC-{i:03d}",
                "input": {"topic": f"Topic {i}"},
                "output": {"title": f"Title {i}", "summary": f"Summary {i}"},
            })
            # Create embeddings in 2 clusters
            if i < 3:
                embeddings.append([1.0, 0.0, 0.0, 0.0])
            else:
                embeddings.append([0.0, 1.0, 0.0, 0.0])

        mock_gen_embed.side_effect = embeddings

        result = cluster_research_cards(cards, n_clusters=2)

        # Should have 2 clusters
        assert len(result) == 2
        # Total cards should be 6
        total_cards = sum(len(v) for v in result.values())
        assert total_cards == 6


class TestKMeansHelpers:
    """Test k-means helper functions."""

    def test_kmeans_plusplus_init(self):
        """Test k-means++ initialization."""
        from src.research.integration.vector_backend_hooks import _kmeans_plusplus_init

        # Create simple test data
        X = np.array([
            [1.0, 0.0],
            [1.0, 0.1],
            [0.0, 1.0],
            [0.1, 1.0],
        ], dtype=np.float32)

        centroids = _kmeans_plusplus_init(X, 2)

        assert centroids.shape == (2, 2)
        # Centroids should be different
        assert not np.allclose(centroids[0], centroids[1])

    def test_compute_distances(self):
        """Test distance computation."""
        from src.research.integration.vector_backend_hooks import _compute_distances

        X = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
        ], dtype=np.float32)

        centroids = np.array([
            [1.0, 0.0],
        ], dtype=np.float32)

        distances = _compute_distances(X, centroids)

        assert distances.shape == (2, 1)
        # First point should be at distance 0 from centroid
        assert distances[0, 0] == 0.0
        # Second point should be at distance 2 (squared Euclidean)
        assert distances[1, 0] == 2.0


class TestSearchSimilarCards:
    """Test convenience search function."""

    @patch("src.research.integration.vector_backend_hooks.vector_search_research_cards")
    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_search_similar_cards(self, mock_gen_embed, mock_search):
        """Test search_similar_cards convenience function."""
        from src.research.integration.vector_backend_hooks import search_similar_cards

        mock_gen_embed.return_value = [0.1] * 768
        mock_search.return_value = [{"card_id": "RC-001", "similarity_score": 0.9}]

        result = search_similar_cards("test query", top_k=3)

        assert len(result) == 1
        assert result[0]["card_id"] == "RC-001"
        mock_gen_embed.assert_called_once_with("test query")
        mock_search.assert_called_once()

    @patch("src.research.integration.vector_backend_hooks.generate_embedding")
    def test_search_with_no_embedding_returns_empty(self, mock_gen_embed):
        """Test search returns empty when embedding fails."""
        from src.research.integration.vector_backend_hooks import search_similar_cards

        mock_gen_embed.return_value = None

        result = search_similar_cards("test query")
        assert result == []


class TestInitVectorBackend:
    """Test vector backend initialization."""

    @patch("src.research.integration.vector_backend_hooks.VECTOR_BACKEND_ENABLED", False)
    def test_disabled_returns_false(self):
        """Test disabled backend returns False."""
        from src.research.integration.vector_backend_hooks import init_vector_backend

        result = init_vector_backend()
        assert result is False

    @patch("src.research.integration.vector_backend_hooks._get_index")
    @patch("src.research.integration.vector_backend_hooks._is_faiss_available")
    @patch("src.research.integration.vector_backend_hooks._get_embedder")
    @patch("src.research.integration.vector_backend_hooks._initialized", False)
    def test_successful_initialization(
        self, mock_get_embedder, mock_faiss_avail, mock_get_index
    ):
        """Test successful initialization."""
        from src.research.integration.vector_backend_hooks import init_vector_backend

        mock_embedder = MagicMock()
        mock_embedder.is_available.return_value = True
        mock_embedder.model = "nomic-embed-text"
        mock_get_embedder.return_value = mock_embedder

        mock_faiss_avail.return_value = True

        mock_index = MagicMock()
        mock_index.size = 0
        mock_get_index.return_value = mock_index

        result = init_vector_backend()

        # Should succeed
        assert result is True

    @patch("src.research.integration.vector_backend_hooks._get_embedder")
    @patch("src.research.integration.vector_backend_hooks._initialized", False)
    def test_embedder_unavailable_returns_false(self, mock_get_embedder):
        """Test unavailable embedder returns False."""
        from src.research.integration.vector_backend_hooks import init_vector_backend

        mock_embedder = MagicMock()
        mock_embedder.is_available.return_value = False
        mock_get_embedder.return_value = mock_embedder

        result = init_vector_backend()
        assert result is False
