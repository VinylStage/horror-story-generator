"""
Tests for research_dedup module.

Phase B+: FAISS-based semantic deduplication tests.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestDedupSignal:
    """Tests for DedupSignal enum."""

    def test_signal_values(self):
        """Should have correct signal values."""
        from src.dedup.research.dedup import DedupSignal

        assert DedupSignal.LOW.value == "LOW"
        assert DedupSignal.MEDIUM.value == "MEDIUM"
        assert DedupSignal.HIGH.value == "HIGH"


class TestGetDedupSignal:
    """Tests for get_dedup_signal function."""

    def test_low_signal_below_threshold(self):
        """Should return LOW for scores below 0.70."""
        from src.dedup.research.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.0) == DedupSignal.LOW
        assert get_dedup_signal(0.5) == DedupSignal.LOW
        assert get_dedup_signal(0.69) == DedupSignal.LOW

    def test_medium_signal_in_range(self):
        """Should return MEDIUM for scores 0.70-0.85."""
        from src.dedup.research.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.70) == DedupSignal.MEDIUM
        assert get_dedup_signal(0.75) == DedupSignal.MEDIUM
        assert get_dedup_signal(0.84) == DedupSignal.MEDIUM

    def test_high_signal_above_threshold(self):
        """Should return HIGH for scores >= 0.85."""
        from src.dedup.research.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.85) == DedupSignal.HIGH
        assert get_dedup_signal(0.90) == DedupSignal.HIGH
        assert get_dedup_signal(1.0) == DedupSignal.HIGH


class TestDedupResult:
    """Tests for DedupResult dataclass."""

    def test_create_result(self):
        """Should create DedupResult with correct fields."""
        from src.dedup.research.dedup import DedupResult, DedupSignal

        result = DedupResult(
            similarity_score=0.75,
            nearest_card_id="RC-2026-01-11-001",
            signal=DedupSignal.MEDIUM
        )

        assert result.similarity_score == 0.75
        assert result.nearest_card_id == "RC-2026-01-11-001"
        assert result.signal == DedupSignal.MEDIUM

    def test_is_duplicate_property(self):
        """Should correctly identify duplicates."""
        from src.dedup.research.dedup import DedupResult, DedupSignal

        low = DedupResult(0.5, None, DedupSignal.LOW)
        medium = DedupResult(0.75, "RC-001", DedupSignal.MEDIUM)
        high = DedupResult(0.90, "RC-002", DedupSignal.HIGH)

        assert low.is_duplicate is False
        assert medium.is_duplicate is False
        assert high.is_duplicate is True

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        from src.dedup.research.dedup import DedupResult, DedupSignal

        result = DedupResult(
            similarity_score=0.7512,
            nearest_card_id="RC-001",
            signal=DedupSignal.MEDIUM
        )

        d = result.to_dict()

        assert d["similarity_score"] == 0.7512
        assert d["nearest_card_id"] == "RC-001"
        assert d["signal"] == "MEDIUM"
        assert d["is_duplicate"] is False


class TestCreateCardTextForEmbedding:
    """Tests for create_card_text_for_embedding function."""

    def test_extracts_topic(self):
        """Should extract topic from card data."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Test Topic"}
        }

        result = create_card_text_for_embedding(card_data)
        assert "Topic: Test Topic" in result

    def test_extracts_output_fields(self):
        """Should extract output fields."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "output": {
                "title": "Test Title",
                "summary": "Test summary",
                "key_concepts": ["concept1", "concept2"],
                "horror_applications": ["app1", "app2"]
            }
        }

        result = create_card_text_for_embedding(card_data)

        assert "Title: Test Title" in result
        assert "Summary: Test summary" in result
        assert "Concepts: concept1, concept2" in result
        assert "Applications: app1; app2" in result

    def test_handles_empty_card(self):
        """Should handle empty card data."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        result = create_card_text_for_embedding({})
        assert result == ""

    def test_handles_partial_card(self):
        """Should handle partial card data."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Only Topic"}
        }

        result = create_card_text_for_embedding(card_data)
        assert "Topic: Only Topic" in result


class TestFaissIndex:
    """Tests for FaissIndex class."""

    def test_create_index(self):
        """Should create empty index."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        assert index.size == 0

    def test_add_vector(self):
        """Should add vector to index."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096

        success = index.add("RC-001", embedding)

        assert success is True
        assert index.size == 1
        assert index.contains("RC-001")

    def test_add_duplicate_skipped(self):
        """Should skip duplicate card IDs."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096

        index.add("RC-001", embedding)
        index.add("RC-001", embedding)  # Duplicate

        assert index.size == 1

    def test_search_empty_index(self):
        """Should return empty list for empty index."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096

        results = index.search(embedding)

        assert results == []

    def test_search_returns_results(self):
        """Should return search results."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()

        # Add some vectors
        index.add("RC-001", [1.0] + [0.0] * 4095)
        index.add("RC-002", [0.0, 1.0] + [0.0] * 4094)

        # Search for similar
        query = [1.0] + [0.0] * 4095
        results = index.search(query, k=2)

        assert len(results) > 0
        assert results[0][0] == "RC-001"  # Should be most similar

    def test_get_nearest(self):
        """Should get nearest card."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [1.0] + [0.0] * 4095)

        query = [1.0] + [0.0] * 4095
        result = index.get_nearest(query)

        assert result is not None
        assert result[0] == "RC-001"

    def test_save_and_load(self):
        """Should save and load index."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            # Create and save
            index1 = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            index1.add("RC-001", [0.1] * 4096)
            index1.save()

            # Load in new instance
            index2 = FaissIndex(index_path=index_path, metadata_path=metadata_path)

            assert index2.size == 1
            assert index2.contains("RC-001")

    def test_clear_index(self):
        """Should clear all indexed data."""
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        index.clear()

        assert index.size == 0
        assert not index.contains("RC-001")


class TestIsFaissAvailable:
    """Tests for is_faiss_available function."""

    def test_returns_boolean(self):
        """Should return boolean."""
        from src.dedup.research.index import is_faiss_available

        result = is_faiss_available()
        assert isinstance(result, bool)


class TestCheckDuplicate:
    """Tests for check_duplicate function."""

    def test_check_with_empty_index(self):
        """Should return LOW signal for empty index."""
        from src.dedup.research.dedup import check_duplicate, DedupSignal
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()  # Empty index
        card_data = {"input": {"topic": "Test"}, "output": {"title": "Title"}}

        result = check_duplicate(card_data, index=index)

        assert result.signal == DedupSignal.LOW
        assert result.similarity_score == 0.0
        assert result.nearest_card_id is None

    def test_check_with_empty_text(self):
        """Should return LOW signal for empty card text."""
        from src.dedup.research.dedup import check_duplicate, DedupSignal
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {}  # Empty card

        result = check_duplicate(card_data, index=index)

        assert result.signal == DedupSignal.LOW

    def test_check_with_embedding_failure(self):
        """Should return LOW signal when embedding fails."""
        from src.dedup.research.dedup import check_duplicate, DedupSignal
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {"input": {"topic": "Test"}}

        with patch("src.dedup.research.dedup.get_embedding", return_value=None):
            result = check_duplicate(card_data, index=index)

            assert result.signal == DedupSignal.LOW

    def test_check_finds_similar_card(self):
        """Should find similar card."""
        from src.dedup.research.dedup import check_duplicate, DedupSignal
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096
        index.add("RC-001", embedding)

        card_data = {"input": {"topic": "Test"}}

        with patch("src.dedup.research.dedup.get_embedding", return_value=embedding):
            result = check_duplicate(card_data, index=index)

            assert result.nearest_card_id == "RC-001"
            assert result.similarity_score > 0.0

    def test_check_excludes_self(self):
        """Should exclude self when card_id in metadata."""
        from src.dedup.research.dedup import check_duplicate
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096
        index.add("RC-001", embedding)
        index.add("RC-002", [0.2] * 4096)

        card_data = {
            "input": {"topic": "Test"},
            "metadata": {"card_id": "RC-001"}  # Exclude self
        }

        with patch("src.dedup.research.dedup.get_embedding", return_value=embedding):
            result = check_duplicate(card_data, index=index)

            # Should find RC-002, not RC-001 (self)
            if result.nearest_card_id:
                assert result.nearest_card_id == "RC-002"

    def test_check_no_nearest_found(self):
        """Should handle case when no nearest found."""
        from src.dedup.research.dedup import check_duplicate, DedupSignal
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {"input": {"topic": "Test"}, "metadata": {"card_id": "RC-001"}}

        with patch("src.dedup.research.dedup.get_embedding", return_value=[0.1] * 4096):
            # Mock get_nearest to return None
            with patch.object(index, "get_nearest", return_value=None):
                result = check_duplicate(card_data, index=index)

                assert result.signal == DedupSignal.LOW


class TestAddCardToIndex:
    """Tests for add_card_to_index function."""

    def test_add_card_success(self):
        """Should add card to index."""
        from src.dedup.research.dedup import add_card_to_index
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        card_data = {"input": {"topic": "Test"}, "output": {"title": "Title"}}
        embedding = [0.1] * 4096

        with patch("src.dedup.research.dedup.get_embedding", return_value=embedding):
            result = add_card_to_index(card_data, "RC-001", index=index, save=False)

            assert result is True
            assert index.contains("RC-001")

    def test_add_card_already_exists(self):
        """Should skip if card already indexed."""
        from src.dedup.research.dedup import add_card_to_index
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {"input": {"topic": "Test"}}

        # Should return True without calling get_embedding
        with patch("src.dedup.research.dedup.get_embedding") as mock_embed:
            result = add_card_to_index(card_data, "RC-001", index=index)

            assert result is True
            mock_embed.assert_not_called()

    def test_add_card_empty_text(self):
        """Should fail for empty card text."""
        from src.dedup.research.dedup import add_card_to_index
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        card_data = {}  # Empty card

        result = add_card_to_index(card_data, "RC-001", index=index)

        assert result is False

    def test_add_card_embedding_failure(self):
        """Should fail when embedding generation fails."""
        from src.dedup.research.dedup import add_card_to_index
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        card_data = {"input": {"topic": "Test"}}

        with patch("src.dedup.research.dedup.get_embedding", return_value=None):
            result = add_card_to_index(card_data, "RC-001", index=index)

            assert result is False

    def test_add_card_with_save(self):
        """Should save index after adding."""
        from src.dedup.research.dedup import add_card_to_index
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            card_data = {"input": {"topic": "Test"}}
            embedding = [0.1] * 4096

            with patch("src.dedup.research.dedup.get_embedding", return_value=embedding):
                result = add_card_to_index(card_data, "RC-001", index=index, save=True)

                assert result is True
                assert index_path.exists()


class TestBatchIndexCards:
    """Tests for batch_index_cards function."""

    def test_batch_index_success(self):
        """Should index multiple cards."""
        from src.dedup.research.dedup import batch_index_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            cards = [
                {"input": {"topic": "Test 1"}, "metadata": {"card_id": "RC-001"}},
                {"input": {"topic": "Test 2"}, "metadata": {"card_id": "RC-002"}},
                {"input": {"topic": "Test 3"}, "metadata": {"card_id": "RC-003"}},
            ]

            with patch("src.dedup.research.dedup.get_embedding", return_value=[0.1] * 4096):
                added = batch_index_cards(cards, index=index)

                assert added == 3
                assert index.size == 3

    def test_batch_index_missing_card_id(self):
        """Should skip cards without card_id."""
        from src.dedup.research.dedup import batch_index_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        cards = [
            {"input": {"topic": "Test 1"}, "metadata": {"card_id": "RC-001"}},
            {"input": {"topic": "Test 2"}, "metadata": {}},  # Missing card_id
            {"input": {"topic": "Test 3"}},  # No metadata
        ]

        with patch("src.dedup.research.dedup.get_embedding", return_value=[0.1] * 4096):
            added = batch_index_cards(cards, index=index)

            assert added == 1  # Only one with valid card_id

    def test_batch_index_empty_list(self):
        """Should handle empty list."""
        from src.dedup.research.dedup import batch_index_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        added = batch_index_cards([], index=index)

        assert added == 0


class TestGetSimilarCards:
    """Tests for get_similar_cards function."""

    def test_get_similar_empty_index(self):
        """Should return empty list for empty index."""
        from src.dedup.research.dedup import get_similar_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        card_data = {"input": {"topic": "Test"}}

        result = get_similar_cards(card_data, index=index)

        assert result == []

    def test_get_similar_empty_text(self):
        """Should return empty list for empty card text."""
        from src.dedup.research.dedup import get_similar_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {}  # Empty

        result = get_similar_cards(card_data, index=index)

        assert result == []

    def test_get_similar_embedding_failure(self):
        """Should return empty list when embedding fails."""
        from src.dedup.research.dedup import get_similar_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 4096)

        card_data = {"input": {"topic": "Test"}}

        with patch("src.dedup.research.dedup.get_embedding", return_value=None):
            result = get_similar_cards(card_data, index=index)

            assert result == []

    def test_get_similar_returns_results(self):
        """Should return similar cards."""
        from src.dedup.research.dedup import get_similar_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        # Use distinct embeddings where RC-001 will be clearly most similar
        index.add("RC-001", [1.0] + [0.0] * 4095)
        index.add("RC-002", [0.0, 1.0] + [0.0] * 4094)

        card_data = {"input": {"topic": "Test"}}

        # Query with same embedding as RC-001
        with patch("src.dedup.research.dedup.get_embedding", return_value=[1.0] + [0.0] * 4095):
            result = get_similar_cards(card_data, k=5, index=index)

            assert len(result) > 0
            assert result[0][0] == "RC-001"  # Most similar

    def test_get_similar_excludes_self(self):
        """Should exclude self from results."""
        from src.dedup.research.dedup import get_similar_cards
        from src.dedup.research.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096
        index.add("RC-001", embedding)
        index.add("RC-002", [0.2] * 4096)

        card_data = {
            "input": {"topic": "Test"},
            "metadata": {"card_id": "RC-001"}
        }

        with patch("src.dedup.research.dedup.get_embedding", return_value=embedding):
            result = get_similar_cards(card_data, k=5, index=index)

            # RC-001 should be excluded
            card_ids = [r[0] for r in result]
            assert "RC-001" not in card_ids


class TestModuleExports:
    """Tests for module exports."""

    def test_main_exports(self):
        """Should export main functions."""
        from src.dedup.research import (
            get_embedding,
            OllamaEmbedder,
            FaissIndex,
            check_duplicate,
            add_card_to_index,
            get_dedup_signal,
            DedupResult,
        )

        # Should not raise
        assert get_embedding is not None
        assert OllamaEmbedder is not None
        assert FaissIndex is not None
        assert check_duplicate is not None
        assert add_card_to_index is not None
        assert get_dedup_signal is not None
        assert DedupResult is not None
