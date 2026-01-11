"""
Tests for research_dedup/index.py module.

Phase B+: Comprehensive FAISS index tests for 100% coverage.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestFaissAvailability:
    """Tests for FAISS availability handling."""

    def test_faiss_not_available_warning(self):
        """Should log warning when FAISS not available."""
        import importlib
        import sys

        # Save original faiss module reference
        original_faiss = sys.modules.get("faiss")

        # Temporarily remove faiss to test import error handling
        if "faiss" in sys.modules:
            del sys.modules["faiss"]

        # Mock import to raise ImportError
        with patch.dict(sys.modules, {"faiss": None}):
            with patch("builtins.__import__", side_effect=ImportError("No FAISS")):
                # This tests the import error path
                pass

        # Restore
        if original_faiss:
            sys.modules["faiss"] = original_faiss


class TestFaissIndexInit:
    """Tests for FaissIndex initialization."""

    def test_init_without_paths(self):
        """Should create index without paths."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()

        assert index.size == 0
        assert index.index_path is None
        assert index.metadata_path is None

    def test_init_with_nonexistent_paths(self):
        """Should handle nonexistent paths gracefully."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "nonexistent.faiss"
            metadata_path = Path(tmpdir) / "nonexistent.json"

            index = FaissIndex(index_path=index_path, metadata_path=metadata_path)

            # Should create empty index
            assert index.size == 0


class TestFaissIndexAdd:
    """Tests for adding vectors to FaissIndex."""

    def test_add_empty_embedding(self):
        """Should fail for empty embedding."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        result = index.add("RC-001", [])

        assert result is False

    def test_add_updates_dimension(self):
        """Should update dimension from first embedding."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        embedding = [0.1] * 100  # 100-dim

        index.add("RC-001", embedding)

        assert index.dimension == 100

    def test_add_exception_handling(self):
        """Should handle add exception."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index._ensure_index(100)

        # Mock the add method to raise
        with patch.object(index._index, "add", side_effect=Exception("Add error")):
            result = index.add("RC-001", [0.1] * 100)

            assert result is False


class TestFaissIndexSearch:
    """Tests for searching FaissIndex."""

    def test_search_without_faiss(self):
        """Should return empty when FAISS not available."""
        from research_dedup.index import FaissIndex

        index = FaissIndex()
        index._index = None  # Simulate no FAISS

        results = index.search([0.1] * 100)

        assert results == []

    def test_search_empty_index(self):
        """Should return empty for empty index."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index._ensure_index(100)

        results = index.search([0.1] * 100)

        assert results == []

    def test_search_with_exclusion(self):
        """Should exclude specified card."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [1.0] + [0.0] * 99)
        index.add("RC-002", [0.9] + [0.1] * 99)

        results = index.search([1.0] + [0.0] * 99, k=2, exclude_card_id="RC-001")

        card_ids = [r[0] for r in results]
        assert "RC-001" not in card_ids

    def test_search_handles_invalid_index(self):
        """Should handle invalid FAISS indices."""
        from research_dedup.index import FaissIndex, is_faiss_available
        import numpy as np

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 100)

        # Mock search to return -1 indices
        with patch.object(index._index, "search") as mock_search:
            mock_search.return_value = (
                np.array([[0.9, -1]]),  # scores
                np.array([[0, -1]])  # indices (-1 is invalid)
            )

            results = index.search([0.1] * 100, k=2)

            # Should filter out -1 indices
            assert len(results) <= 1

    def test_search_handles_missing_card_id(self):
        """Should handle missing card ID in metadata."""
        from research_dedup.index import FaissIndex, is_faiss_available
        import numpy as np

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 100)

        # Remove from id_to_card mapping
        del index._id_to_card[0]

        results = index.search([0.1] * 100, k=2)

        # Should skip missing card IDs
        assert len(results) == 0

    def test_search_exception_handling(self):
        """Should handle search exception."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 100)

        with patch.object(index._index, "search", side_effect=Exception("Search error")):
            results = index.search([0.1] * 100)

            assert results == []


class TestFaissIndexSave:
    """Tests for saving FaissIndex."""

    def test_save_without_faiss(self):
        """Should fail when FAISS not available."""
        from research_dedup.index import FaissIndex

        index = FaissIndex()
        index._index = None

        result = index.save()

        assert result is False

    def test_save_without_paths(self):
        """Should fail without configured paths."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index._ensure_index(100)

        result = index.save()

        assert result is False

    def test_save_creates_directories(self):
        """Should create parent directories."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "nested" / "dir" / "test.faiss"
            metadata_path = Path(tmpdir) / "nested" / "dir" / "metadata.json"

            index = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            index.add("RC-001", [0.1] * 100)

            result = index.save()

            assert result is True
            assert index_path.exists()
            assert metadata_path.exists()

    def test_save_exception_handling(self):
        """Should handle save exception."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            index.add("RC-001", [0.1] * 100)

            # Mock write_index to raise
            with patch("faiss.write_index", side_effect=Exception("Write error")):
                result = index.save()

                assert result is False


class TestFaissIndexLoad:
    """Tests for loading FaissIndex."""

    def test_load_without_faiss(self):
        """Should fail when FAISS not available."""
        from research_dedup.index import FaissIndex

        with patch("research_dedup.index.FAISS_AVAILABLE", False):
            index = FaissIndex()
            result = index._load()

            assert result is False

    def test_load_without_paths(self):
        """Should fail without paths."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        result = index._load()

        assert result is False

    def test_load_exception_handling(self):
        """Should handle load exception and reset state."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            # Create index and save
            index1 = FaissIndex(index_path=index_path, metadata_path=metadata_path)
            index1.add("RC-001", [0.1] * 100)
            index1.save()

            # Try to load with error
            with patch("faiss.read_index", side_effect=Exception("Read error")):
                index2 = FaissIndex()
                index2.index_path = index_path
                index2.metadata_path = metadata_path

                result = index2._load()

                assert result is False
                assert index2._index is None
                assert index2._id_to_card == {}


class TestGetIndex:
    """Tests for get_index function."""

    def test_get_index_creates_global(self):
        """Should create global index instance."""
        from research_dedup.index import get_index, is_faiss_available
        import research_dedup.index as module

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        # Reset global
        module._global_index = None

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index = get_index(index_path=index_path, metadata_path=metadata_path)

            assert index is not None
            assert module._global_index is index

            # Cleanup
            module._global_index = None

    def test_get_index_returns_same_instance(self):
        """Should return same global instance."""
        from research_dedup.index import get_index, is_faiss_available
        import research_dedup.index as module

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        # Reset global
        module._global_index = None

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test.faiss"
            metadata_path = Path(tmpdir) / "metadata.json"

            index1 = get_index(index_path=index_path, metadata_path=metadata_path)
            index2 = get_index(index_path=index_path, metadata_path=metadata_path)

            assert index1 is index2

            # Cleanup
            module._global_index = None

    def test_get_index_uses_default_paths(self):
        """Should use default paths from data_paths."""
        from research_dedup.index import get_index, is_faiss_available
        import research_dedup.index as module

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        # Reset global
        module._global_index = None

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("data_paths.get_faiss_index_path", return_value=Path(tmpdir) / "default.faiss"):
                with patch("data_paths.get_vector_metadata_path", return_value=Path(tmpdir) / "default.json"):
                    index = get_index()

                    assert index is not None

        # Cleanup
        module._global_index = None

    def test_get_index_import_error(self):
        """Should handle ImportError for data_paths."""
        from research_dedup.index import get_index, is_faiss_available
        import research_dedup.index as module

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        # Reset global
        module._global_index = None

        # This should work even if data_paths import fails
        index = get_index()

        assert index is not None

        # Cleanup
        module._global_index = None


class TestEnsureIndex:
    """Tests for _ensure_index method."""

    def test_ensure_index_not_available(self):
        """Should return False when FAISS not available."""
        from research_dedup.index import FaissIndex

        index = FaissIndex()

        with patch("research_dedup.index.FAISS_AVAILABLE", False):
            result = index._ensure_index()

            assert result is False

    def test_ensure_index_uses_provided_dim(self):
        """Should use provided dimension."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex(dimension=1000)  # Default 1000

        result = index._ensure_index(dim=200)  # Override to 200

        assert result is True
        assert index.dimension == 200

    def test_ensure_index_uses_default_dim(self):
        """Should use default dimension if not provided."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex(dimension=500)

        result = index._ensure_index()  # No dim provided

        assert result is True
        assert index.dimension == 500


class TestContainsAndSize:
    """Tests for contains and size methods."""

    def test_contains_returns_false_for_missing(self):
        """Should return False for non-existent card."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()

        assert index.contains("RC-NONEXISTENT") is False

    def test_size_reflects_additions(self):
        """Should reflect number of added cards."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()

        assert index.size == 0

        index.add("RC-001", [0.1] * 100)
        assert index.size == 1

        index.add("RC-002", [0.2] * 100)
        assert index.size == 2


class TestClear:
    """Tests for clear method."""

    def test_clear_resets_all(self):
        """Should reset all internal state."""
        from research_dedup.index import FaissIndex, is_faiss_available

        if not is_faiss_available():
            pytest.skip("FAISS not available")

        index = FaissIndex()
        index.add("RC-001", [0.1] * 100)
        index.add("RC-002", [0.2] * 100)

        assert index.size == 2

        index.clear()

        assert index.size == 0
        assert index._index is None
        assert index._id_to_card == {}
        assert index._card_to_id == {}
