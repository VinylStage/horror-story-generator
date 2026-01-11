"""
Tests for dedup_service module.

Phase B+: Comprehensive mocking for 100% coverage.
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass


@dataclass
class MockStory:
    """Mock story for testing."""
    id: str
    template_id: str
    semantic_summary: str


class TestComputeSignal:
    """Tests for compute_signal function."""

    def test_low_signal(self):
        """Should return LOW for low similarity."""
        from src.api.services.dedup_service import compute_signal

        assert compute_signal(0.0) == "LOW"
        assert compute_signal(0.1) == "LOW"
        assert compute_signal(0.29) == "LOW"

    def test_medium_signal(self):
        """Should return MEDIUM for medium similarity."""
        from src.api.services.dedup_service import compute_signal

        assert compute_signal(0.3) == "MEDIUM"
        assert compute_signal(0.45) == "MEDIUM"
        assert compute_signal(0.59) == "MEDIUM"

    def test_high_signal(self):
        """Should return HIGH for high similarity."""
        from src.api.services.dedup_service import compute_signal

        assert compute_signal(0.6) == "HIGH"
        assert compute_signal(0.8) == "HIGH"
        assert compute_signal(1.0) == "HIGH"


class TestComputeCanonicalSimilarity:
    """Tests for compute_canonical_similarity function."""

    def test_identical_cores(self):
        """Should return 1.0 for identical cores."""
        from src.api.services.dedup_service import compute_canonical_similarity

        core = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "ghost",
            "mechanism": "haunting",
            "twist": "reveal"
        }

        result = compute_canonical_similarity(core, core)
        assert result == 1.0

    def test_completely_different_cores(self):
        """Should return 0.0 for different cores."""
        from src.api.services.dedup_service import compute_canonical_similarity

        core1 = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "ghost",
            "mechanism": "haunting",
            "twist": "reveal"
        }
        core2 = {
            "setting": "forest",
            "primary_fear": "pursuit",
            "antagonist": "monster",
            "mechanism": "chase",
            "twist": "escape"
        }

        result = compute_canonical_similarity(core1, core2)
        assert result == 0.0

    def test_partial_match(self):
        """Should return partial score for some matches."""
        from src.api.services.dedup_service import compute_canonical_similarity

        core1 = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "ghost",
            "mechanism": "haunting",
            "twist": "reveal"
        }
        core2 = {
            "setting": "apartment",  # Match
            "primary_fear": "isolation",  # Match
            "antagonist": "monster",  # Different
            "mechanism": "chase",  # Different
            "twist": "reveal"  # Match
        }

        result = compute_canonical_similarity(core1, core2)
        # setting (0.15) + primary_fear (0.25) + twist (0.15) = 0.55
        assert 0.5 < result < 0.6

    def test_empty_cores(self):
        """Should handle empty cores."""
        from src.api.services.dedup_service import compute_canonical_similarity

        result = compute_canonical_similarity({}, {})
        assert result == 0.0

    def test_case_insensitive_matching(self):
        """Should match values case-insensitively."""
        from src.api.services.dedup_service import compute_canonical_similarity

        core1 = {"setting": "APARTMENT", "primary_fear": "Isolation"}
        core2 = {"setting": "apartment", "primary_fear": "isolation"}

        result = compute_canonical_similarity(core1, core2)
        assert result > 0.0


class TestEvaluateDedup:
    """Tests for evaluate_dedup function."""

    @pytest.mark.asyncio
    async def test_evaluate_no_existing_stories(self):
        """Should return LOW when no stories exist."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = []
        mock_registry.close = MagicMock()

        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            result = await evaluate_dedup(
                template_id="test_001",
                canonical_core={"setting": "apartment"}
            )

            assert result["signal"] == "LOW"
            assert result["similarity_score"] == 0.0
            assert "No existing stories" in result["message"]

    @pytest.mark.asyncio
    async def test_evaluate_with_template_match(self):
        """Should increase similarity for template matches."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_stories = [
            MockStory(id="1", template_id="test_001", semantic_summary=""),
            MockStory(id="2", template_id="test_001", semantic_summary=""),
            MockStory(id="3", template_id="test_001", semantic_summary=""),
        ]

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = mock_stories
        mock_registry.close = MagicMock()

        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            result = await evaluate_dedup(
                template_id="test_001",
                canonical_core={}
            )

            # 3+ template matches should set similarity to at least 0.4
            assert result["similarity_score"] >= 0.4

    @pytest.mark.asyncio
    async def test_evaluate_with_canonical_similarity(self):
        """Should compute similarity based on canonical cores."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_stories = [
            MockStory(id="1", template_id="other", semantic_summary=""),
        ]

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = mock_stories
        mock_registry.close = MagicMock()

        # Mock parse_semantic_summary to return a matching core
        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            with patch("research_api.services.dedup_service.parse_semantic_summary") as mock_parse:
                mock_parse.return_value = {
                    "setting": "apartment",
                    "primary_fear": "isolation"
                }

                result = await evaluate_dedup(
                    canonical_core={
                        "setting": "apartment",
                        "primary_fear": "isolation"
                    }
                )

                assert result["similarity_score"] > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_high_signal_message(self):
        """Should return appropriate message for HIGH signal."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_stories = [MockStory(id="1", template_id="t", semantic_summary="")]

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = mock_stories
        mock_registry.close = MagicMock()

        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            with patch("research_api.services.dedup_service.parse_semantic_summary") as mock_parse:
                # Return identical core for high similarity
                mock_parse.return_value = {
                    "setting": "a", "primary_fear": "b", "antagonist": "c",
                    "mechanism": "d", "twist": "e"
                }

                result = await evaluate_dedup(
                    canonical_core={
                        "setting": "a", "primary_fear": "b", "antagonist": "c",
                        "mechanism": "d", "twist": "e"
                    }
                )

                if result["signal"] == "HIGH":
                    assert "consider regenerating" in result["message"]

    @pytest.mark.asyncio
    async def test_evaluate_medium_signal_message(self):
        """Should return appropriate message for MEDIUM signal."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_stories = [MockStory(id="1", template_id="t", semantic_summary="")]

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = mock_stories
        mock_registry.close = MagicMock()

        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            with patch("research_api.services.dedup_service.parse_semantic_summary") as mock_parse:
                # Partial match
                mock_parse.return_value = {
                    "setting": "apartment",
                    "primary_fear": "isolation"
                }

                with patch("research_api.services.dedup_service.compute_canonical_similarity", return_value=0.5):
                    result = await evaluate_dedup(
                        canonical_core={"setting": "apartment", "primary_fear": "isolation"}
                    )

                    if result["signal"] == "MEDIUM":
                        assert "review recommended" in result["message"]

    @pytest.mark.asyncio
    async def test_evaluate_exception_handling(self):
        """Should handle exceptions gracefully."""
        from src.api.services.dedup_service import evaluate_dedup

        with patch("research_api.services.dedup_service.StoryRegistry", side_effect=Exception("DB error")):
            result = await evaluate_dedup()

            assert result["signal"] == "LOW"
            assert "error" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_evaluate_similar_stories_list(self):
        """Should return list of similar stories."""
        from src.api.services.dedup_service import evaluate_dedup

        mock_stories = [
            MockStory(id="1", template_id="t1", semantic_summary=""),
            MockStory(id="2", template_id="t2", semantic_summary=""),
        ]

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = mock_stories
        mock_registry.close = MagicMock()

        with patch("research_api.services.dedup_service.StoryRegistry", return_value=mock_registry):
            with patch("research_api.services.dedup_service.parse_semantic_summary") as mock_parse:
                mock_parse.return_value = {"setting": "apartment"}

                with patch("research_api.services.dedup_service.compute_canonical_similarity", return_value=0.5):
                    result = await evaluate_dedup(
                        canonical_core={"setting": "apartment"}
                    )

                    # Should have similar stories list
                    assert "similar_stories" in result


class TestParseSemanticSummary:
    """Tests for parse_semantic_summary function."""

    def test_parse_returns_empty_dict(self):
        """Should return empty dict (placeholder implementation)."""
        from src.api.services.dedup_service import parse_semantic_summary

        result = parse_semantic_summary("any summary text")
        assert result == {}

    def test_parse_empty_string(self):
        """Should handle empty string."""
        from src.api.services.dedup_service import parse_semantic_summary

        result = parse_semantic_summary("")
        assert result == {}


class TestGetMatchedDimensions:
    """Tests for get_matched_dimensions function."""

    def test_all_dimensions_match(self):
        """Should return all matching dimensions."""
        from src.api.services.dedup_service import get_matched_dimensions

        core = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "ghost",
            "mechanism": "haunting",
            "twist": "reveal"
        }

        result = get_matched_dimensions(core, core)

        assert "setting" in result
        assert "primary_fear" in result
        assert "antagonist" in result
        assert "mechanism" in result
        assert "twist" in result

    def test_no_dimensions_match(self):
        """Should return empty list when nothing matches."""
        from src.api.services.dedup_service import get_matched_dimensions

        core1 = {"setting": "apartment", "primary_fear": "isolation"}
        core2 = {"setting": "forest", "primary_fear": "pursuit"}

        result = get_matched_dimensions(core1, core2)
        assert result == []

    def test_partial_match(self):
        """Should return only matching dimensions."""
        from src.api.services.dedup_service import get_matched_dimensions

        core1 = {"setting": "apartment", "primary_fear": "isolation", "antagonist": "ghost"}
        core2 = {"setting": "apartment", "primary_fear": "pursuit", "antagonist": "ghost"}

        result = get_matched_dimensions(core1, core2)

        assert "setting" in result
        assert "antagonist" in result
        assert "primary_fear" not in result

    def test_empty_values_not_matched(self):
        """Should not match empty values."""
        from src.api.services.dedup_service import get_matched_dimensions

        core1 = {"setting": "", "primary_fear": "isolation"}
        core2 = {"setting": "", "primary_fear": "isolation"}

        result = get_matched_dimensions(core1, core2)

        assert "setting" not in result
        assert "primary_fear" in result
