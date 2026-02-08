"""
Tests for story_dedup_check module — hybrid dedup, logging, and semantic index.

Covers functionality NOT already tested in test_story_dedup.py:
1. check_story_duplicate() with dedup disabled via env
2. check_story_duplicate_hybrid(): semantic disabled fallback, ImportError,
   hybrid integration, strict mode
3. log_dedup_decision(): DUPLICATE/UNIQUE logging, semantic info
4. add_story_to_semantic_index(): disabled path, import handling
5. StoryDedupResult.to_dict(): semantic fields, rounding
"""

import logging
import pytest
from unittest.mock import MagicMock, patch

from src.story.dedup.story_dedup_check import (
    check_story_duplicate,
    check_story_duplicate_hybrid,
    log_dedup_decision,
    add_story_to_semantic_index,
    StoryDedupResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CANONICAL_CORE = {
    "setting": "apartment",
    "primary_fear": "isolation",
    "antagonist": "system",
    "mechanism": "surveillance",
    "twist": "inevitability",
}
RESEARCH_USED = ["RC-001", "RC-002"]
STORY_DATA = {"title": "The Watching Walls", "body": "A story about surveillance."}
EXISTING_MATCH = {
    "id": "story_existing",
    "created_at": "2026-01-15T10:00:00",
}
TEMPLATE_ID = "T-001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_registry():
    """Registry mock that finds no duplicates by default."""
    reg = MagicMock()
    reg.find_by_signature.return_value = None
    return reg


@pytest.fixture()
def mock_registry_with_match():
    """Registry mock that returns an existing match."""
    reg = MagicMock()
    reg.find_by_signature.return_value = EXISTING_MATCH
    return reg


# ---------------------------------------------------------------------------
# check_story_duplicate — dedup disabled
# ---------------------------------------------------------------------------
class TestCheckStoryDuplicateDisabled:
    """Tests for check_story_duplicate when ENABLE_STORY_DEDUP=false."""

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", False)
    def test_returns_unique_when_disabled(self, mock_registry_with_match):
        """Should short-circuit to 'unique' when dedup is disabled."""
        result = check_story_duplicate(
            CANONICAL_CORE, RESEARCH_USED, registry=mock_registry_with_match,
        )

        assert result.is_duplicate is False
        assert result.reason == "dedup_disabled"
        mock_registry_with_match.find_by_signature.assert_not_called()


# ---------------------------------------------------------------------------
# check_story_duplicate_hybrid
# ---------------------------------------------------------------------------
class TestCheckStoryDuplicateHybrid:
    """Tests for check_story_duplicate_hybrid()."""

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", False)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    def test_semantic_disabled_falls_back_to_signature(self, mock_registry):
        """When semantic dedup is disabled, should use signature-only."""
        result = check_story_duplicate_hybrid(
            CANONICAL_CORE, RESEARCH_USED, STORY_DATA, registry=mock_registry,
        )

        assert result.is_duplicate is False
        assert result.reason == "unique"

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", False)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.STORY_DEDUP_STRICT", False)
    def test_semantic_disabled_strict_with_signature_match(self, mock_registry_with_match):
        """Semantic disabled + signature match + strict should raise ValueError."""
        with pytest.raises(ValueError, match="duplicate detected"):
            check_story_duplicate_hybrid(
                CANONICAL_CORE, RESEARCH_USED, STORY_DATA,
                registry=mock_registry_with_match, strict=True,
            )

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    def test_import_error_falls_back_to_signature(self, mock_registry):
        """ImportError on hybrid module should gracefully fall back."""
        with patch(
            "src.story.dedup.story_dedup_check.check_story_duplicate_hybrid.__module__",
            new="src.story.dedup.story_dedup_check",
        ):
            # Simulate ImportError by patching the import inside the function
            with patch.dict(
                "sys.modules",
                {"src.dedup.story.hybrid_dedup": None},
            ):
                import importlib
                # The function uses a try/except ImportError internally
                result = check_story_duplicate_hybrid(
                    CANONICAL_CORE, RESEARCH_USED, STORY_DATA, registry=mock_registry,
                )

                assert result.is_duplicate is False

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    def test_hybrid_check_updates_result_with_semantic_scores(self, mock_registry):
        """Successful hybrid check should populate semantic fields."""
        mock_hybrid_result = MagicMock()
        mock_hybrid_result.semantic_score = 0.87
        mock_hybrid_result.hybrid_score = 0.91
        mock_hybrid_result.nearest_story_id = "story_nearest"
        mock_hybrid_result.is_duplicate = True

        with patch(
            "src.story.dedup.story_dedup_check.check_hybrid_duplicate",
            create=True,
        ) as mock_hybrid_fn:
            mock_hybrid_fn.return_value = mock_hybrid_result

            # Patch the import to succeed
            import types
            fake_module = types.ModuleType("src.dedup.story.hybrid_dedup")
            fake_module.check_hybrid_duplicate = mock_hybrid_fn

            with patch.dict("sys.modules", {"src.dedup.story.hybrid_dedup": fake_module}):
                result = check_story_duplicate_hybrid(
                    CANONICAL_CORE, RESEARCH_USED, STORY_DATA, registry=mock_registry,
                )

        assert result.semantic_score == 0.87
        assert result.hybrid_score == 0.91
        assert result.nearest_story_id == "story_nearest"
        assert result.is_duplicate is True
        assert "semantic_similar" in result.reason

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.STORY_DEDUP_STRICT", False)
    def test_hybrid_duplicate_strict_raises(self, mock_registry):
        """Hybrid duplicate + strict should raise ValueError."""
        mock_hybrid_result = MagicMock()
        mock_hybrid_result.semantic_score = 0.95
        mock_hybrid_result.hybrid_score = 0.97
        mock_hybrid_result.nearest_story_id = "story_nearest"
        mock_hybrid_result.is_duplicate = True

        import types
        fake_module = types.ModuleType("src.dedup.story.hybrid_dedup")
        fake_module.check_hybrid_duplicate = MagicMock(return_value=mock_hybrid_result)

        with patch.dict("sys.modules", {"src.dedup.story.hybrid_dedup": fake_module}):
            with pytest.raises(ValueError, match="duplicate detected"):
                check_story_duplicate_hybrid(
                    CANONICAL_CORE, RESEARCH_USED, STORY_DATA,
                    registry=mock_registry, strict=True,
                )

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    def test_hybrid_exception_falls_back_to_signature(self, mock_registry):
        """If hybrid check raises a non-import error, should fall back gracefully."""
        import types
        fake_module = types.ModuleType("src.dedup.story.hybrid_dedup")
        fake_module.check_hybrid_duplicate = MagicMock(
            side_effect=RuntimeError("FAISS error"),
        )

        with patch.dict("sys.modules", {"src.dedup.story.hybrid_dedup": fake_module}):
            result = check_story_duplicate_hybrid(
                CANONICAL_CORE, RESEARCH_USED, STORY_DATA, registry=mock_registry,
            )

        assert result.is_duplicate is False
        assert result.semantic_score == 0.0

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_DEDUP", True)
    def test_hybrid_not_duplicate_preserves_signature_unique(self, mock_registry):
        """If hybrid check says not duplicate, original unique result preserved."""
        mock_hybrid_result = MagicMock()
        mock_hybrid_result.semantic_score = 0.3
        mock_hybrid_result.hybrid_score = 0.25
        mock_hybrid_result.nearest_story_id = "story_other"
        mock_hybrid_result.is_duplicate = False

        import types
        fake_module = types.ModuleType("src.dedup.story.hybrid_dedup")
        fake_module.check_hybrid_duplicate = MagicMock(return_value=mock_hybrid_result)

        with patch.dict("sys.modules", {"src.dedup.story.hybrid_dedup": fake_module}):
            result = check_story_duplicate_hybrid(
                CANONICAL_CORE, RESEARCH_USED, STORY_DATA, registry=mock_registry,
            )

        assert result.is_duplicate is False
        assert result.semantic_score == 0.3
        assert result.hybrid_score == 0.25


# ---------------------------------------------------------------------------
# log_dedup_decision
# ---------------------------------------------------------------------------
class TestLogDedupDecision:
    """Tests for log_dedup_decision()."""

    def test_logs_unique_decision(self, caplog):
        """Should log UNIQUE status with template and research info."""
        result = StoryDedupResult(signature="a" * 64, is_duplicate=False, action="none")

        with caplog.at_level(logging.INFO, logger="src.story.dedup.story_dedup_check"):
            log_dedup_decision(result, template_id=TEMPLATE_ID, research_count=3)

        assert "UNIQUE" in caplog.text
        assert TEMPLATE_ID in caplog.text
        assert "3 cards" in caplog.text

    def test_logs_duplicate_decision(self, caplog):
        """Should log DUPLICATE status with existing story info."""
        result = StoryDedupResult(
            signature="b" * 64,
            is_duplicate=True,
            existing_story_id="story_existing",
            existing_created_at="2026-01-15T10:00:00",
            action="warn",
        )

        with caplog.at_level(logging.INFO, logger="src.story.dedup.story_dedup_check"):
            log_dedup_decision(result, template_id=TEMPLATE_ID, research_count=2)

        assert "DUPLICATE" in caplog.text
        assert "story_existing" in caplog.text

    def test_logs_semantic_info_when_present(self, caplog):
        """Should log semantic score when > 0."""
        result = StoryDedupResult(
            signature="c" * 64,
            is_duplicate=True,
            semantic_score=0.87,
            hybrid_score=0.91,
            nearest_story_id="story_nearest",
            action="warn",
        )

        with caplog.at_level(logging.INFO, logger="src.story.dedup.story_dedup_check"):
            log_dedup_decision(result)

        assert "0.8700" in caplog.text
        assert "0.9100" in caplog.text
        assert "story_nearest" in caplog.text

    def test_no_semantic_log_when_score_zero(self, caplog):
        """Should not log semantic info when score is 0."""
        result = StoryDedupResult(
            signature="d" * 64,
            is_duplicate=False,
            semantic_score=0.0,
        )

        with caplog.at_level(logging.INFO, logger="src.story.dedup.story_dedup_check"):
            log_dedup_decision(result)

        assert "Semantic:" not in caplog.text


# ---------------------------------------------------------------------------
# add_story_to_semantic_index
# ---------------------------------------------------------------------------
class TestAddStoryToSemanticIndex:
    """Tests for add_story_to_semantic_index()."""

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", False)
    def test_returns_false_when_disabled(self):
        """Should return False when semantic dedup is disabled."""
        result = add_story_to_semantic_index("story_001", STORY_DATA)
        assert result is False

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    def test_import_error_returns_false(self):
        """Should return False when semantic_dedup module is unavailable."""
        with patch.dict("sys.modules", {"src.dedup.story.semantic_dedup": None}):
            result = add_story_to_semantic_index("story_001", STORY_DATA)
            assert result is False

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    def test_success_returns_true(self):
        """Should return True when add_story_to_index succeeds."""
        import types
        fake_module = types.ModuleType("src.dedup.story.semantic_dedup")
        fake_module.add_story_to_index = MagicMock(return_value=True)

        with patch.dict("sys.modules", {"src.dedup.story.semantic_dedup": fake_module}):
            result = add_story_to_semantic_index("story_001", STORY_DATA)

        assert result is True
        fake_module.add_story_to_index.assert_called_once_with(STORY_DATA, "story_001")

    @patch("src.story.dedup.story_dedup_check.ENABLE_STORY_SEMANTIC_DEDUP", True)
    def test_runtime_error_returns_false(self):
        """Should return False on general exception."""
        import types
        fake_module = types.ModuleType("src.dedup.story.semantic_dedup")
        fake_module.add_story_to_index = MagicMock(
            side_effect=RuntimeError("FAISS error"),
        )

        with patch.dict("sys.modules", {"src.dedup.story.semantic_dedup": fake_module}):
            result = add_story_to_semantic_index("story_001", STORY_DATA)

        assert result is False


# ---------------------------------------------------------------------------
# StoryDedupResult.to_dict
# ---------------------------------------------------------------------------
class TestStoryDedupResultToDict:
    """Tests for StoryDedupResult.to_dict() — semantic fields and rounding."""

    def test_unique_result_no_semantic_fields(self):
        """Unique result with zero scores should not include semantic keys."""
        result = StoryDedupResult(
            signature="abc123",
            is_duplicate=False,
            reason="unique",
            action="none",
        )

        d = result.to_dict()

        assert d["story_dedup_result"] == "unique"
        assert "semantic_similarity_score" not in d
        assert "hybrid_dedup_score" not in d
        assert "nearest_story_id" not in d

    def test_semantic_fields_included_when_positive(self):
        """Semantic scores > 0 should appear in dict output."""
        result = StoryDedupResult(
            signature="abc123",
            is_duplicate=True,
            reason="semantic_similar_to_story_x",
            action="warn",
            semantic_score=0.87654,
            hybrid_score=0.91234,
            nearest_story_id="story_x",
        )

        d = result.to_dict()

        assert d["semantic_similarity_score"] == 0.8765
        assert d["hybrid_dedup_score"] == 0.9123
        assert d["nearest_story_id"] == "story_x"

    def test_rounding_to_four_decimals(self):
        """Scores should be rounded to exactly 4 decimal places."""
        result = StoryDedupResult(
            signature="abc",
            semantic_score=0.123456789,
            hybrid_score=0.999999999,
        )

        d = result.to_dict()

        assert d["semantic_similarity_score"] == 0.1235
        assert d["hybrid_dedup_score"] == 1.0

    def test_nearest_story_id_only_when_present(self):
        """nearest_story_id should only appear when not None."""
        result = StoryDedupResult(
            signature="abc",
            semantic_score=0.5,
            nearest_story_id=None,
        )

        d = result.to_dict()

        assert "semantic_similarity_score" in d
        assert "nearest_story_id" not in d

    @pytest.mark.parametrize(
        "is_dup, expected",
        [
            (True, "duplicate"),
            (False, "unique"),
        ],
    )
    def test_dedup_result_field(self, is_dup, expected):
        """story_dedup_result field should reflect is_duplicate boolean."""
        result = StoryDedupResult(signature="x", is_duplicate=is_dup)
        d = result.to_dict()
        assert d["story_dedup_result"] == expected

    def test_all_base_fields_present(self):
        """All base fields should always be present regardless of state."""
        result = StoryDedupResult(
            signature="sig123",
            is_duplicate=False,
            existing_story_id=None,
            reason="unique",
            action="none",
        )

        d = result.to_dict()

        assert "story_signature" in d
        assert "story_dedup_result" in d
        assert "story_dedup_reason" in d
        assert "story_dedup_action" in d
        assert "story_dedup_existing_id" in d
