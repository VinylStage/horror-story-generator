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
        from research_dedup.dedup import DedupSignal

        assert DedupSignal.LOW.value == "LOW"
        assert DedupSignal.MEDIUM.value == "MEDIUM"
        assert DedupSignal.HIGH.value == "HIGH"


class TestGetDedupSignal:
    """Tests for get_dedup_signal function."""

    def test_low_signal_below_threshold(self):
        """Should return LOW for scores below 0.70."""
        from research_dedup.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.0) == DedupSignal.LOW
        assert get_dedup_signal(0.5) == DedupSignal.LOW
        assert get_dedup_signal(0.69) == DedupSignal.LOW

    def test_medium_signal_in_range(self):
        """Should return MEDIUM for scores 0.70-0.85."""
        from research_dedup.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.70) == DedupSignal.MEDIUM
        assert get_dedup_signal(0.75) == DedupSignal.MEDIUM
        assert get_dedup_signal(0.84) == DedupSignal.MEDIUM

    def test_high_signal_above_threshold(self):
        """Should return HIGH for scores >= 0.85."""
        from research_dedup.dedup import get_dedup_signal, DedupSignal

        assert get_dedup_signal(0.85) == DedupSignal.HIGH
        assert get_dedup_signal(0.90) == DedupSignal.HIGH
        assert get_dedup_signal(1.0) == DedupSignal.HIGH


class TestDedupResult:
    """Tests for DedupResult dataclass."""

    def test_create_result(self):
        """Should create DedupResult with correct fields."""
        from research_dedup.dedup import DedupResult, DedupSignal

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
        from research_dedup.dedup import DedupResult, DedupSignal

        low = DedupResult(0.5, None, DedupSignal.LOW)
        medium = DedupResult(0.75, "RC-001", DedupSignal.MEDIUM)
        high = DedupResult(0.90, "RC-002", DedupSignal.HIGH)

        assert low.is_duplicate is False
        assert medium.is_duplicate is False
        assert high.is_duplicate is True

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        from research_dedup.dedup import DedupResult, DedupSignal

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
        from research_dedup.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Test Topic"}
        }

        result = create_card_text_for_embedding(card_data)
        assert "Topic: Test Topic" in result

    def test_extracts_output_fields(self):
        """Should extract output fields."""
        from research_dedup.embedder import create_card_text_for_embedding

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
        from research_dedup.embedder import create_card_text_for_embedding

        result = create_card_text_for_embedding({})
        assert result == ""

    def test_handles_partial_card(self):
        """Should handle partial card data."""
        from research_dedup.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Only Topic"}
        }

        result = create_card_text_for_embedding(card_data)
        assert "Topic: Only Topic" in result


class TestFaissIndex:
    """Tests for FaissIndex class."""

    def test_create_index(self):
        """Should create empty index."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        assert index.size == 0

    def test_add_vector(self):
        """Should add vector to index."""
        from research_dedup.index import FaissIndex, is_faiss_available

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
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096

        index.add("RC-001", embedding)
        index.add("RC-001", embedding)  # Duplicate

        assert index.size == 1

    def test_search_empty_index(self):
        """Should return empty list for empty index."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 4096

        results = index.search(embedding)

        assert results == []

    def test_search_returns_results(self):
        """Should return search results."""
        from research_dedup.index import FaissIndex, is_faiss_available

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
        from research_dedup.index import FaissIndex, is_faiss_available

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
        from research_dedup.index import FaissIndex, is_faiss_available

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
        from research_dedup.index import FaissIndex, is_faiss_available

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
        from research_dedup.index import is_faiss_available

        result = is_faiss_available()
        assert isinstance(result, bool)


class TestModuleExports:
    """Tests for module exports."""

    def test_main_exports(self):
        """Should export main functions."""
        from research_dedup import (
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
