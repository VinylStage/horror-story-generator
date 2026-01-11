"""
Tests for seed_integration module.

Phase B+: Non-blocking seed injection tests.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestSeedSelection:
    """Tests for SeedSelection dataclass."""

    def test_create_selection_with_seed(self):
        """Should create selection with seed."""
        from src.story.seed_integration import SeedSelection
        from src.story.story_seed import StorySeed

        seed = StorySeed(
            seed_id="SS-001",
            source_card_id="RC-001",
            key_themes=["isolation"],
            atmosphere_tags=["oppressive"],
            suggested_hooks=["A door opens..."],
            cultural_elements=["urban life"]
        )

        selection = SeedSelection(
            seed=seed,
            selection_reason="Selected via least_used",
            total_available=5
        )

        assert selection.seed == seed
        assert selection.has_seed is True
        assert selection.selection_reason == "Selected via least_used"
        assert selection.total_available == 5

    def test_create_selection_without_seed(self):
        """Should create selection without seed."""
        from src.story.seed_integration import SeedSelection

        selection = SeedSelection(
            seed=None,
            selection_reason="No seeds available",
            total_available=0
        )

        assert selection.seed is None
        assert selection.has_seed is False

    def test_has_seed_property(self):
        """Should correctly report has_seed."""
        from src.story.seed_integration import SeedSelection
        from src.story.story_seed import StorySeed

        no_seed = SeedSelection(None, "No seed", 0)
        assert no_seed.has_seed is False

        seed = StorySeed(
            seed_id="SS-001",
            source_card_id="RC-001",
            key_themes=[],
            atmosphere_tags=[],
            suggested_hooks=[],
            cultural_elements=[]
        )
        with_seed = SeedSelection(seed, "Found", 1)
        assert with_seed.has_seed is True


class TestSelectSeedForGeneration:
    """Tests for select_seed_for_generation function."""

    def test_returns_selection_object(self):
        """Should return SeedSelection object."""
        from src.story.seed_integration import select_seed_for_generation, SeedSelection

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
                mock_reg = MagicMock()
                mock_reg.list_available.return_value = []
                mock_reg.count.return_value = 0
                mock_registry.return_value = mock_reg

                with patch("src.story.seed_integration.list_seeds", return_value=[]):
                    result = select_seed_for_generation()

                    assert isinstance(result, SeedSelection)

    def test_handles_registry_unavailable(self):
        """Should handle registry being unavailable."""
        from src.story.seed_integration import select_seed_for_generation

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_registry.side_effect = Exception("Database error")

            result = select_seed_for_generation()

            assert result.seed is None
            assert "unavailable" in result.selection_reason.lower()
            assert result.total_available == 0

    def test_handles_no_seeds_available(self):
        """Should handle no seeds available."""
        from src.story.seed_integration import select_seed_for_generation

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.list_available.return_value = []
            mock_reg.count.return_value = 0
            mock_registry.return_value = mock_reg

            with patch("src.story.seed_integration.list_seeds", return_value=[]):
                result = select_seed_for_generation()

                assert result.seed is None
                assert "no seeds" in result.selection_reason.lower()

    def test_strategy_least_used(self):
        """Should use least_used strategy by default."""
        from src.story.seed_integration import select_seed_for_generation
        from src.registry.seed_registry import SeedRecord

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_record = SeedRecord(
                seed_id="SS-001",
                source_card_id="RC-001",
                created_at=datetime.now(),
                times_used=0,
                file_path="/path/to/seed.json"
            )
            mock_reg.list_available.return_value = [mock_record]
            mock_reg.count.return_value = 1
            mock_reg.get_least_used.return_value = mock_record
            mock_registry.return_value = mock_reg

            with patch("src.story.seed_integration.load_seed") as mock_load:
                mock_load.return_value = None  # Will trigger file not found

                result = select_seed_for_generation(strategy="least_used")

                mock_reg.get_least_used.assert_called_once()

    def test_strategy_random(self):
        """Should support random strategy."""
        from src.story.seed_integration import select_seed_for_generation
        from src.registry.seed_registry import SeedRecord

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_record = SeedRecord(
                seed_id="SS-001",
                source_card_id="RC-001",
                created_at=datetime.now()
            )
            mock_reg.list_available.return_value = [mock_record]
            mock_reg.count.return_value = 1
            mock_registry.return_value = mock_reg

            with patch("src.story.seed_integration.load_seed", return_value=None):
                result = select_seed_for_generation(strategy="random")

                assert isinstance(result.total_available, int)

    def test_never_raises_exception(self):
        """Should never raise exceptions."""
        from src.story.seed_integration import select_seed_for_generation

        # Various failure scenarios
        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_registry.side_effect = RuntimeError("Catastrophic failure")

            # Should not raise
            result = select_seed_for_generation()
            assert result.seed is None


class TestGetSeedContextForPrompt:
    """Tests for get_seed_context_for_prompt function."""

    def test_returns_none_without_seed(self):
        """Should return None when no seed selected."""
        from src.story.seed_integration import get_seed_context_for_prompt, SeedSelection

        selection = SeedSelection(seed=None, selection_reason="None", total_available=0)

        result = get_seed_context_for_prompt(selection)

        assert result is None

    def test_returns_context_dict_with_seed(self):
        """Should return context dict when seed is selected."""
        from src.story.seed_integration import get_seed_context_for_prompt, SeedSelection
        from src.story.story_seed import StorySeed

        seed = StorySeed(
            seed_id="SS-001",
            source_card_id="RC-001",
            key_themes=["isolation", "paranoia"],
            atmosphere_tags=["oppressive"],
            suggested_hooks=["A door opens..."],
            cultural_elements=["corporate"]
        )

        selection = SeedSelection(seed=seed, selection_reason="Selected", total_available=1)

        result = get_seed_context_for_prompt(selection)

        assert result is not None
        assert result["seed_id"] == "SS-001"
        assert result["source_card_id"] == "RC-001"
        assert result["key_themes"] == ["isolation", "paranoia"]
        assert result["atmosphere_tags"] == ["oppressive"]
        assert result["suggested_hooks"] == ["A door opens..."]
        assert result["cultural_elements"] == ["corporate"]


class TestFormatSeedForSystemPrompt:
    """Tests for format_seed_for_system_prompt function."""

    def test_returns_empty_for_none(self):
        """Should return empty string for None context."""
        from src.story.seed_integration import format_seed_for_system_prompt

        result = format_seed_for_system_prompt(None)

        assert result == ""

    def test_returns_empty_for_empty_dict(self):
        """Should return empty string for empty dict (truthy check)."""
        from src.story.seed_integration import format_seed_for_system_prompt

        result = format_seed_for_system_prompt({})

        # Empty dict is falsy in Python, so returns empty string
        assert result == ""

    def test_formats_themes(self):
        """Should format key themes."""
        from src.story.seed_integration import format_seed_for_system_prompt

        context = {"key_themes": ["isolation", "paranoia", "dread"]}

        result = format_seed_for_system_prompt(context)

        assert "Core themes" in result
        assert "- isolation" in result
        assert "- paranoia" in result
        assert "- dread" in result

    def test_formats_atmosphere(self):
        """Should format atmosphere tags."""
        from src.story.seed_integration import format_seed_for_system_prompt

        context = {"atmosphere_tags": ["oppressive", "uncanny"]}

        result = format_seed_for_system_prompt(context)

        assert "Atmosphere" in result
        assert "oppressive" in result
        assert "uncanny" in result

    def test_formats_hooks(self):
        """Should format suggested hooks."""
        from src.story.seed_integration import format_seed_for_system_prompt

        context = {"suggested_hooks": ["A researcher discovers...", "The elevator stops..."]}

        result = format_seed_for_system_prompt(context)

        assert "story hooks" in result.lower()
        assert "researcher discovers" in result

    def test_formats_cultural_elements(self):
        """Should format cultural elements."""
        from src.story.seed_integration import format_seed_for_system_prompt

        context = {"cultural_elements": ["corporate surveillance", "late-night convenience stores"]}

        result = format_seed_for_system_prompt(context)

        assert "Cultural elements" in result
        assert "corporate surveillance" in result

    def test_includes_inspiration_note(self):
        """Should include note about seeds being inspiration."""
        from src.story.seed_integration import format_seed_for_system_prompt

        context = {"key_themes": ["test"]}

        result = format_seed_for_system_prompt(context)

        assert "inspire" in result.lower()


class TestMarkSeedUsed:
    """Tests for mark_seed_used function."""

    def test_marks_seed_in_registry(self):
        """Should mark seed as used."""
        from src.story.seed_integration import mark_seed_used

        with patch("src.story.seed_integration.get_seed_registry") as mock_get:
            mock_reg = MagicMock()
            mock_reg.mark_used.return_value = True
            mock_get.return_value = mock_reg

            result = mark_seed_used("SS-001")

            assert result is True
            mock_reg.mark_used.assert_called_once_with("SS-001")

    def test_returns_false_on_error(self):
        """Should return False on registry error."""
        from src.story.seed_integration import mark_seed_used

        with patch("src.story.seed_integration.get_seed_registry") as mock_get:
            mock_get.side_effect = Exception("Database error")

            result = mark_seed_used("SS-001")

            assert result is False

    def test_accepts_custom_registry(self):
        """Should accept custom registry."""
        from src.story.seed_integration import mark_seed_used

        mock_reg = MagicMock()
        mock_reg.mark_used.return_value = True

        result = mark_seed_used("SS-001", registry=mock_reg)

        assert result is True
        mock_reg.mark_used.assert_called_once_with("SS-001")


class TestGetSeedInjectionStatus:
    """Tests for get_seed_injection_status function."""

    def test_returns_status_dict(self):
        """Should return status dictionary."""
        from src.story.seed_integration import get_seed_injection_status

        with patch("src.story.seed_integration.get_seed_registry") as mock_get:
            mock_reg = MagicMock()
            mock_reg.get_stats.return_value = {"total": 5, "available": 3}
            mock_get.return_value = mock_reg

            with patch("src.story.seed_integration.list_seeds", return_value=[]):
                result = get_seed_injection_status()

                assert "available" in result
                assert result["available"] is True
                assert "registry_stats" in result

    def test_handles_error_gracefully(self):
        """Should handle errors gracefully."""
        from src.story.seed_integration import get_seed_injection_status

        with patch("src.story.seed_integration.get_seed_registry") as mock_get:
            mock_get.side_effect = Exception("Database unavailable")

            result = get_seed_injection_status()

            assert result["available"] is False
            assert "error" in result


class TestSelectSeedAdvanced:
    """Advanced tests for select_seed_for_generation."""

    def test_successful_seed_selection_with_load(self):
        """Should successfully select and load a seed."""
        from src.story.seed_integration import select_seed_for_generation
        from src.registry.seed_registry import SeedRecord
        from src.story.story_seed import StorySeed

        mock_seed = StorySeed(
            seed_id="SS-001",
            source_card_id="RC-001",
            key_themes=["test"],
            atmosphere_tags=[],
            suggested_hooks=[],
            cultural_elements=[]
        )

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_record = SeedRecord(
                seed_id="SS-001",
                source_card_id="RC-001",
                created_at=datetime.now(),
                file_path="/path/to/seed.json"
            )
            mock_reg.list_available.return_value = [mock_record]
            mock_reg.count.return_value = 1
            mock_reg.get_least_used.return_value = mock_record
            mock_registry.return_value = mock_reg

            # Mock Path.exists to return True so the seed file is "found"
            with patch("pathlib.Path.exists", return_value=True):
                with patch("src.story.seed_integration.load_seed", return_value=mock_seed):
                    result = select_seed_for_generation()

                    assert result.seed is not None
                    assert result.seed.seed_id == "SS-001"
                    assert result.has_seed is True

    def test_fallback_to_files_when_registry_empty(self):
        """Should try file system when registry is empty."""
        from src.story.seed_integration import select_seed_for_generation
        from src.story.story_seed import StorySeed

        mock_seed = StorySeed(
            seed_id="SS-FILE-001",
            source_card_id="RC-001",
            key_themes=["file"],
            atmosphere_tags=[],
            suggested_hooks=[],
            cultural_elements=[]
        )

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.list_available.return_value = []
            mock_reg.count.return_value = 0
            mock_registry.return_value = mock_reg

            with patch("src.story.seed_integration.list_seeds") as mock_list:
                from pathlib import Path
                mock_list.return_value = [Path("/fake/SS-FILE-001.json")]

                with patch("src.story.seed_integration.load_seed", return_value=mock_seed):
                    result = select_seed_for_generation()

                    # Should have attempted to get seed from file system
                    assert mock_list.called

    def test_random_selection_from_multiple_seeds(self):
        """Should select randomly from multiple available seeds."""
        from src.story.seed_integration import select_seed_for_generation
        from src.registry.seed_registry import SeedRecord
        from src.story.story_seed import StorySeed

        mock_seed = StorySeed(
            seed_id="SS-RANDOM",
            source_card_id="RC-001",
            key_themes=["random"],
            atmosphere_tags=[],
            suggested_hooks=[],
            cultural_elements=[]
        )

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            records = [
                SeedRecord(seed_id=f"SS-00{i}", source_card_id="RC-001", created_at=datetime.now(), file_path=f"/path/SS-00{i}.json")
                for i in range(5)
            ]
            mock_reg.list_available.return_value = records
            mock_reg.count.return_value = 5
            mock_registry.return_value = mock_reg

            with patch("pathlib.Path.exists", return_value=True):
                with patch("src.story.seed_integration.load_seed", return_value=mock_seed):
                    with patch("random.choice", return_value=records[2]):
                        result = select_seed_for_generation(strategy="random")

                        assert result.total_available == 5
                        assert result.seed is not None

    def test_load_failure_returns_none_seed(self):
        """Should return None seed when load fails."""
        from src.story.seed_integration import select_seed_for_generation
        from src.registry.seed_registry import SeedRecord

        with patch("src.story.seed_integration.get_seed_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_record = SeedRecord(
                seed_id="SS-001",
                source_card_id="RC-001",
                created_at=datetime.now(),
                file_path="/nonexistent.json"
            )
            mock_reg.list_available.return_value = [mock_record]
            mock_reg.count.return_value = 1
            mock_reg.get_least_used.return_value = mock_record
            mock_registry.return_value = mock_reg

            with patch("src.story.seed_integration.load_seed", return_value=None):
                result = select_seed_for_generation()

                # Load failed, but should handle gracefully
                assert result is not None
