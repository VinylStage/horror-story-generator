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
        from src.infra.data_paths import get_project_root

        result = get_project_root()
        assert isinstance(result, Path)

    def test_path_exists(self):
        """Should return an existing directory."""
        from src.infra.data_paths import get_project_root

        result = get_project_root()
        assert result.exists()
        assert result.is_dir()

    def test_contains_main_py(self):
        """Should be the project root containing main.py."""
        from src.infra.data_paths import get_project_root

        result = get_project_root()
        assert (result / "main.py").exists()


class TestGetDataRoot:
    """Tests for get_data_root function."""

    def test_returns_data_subdirectory(self):
        """Should return data/ subdirectory of project root."""
        from src.infra.data_paths import get_data_root, get_project_root

        result = get_data_root()
        expected = get_project_root() / "data"
        assert result == expected

    def test_returns_path_object(self):
        """Should return a Path object."""
        from src.infra.data_paths import get_data_root

        result = get_data_root()
        assert isinstance(result, Path)


class TestResearchPaths:
    """Tests for research-related path functions."""

    def test_get_research_root(self):
        """Should return research directory path."""
        from src.infra.data_paths import get_research_root, get_data_root

        result = get_research_root()
        assert result == get_data_root() / "research"

    def test_get_research_cards_dir(self):
        """Should return cards subdirectory."""
        from src.infra.data_paths import get_research_cards_dir, get_research_root

        result = get_research_cards_dir()
        assert result == get_research_root() / "cards"

    def test_get_research_vectors_dir(self):
        """Should return vectors subdirectory."""
        from src.infra.data_paths import get_research_vectors_dir, get_research_root

        result = get_research_vectors_dir()
        assert result == get_research_root() / "vectors"

    def test_get_research_logs_dir(self):
        """Should return logs subdirectory."""
        from src.infra.data_paths import get_research_logs_dir, get_research_root

        result = get_research_logs_dir()
        assert result == get_research_root() / "logs"

    def test_get_research_registry_path(self):
        """Should return registry.sqlite path."""
        from src.infra.data_paths import get_research_registry_path, get_research_root

        result = get_research_registry_path()
        assert result == get_research_root() / "registry.sqlite"

    def test_get_faiss_index_path(self):
        """Should return research.faiss path."""
        from src.infra.data_paths import get_faiss_index_path, get_research_vectors_dir

        result = get_faiss_index_path()
        assert result == get_research_vectors_dir() / "research.faiss"

    def test_get_vector_metadata_path(self):
        """Should return metadata.json path."""
        from src.infra.data_paths import get_vector_metadata_path, get_research_vectors_dir

        result = get_vector_metadata_path()
        assert result == get_research_vectors_dir() / "metadata.json"


class TestSeedsPaths:
    """Tests for seeds-related path functions."""

    def test_get_seeds_root(self):
        """Should return seeds directory path."""
        from src.infra.data_paths import get_seeds_root, get_data_root

        result = get_seeds_root()
        assert result == get_data_root() / "seeds"

    def test_get_seed_registry_path(self):
        """Should return seed_registry.sqlite path."""
        from src.infra.data_paths import get_seed_registry_path, get_seeds_root

        result = get_seed_registry_path()
        assert result == get_seeds_root() / "seed_registry.sqlite"


class TestStoryRegistryPath:
    """Tests for story registry path."""

    def test_get_story_registry_path(self):
        """Should return story_registry.db path."""
        from src.infra.data_paths import get_story_registry_path, get_data_root

        result = get_story_registry_path()
        assert result == get_data_root() / "story_registry.db"


class TestEnsureDataDirectories:
    """Tests for ensure_data_directories function."""

    def test_creates_directories(self):
        """Should create all required directories."""
        from src.infra.data_paths import ensure_data_directories

        result = ensure_data_directories()

        assert "data_root" in result
        assert "research_root" in result
        assert "research_cards" in result
        assert "research_vectors" in result
        assert "research_logs" in result
        assert "seeds" in result

    def test_returns_path_dict(self):
        """Should return dictionary of paths."""
        from src.infra.data_paths import ensure_data_directories

        result = ensure_data_directories()

        for key, path in result.items():
            assert isinstance(path, Path)

    def test_idempotent(self):
        """Should be safe to call multiple times."""
        from src.infra.data_paths import ensure_data_directories

        result1 = ensure_data_directories()
        result2 = ensure_data_directories()

        assert result1 == result2


class TestGetAllPaths:
    """Tests for get_all_paths function."""

    def test_returns_complete_structure(self):
        """Should return all path configurations."""
        from src.infra.data_paths import get_all_paths

        result = get_all_paths()

        assert "project_root" in result
        assert "data_root" in result
        assert "research" in result
        assert "seeds" in result
        assert "story_registry" in result

    def test_research_paths_nested(self):
        """Should have nested research paths."""
        from src.infra.data_paths import get_all_paths

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
        from src.infra.data_paths import get_all_paths

        result = get_all_paths()
        seeds = result["seeds"]

        assert "root" in seeds
        assert "registry" in seeds


class TestFindAllResearchCards:
    """Tests for find_all_research_cards function."""

    def test_returns_list(self):
        """Should return a list."""
        from src.infra.data_paths import find_all_research_cards

        result = find_all_research_cards()
        assert isinstance(result, list)

    def test_finds_json_files(self):
        """Should find RC-*.json files."""
        from src.infra.data_paths import find_all_research_cards

        result = find_all_research_cards()

        for path in result:
            assert path.suffix == ".json"
            assert path.stem.startswith("RC-")

    def test_include_legacy_parameter(self):
        """Should accept include_legacy parameter."""
        from src.infra.data_paths import find_all_research_cards

        # Should not raise
        result1 = find_all_research_cards(include_legacy=True)
        result2 = find_all_research_cards(include_legacy=False)

        assert isinstance(result1, list)
        assert isinstance(result2, list)


class TestInitialize:
    """Tests for initialize function."""

    def test_initialize_is_idempotent(self):
        """Should be safe to call multiple times."""
        from src.infra.data_paths import initialize

        # Should not raise
        initialize()
        initialize()
        initialize()

    def test_module_auto_initializes(self):
        """Module should auto-initialize on import."""
        from src.infra.data_paths import _initialized

        # After import, should be initialized
        assert _initialized is True


class TestGetNovelOutputDir:
    """Tests for get_novel_output_dir function (v1.3.1)."""

    def test_returns_default_path(self):
        """Should return data/novel by default."""
        from src.infra.data_paths import get_novel_output_dir, get_data_root

        with patch.dict("os.environ", {}, clear=False):
            # Clear NOVEL_OUTPUT_DIR if set
            import os
            os.environ.pop("NOVEL_OUTPUT_DIR", None)
            result = get_novel_output_dir()
            assert result == get_data_root() / "novel"

    def test_respects_env_override(self):
        """Should respect NOVEL_OUTPUT_DIR environment variable."""
        from src.infra.data_paths import get_novel_output_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"NOVEL_OUTPUT_DIR": tmpdir}):
                result = get_novel_output_dir()
                assert result == Path(tmpdir).resolve()


class TestGetJobsDir:
    """Tests for get_jobs_dir function (v1.3.1)."""

    def test_returns_default_path(self):
        """Should return jobs/ directory by default."""
        from src.infra.data_paths import get_jobs_dir, get_project_root

        import os
        os.environ.pop("JOB_DIR", None)
        result = get_jobs_dir()
        assert result == get_project_root() / "jobs"

    def test_respects_env_override(self):
        """Should respect JOB_DIR environment variable."""
        from src.infra.data_paths import get_jobs_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"JOB_DIR": tmpdir}):
                result = get_jobs_dir()
                assert result == Path(tmpdir).resolve()


class TestGetJobPruneConfig:
    """Tests for get_job_prune_config function (v1.3.1)."""

    def test_returns_defaults(self):
        """Should return default config when no env vars set."""
        from src.infra.data_paths import get_job_prune_config

        import os
        os.environ.pop("JOB_PRUNE_ENABLED", None)
        os.environ.pop("JOB_PRUNE_DAYS", None)
        os.environ.pop("JOB_PRUNE_MAX_COUNT", None)

        result = get_job_prune_config()
        assert result["enabled"] is False
        assert result["days"] == 30
        assert result["max_count"] == 1000

    def test_respects_env_overrides(self):
        """Should respect JOB_PRUNE_* environment variables."""
        from src.infra.data_paths import get_job_prune_config

        with patch.dict("os.environ", {
            "JOB_PRUNE_ENABLED": "true",
            "JOB_PRUNE_DAYS": "7",
            "JOB_PRUNE_MAX_COUNT": "100"
        }):
            result = get_job_prune_config()
            assert result["enabled"] is True
            assert result["days"] == 7
            assert result["max_count"] == 100


class TestGetLegacyResearchCardsJsonl:
    """Tests for get_legacy_research_cards_jsonl function (v1.3.1)."""

    def test_returns_legacy_path(self):
        """Should return the legacy research_cards.jsonl path."""
        import warnings
        from src.infra.data_paths import get_legacy_research_cards_jsonl, get_data_root

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_legacy_research_cards_jsonl()
            assert result == get_data_root() / "research_cards.jsonl"

    def test_emits_deprecation_warning(self):
        """Should emit DeprecationWarning."""
        import warnings
        from src.infra.data_paths import get_legacy_research_cards_jsonl

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            get_legacy_research_cards_jsonl()
            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "deprecated" in str(w[-1].message).lower()
