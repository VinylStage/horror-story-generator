"""
Tests for data_paths module.

Phase B+: Centralized path management tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetProjectRoot:
    """Tests for get_project_root function."""

    def test_returns_path_object(self):
        """Should return a Path object."""
        from data_paths import get_project_root

        result = get_project_root()
        assert isinstance(result, Path)

    def test_path_exists(self):
        """Should return an existing directory."""
        from data_paths import get_project_root

        result = get_project_root()
        assert result.exists()
        assert result.is_dir()

    def test_contains_data_paths_file(self):
        """Should be the directory containing data_paths.py."""
        from data_paths import get_project_root

        result = get_project_root()
        assert (result / "data_paths.py").exists()


class TestGetDataRoot:
    """Tests for get_data_root function."""

    def test_returns_data_subdirectory(self):
        """Should return data/ subdirectory of project root."""
        from data_paths import get_data_root, get_project_root

        result = get_data_root()
        expected = get_project_root() / "data"
        assert result == expected

    def test_returns_path_object(self):
        """Should return a Path object."""
        from data_paths import get_data_root

        result = get_data_root()
        assert isinstance(result, Path)


class TestResearchPaths:
    """Tests for research-related path functions."""

    def test_get_research_root(self):
        """Should return research directory path."""
        from data_paths import get_research_root, get_data_root

        result = get_research_root()
        assert result == get_data_root() / "research"

    def test_get_research_cards_dir(self):
        """Should return cards subdirectory."""
        from data_paths import get_research_cards_dir, get_research_root

        result = get_research_cards_dir()
        assert result == get_research_root() / "cards"

    def test_get_research_vectors_dir(self):
        """Should return vectors subdirectory."""
        from data_paths import get_research_vectors_dir, get_research_root

        result = get_research_vectors_dir()
        assert result == get_research_root() / "vectors"

    def test_get_research_logs_dir(self):
        """Should return logs subdirectory."""
        from data_paths import get_research_logs_dir, get_research_root

        result = get_research_logs_dir()
        assert result == get_research_root() / "logs"

    def test_get_research_registry_path(self):
        """Should return registry.sqlite path."""
        from data_paths import get_research_registry_path, get_research_root

        result = get_research_registry_path()
        assert result == get_research_root() / "registry.sqlite"

    def test_get_faiss_index_path(self):
        """Should return research.faiss path."""
        from data_paths import get_faiss_index_path, get_research_vectors_dir

        result = get_faiss_index_path()
        assert result == get_research_vectors_dir() / "research.faiss"

    def test_get_vector_metadata_path(self):
        """Should return metadata.json path."""
        from data_paths import get_vector_metadata_path, get_research_vectors_dir

        result = get_vector_metadata_path()
        assert result == get_research_vectors_dir() / "metadata.json"


class TestSeedsPaths:
    """Tests for seeds-related path functions."""

    def test_get_seeds_root(self):
        """Should return seeds directory path."""
        from data_paths import get_seeds_root, get_data_root

        result = get_seeds_root()
        assert result == get_data_root() / "seeds"

    def test_get_seed_registry_path(self):
        """Should return seed_registry.sqlite path."""
        from data_paths import get_seed_registry_path, get_seeds_root

        result = get_seed_registry_path()
        assert result == get_seeds_root() / "seed_registry.sqlite"


class TestStoryRegistryPath:
    """Tests for story registry path."""

    def test_get_story_registry_path(self):
        """Should return story_registry.db path."""
        from data_paths import get_story_registry_path, get_data_root

        result = get_story_registry_path()
        assert result == get_data_root() / "story_registry.db"


class TestEnsureDataDirectories:
    """Tests for ensure_data_directories function."""

    def test_creates_directories(self):
        """Should create all required directories."""
        from data_paths import ensure_data_directories

        result = ensure_data_directories()

        assert "data_root" in result
        assert "research_root" in result
        assert "research_cards" in result
        assert "research_vectors" in result
        assert "research_logs" in result
        assert "seeds" in result

    def test_returns_path_dict(self):
        """Should return dictionary of paths."""
        from data_paths import ensure_data_directories

        result = ensure_data_directories()

        for key, path in result.items():
            assert isinstance(path, Path)

    def test_idempotent(self):
        """Should be safe to call multiple times."""
        from data_paths import ensure_data_directories

        result1 = ensure_data_directories()
        result2 = ensure_data_directories()

        assert result1 == result2


class TestGetAllPaths:
    """Tests for get_all_paths function."""

    def test_returns_complete_structure(self):
        """Should return all path configurations."""
        from data_paths import get_all_paths

        result = get_all_paths()

        assert "project_root" in result
        assert "data_root" in result
        assert "research" in result
        assert "seeds" in result
        assert "story_registry" in result

    def test_research_paths_nested(self):
        """Should have nested research paths."""
        from data_paths import get_all_paths

        result = get_all_paths()
        research = result["research"]

        assert "root" in research
        assert "cards" in research
        assert "vectors" in research
        assert "logs" in research
        assert "registry" in research
        assert "faiss_index" in research
        assert "vector_metadata" in research

    def test_seeds_paths_nested(self):
        """Should have nested seeds paths."""
        from data_paths import get_all_paths

        result = get_all_paths()
        seeds = result["seeds"]

        assert "root" in seeds
        assert "registry" in seeds


class TestFindAllResearchCards:
    """Tests for find_all_research_cards function."""

    def test_returns_list(self):
        """Should return a list."""
        from data_paths import find_all_research_cards

        result = find_all_research_cards()
        assert isinstance(result, list)

    def test_finds_json_files(self):
        """Should find RC-*.json files."""
        from data_paths import find_all_research_cards

        result = find_all_research_cards()

        for path in result:
            assert path.suffix == ".json"
            assert path.stem.startswith("RC-")

    def test_include_legacy_parameter(self):
        """Should accept include_legacy parameter."""
        from data_paths import find_all_research_cards

        # Should not raise
        result1 = find_all_research_cards(include_legacy=True)
        result2 = find_all_research_cards(include_legacy=False)

        assert isinstance(result1, list)
        assert isinstance(result2, list)


class TestInitialize:
    """Tests for initialize function."""

    def test_initialize_is_idempotent(self):
        """Should be safe to call multiple times."""
        from data_paths import initialize

        # Should not raise
        initialize()
        initialize()
        initialize()

    def test_module_auto_initializes(self):
        """Module should auto-initialize on import."""
        from data_paths import _initialized

        # After import, should be initialized
        assert _initialized is True
