"""
Tests for story semantic deduplication.

v1.4.0: Tests for embedding-based story dedup and hybrid scoring.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile


class TestStoryTextForEmbedding:
    """Test story text extraction for embedding."""

    def test_create_story_text_basic(self):
        """Test basic text extraction from story data."""
        from src.dedup.story.embedder import create_story_text_for_embedding

        story_data = {
            "title": "The Haunted Apartment",
            "semantic_summary": "A story about a haunted apartment in Seoul",
            "body": "It was a dark night when the door opened by itself...",
        }

        text = create_story_text_for_embedding(story_data)

        assert "Title: The Haunted Apartment" in text
        assert "Summary: A story about a haunted apartment" in text
        assert "Content:" in text

    def test_create_story_text_with_canonical_core(self):
        """Test text extraction includes canonical core."""
        from src.dedup.story.embedder import create_story_text_for_embedding

        story_data = {
            "title": "Test Story",
            "canonical_core": {
                "setting_archetype": "apartment",
                "primary_fear": "isolation",
                "antagonist_archetype": "ghost",
            },
        }

        text = create_story_text_for_embedding(story_data)

        assert "Core:" in text
        assert "setting=apartment" in text
        assert "fear=isolation" in text

    def test_create_story_text_truncation(self):
        """Test that long body is truncated."""
        from src.dedup.story.embedder import create_story_text_for_embedding

        long_body = "A" * 5000
        story_data = {
            "title": "Test",
            "body": long_body,
        }

        text = create_story_text_for_embedding(story_data, max_body_chars=100)

        # Should be truncated with ellipsis
        assert "..." in text
        assert len(text) < len(long_body)

    def test_create_story_text_empty(self):
        """Test handling of empty story data."""
        from src.dedup.story.embedder import create_story_text_for_embedding

        text = create_story_text_for_embedding({})
        assert text == ""


class TestStoryFaissIndex:
    """Test story FAISS index functionality."""

    def test_index_initialization(self):
        """Test index can be initialized."""
        from src.dedup.story.index import StoryFaissIndex, is_faiss_available

        # Just test initialization - may or may not have FAISS
        index = StoryFaissIndex()
        assert index.size == 0

    def test_index_add_and_search(self):
        """Test adding and searching embeddings."""
        from src.dedup.story.index import StoryFaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index = StoryFaissIndex(
                index_path=index_path,
                metadata_path=metadata_path,
                dimension=4  # Small dimension for testing
            )

            # Add test embeddings
            embedding1 = [1.0, 0.0, 0.0, 0.0]
            embedding2 = [0.9, 0.1, 0.0, 0.0]  # Similar to 1
            embedding3 = [0.0, 0.0, 0.0, 1.0]  # Different

            assert index.add("story-1", embedding1)
            assert index.add("story-2", embedding2)
            assert index.add("story-3", embedding3)
            assert index.size == 3

            # Search for similar to embedding1
            results = index.search(embedding1, k=2)
            assert len(results) == 2
            # story-1 should be first (exact match)
            assert results[0][0] == "story-1"

    def test_index_persistence(self):
        """Test index save and load."""
        from src.dedup.story.index import StoryFaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            # Create and populate index
            index1 = StoryFaissIndex(
                index_path=index_path,
                metadata_path=metadata_path,
                dimension=4
            )
            index1.add("story-1", [1.0, 0.0, 0.0, 0.0])
            index1.save()

            # Load in new instance
            index2 = StoryFaissIndex(
                index_path=index_path,
                metadata_path=metadata_path,
            )

            assert index2.size == 1
            assert index2.contains("story-1")


class TestSemanticDedup:
    """Test semantic deduplication logic."""

    def test_dedup_signal_levels(self):
        """Test dedup signal level determination."""
        from src.dedup.story.semantic_dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.5) == DedupSignal.LOW
        assert get_dedup_signal(0.75) == DedupSignal.MEDIUM
        assert get_dedup_signal(0.9) == DedupSignal.HIGH

    def test_semantic_dedup_result_to_dict(self):
        """Test SemanticDedupResult serialization."""
        from src.dedup.story.semantic_dedup import SemanticDedupResult, DedupSignal

        result = SemanticDedupResult(
            similarity_score=0.85,
            nearest_story_id="story-123",
            signal=DedupSignal.HIGH,
        )

        d = result.to_dict()
        assert d["similarity_score"] == 0.85
        assert d["nearest_story_id"] == "story-123"
        assert d["signal"] == "HIGH"
        assert d["is_duplicate"] is True

    @patch("src.dedup.story.semantic_dedup.get_story_index")
    @patch("src.dedup.story.semantic_dedup.get_story_embedding")
    def test_check_semantic_duplicate_empty_index(self, mock_embedding, mock_index):
        """Test semantic check with empty index."""
        from src.dedup.story.semantic_dedup import check_semantic_duplicate, DedupSignal

        mock_index_instance = MagicMock()
        mock_index_instance.size = 0
        mock_index.return_value = mock_index_instance

        story_data = {"title": "Test", "body": "Test content"}
        result = check_semantic_duplicate(story_data)

        assert result.signal == DedupSignal.LOW
        assert result.similarity_score == 0.0
        assert result.nearest_story_id is None


class TestHybridDedup:
    """Test hybrid deduplication logic."""

    def test_compute_hybrid_score(self):
        """Test hybrid score computation."""
        from src.dedup.story.hybrid_dedup import compute_hybrid_score

        # 30% canonical + 70% semantic (default weights)
        score = compute_hybrid_score(
            canonical_score=1.0,
            semantic_score=0.5,
            canonical_weight=0.3,
            semantic_weight=0.7,
        )

        expected = (1.0 * 0.3) + (0.5 * 0.7)  # 0.3 + 0.35 = 0.65
        assert abs(score - expected) < 0.001

    def test_compute_hybrid_score_canonical_only(self):
        """Test hybrid score with canonical match only."""
        from src.dedup.story.hybrid_dedup import compute_hybrid_score

        # Canonical match, no semantic similarity
        score = compute_hybrid_score(
            canonical_score=1.0,
            semantic_score=0.0,
        )

        # Should be 0.3 (30% of 1.0)
        assert score > 0.2 and score < 0.5

    def test_compute_hybrid_score_semantic_only(self):
        """Test hybrid score with semantic similarity only."""
        from src.dedup.story.hybrid_dedup import compute_hybrid_score

        # No canonical match, high semantic similarity
        score = compute_hybrid_score(
            canonical_score=0.0,
            semantic_score=0.9,
        )

        # Should be 0.63 (70% of 0.9)
        assert score > 0.5 and score < 0.7

    def test_hybrid_result_to_dict(self):
        """Test HybridDedupResult serialization."""
        from src.dedup.story.hybrid_dedup import HybridDedupResult
        from src.dedup.story.semantic_dedup import DedupSignal

        result = HybridDedupResult(
            canonical_match=False,
            canonical_score=0.0,
            semantic_score=0.85,
            hybrid_score=0.595,
            signal=DedupSignal.MEDIUM,
            is_duplicate=False,
            nearest_story_id="story-456",
            matching_story_id=None,
        )

        d = result.to_dict()
        assert d["canonical_match"] is False
        assert d["semantic_score"] == 0.85
        assert d["hybrid_score"] == 0.595
        assert d["signal"] == "MEDIUM"


class TestStoryDedupCheckHybrid:
    """Test hybrid story dedup check integration."""

    def test_check_story_duplicate_hybrid_signature_only(self):
        """Test hybrid check falls back to signature when semantic disabled."""
        from src.story.dedup.story_dedup_check import check_story_duplicate_hybrid

        with patch(
            "src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP",
            False
        ):
            result = check_story_duplicate_hybrid(
                canonical_core={"setting_archetype": "apartment"},
                research_used=["RC-001"],
                story_data={"title": "Test"},
                registry=None,
            )

            assert result.signature != ""
            assert result.semantic_score == 0.0

    def test_story_dedup_result_to_dict_with_semantic(self):
        """Test StoryDedupResult includes semantic fields."""
        from src.story.dedup.story_dedup_check import StoryDedupResult

        result = StoryDedupResult(
            signature="abc123",
            is_duplicate=True,
            semantic_score=0.85,
            hybrid_score=0.75,
            nearest_story_id="story-789",
        )

        d = result.to_dict()
        assert "semantic_similarity_score" in d
        assert d["semantic_similarity_score"] == 0.85
        assert "hybrid_dedup_score" in d
        assert d["hybrid_dedup_score"] == 0.75
        assert d["nearest_story_id"] == "story-789"


class TestDataPaths:
    """Test data path configuration for story vectors."""

    def test_story_vector_paths_exist(self):
        """Test story vector path functions exist and return paths."""
        from src.infra.data_paths import (
            get_story_vectors_dir,
            get_story_faiss_index_path,
            get_story_vector_metadata_path,
        )

        assert get_story_vectors_dir().name == "story_vectors"
        assert get_story_faiss_index_path().name == "story.faiss"
        assert get_story_vector_metadata_path().name == "metadata.json"

    def test_story_vectors_in_all_paths(self):
        """Test story vectors included in get_all_paths()."""
        from src.infra.data_paths import get_all_paths

        paths = get_all_paths()
        assert "story_vectors" in paths
        assert "root" in paths["story_vectors"]
        assert "faiss_index" in paths["story_vectors"]
        assert "metadata" in paths["story_vectors"]
