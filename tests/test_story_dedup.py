"""
Tests for story-level deduplication.

Verifies:
1. Same canonical_core + research_used → same signature
2. Different research_used → different signature
3. Dedup check triggers on second generation
4. STRICT mode aborts generation
"""

import json
import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from src.story.dedup.story_signature import (
    compute_story_signature,
    normalize_canonical_core,
    compute_signature_preview,
)
from src.story.dedup.story_dedup_check import (
    check_story_duplicate,
    StoryDedupResult,
)


# =============================================================================
# Story Signature Tests
# =============================================================================

class TestStorySignature:
    """Tests for story signature computation."""

    def test_same_inputs_same_signature(self):
        """Same canonical_core + research_used should produce same signature."""
        canonical_core = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance",
            "twist": "inevitability"
        }
        research_used = ["RC-20260112-082330", "RC-20260112-082845"]

        sig1 = compute_story_signature(canonical_core, research_used)
        sig2 = compute_story_signature(canonical_core, research_used)

        assert sig1 == sig2
        assert len(sig1) == 64  # SHA256 hex

    def test_different_research_different_signature(self):
        """Different research_used should produce different signature."""
        canonical_core = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance",
            "twist": "inevitability"
        }

        sig1 = compute_story_signature(canonical_core, ["RC-001"])
        sig2 = compute_story_signature(canonical_core, ["RC-002"])

        assert sig1 != sig2

    def test_different_canonical_core_different_signature(self):
        """Different canonical_core should produce different signature."""
        research_used = ["RC-001"]

        sig1 = compute_story_signature(
            {"setting": "apartment", "primary_fear": "isolation"},
            research_used
        )
        sig2 = compute_story_signature(
            {"setting": "hospital", "primary_fear": "isolation"},
            research_used
        )

        assert sig1 != sig2

    def test_research_order_independent(self):
        """Research list order should not affect signature (sorted internally)."""
        canonical_core = {"setting": "apartment"}

        sig1 = compute_story_signature(canonical_core, ["RC-001", "RC-002"])
        sig2 = compute_story_signature(canonical_core, ["RC-002", "RC-001"])

        assert sig1 == sig2

    def test_empty_research_produces_signature(self):
        """Empty research list should still produce valid signature."""
        canonical_core = {"setting": "apartment"}

        sig1 = compute_story_signature(canonical_core, [])
        sig2 = compute_story_signature(canonical_core, None)

        assert sig1 == sig2
        assert len(sig1) == 64

    def test_empty_canonical_core_produces_signature(self):
        """Empty canonical_core should still produce valid signature."""
        sig1 = compute_story_signature({}, ["RC-001"])
        sig2 = compute_story_signature(None, ["RC-001"])

        assert sig1 == sig2
        assert len(sig1) == 64


class TestNormalizeCanonicalCore:
    """Tests for canonical core normalization."""

    def test_short_names_converted(self):
        """Short field names should be converted to full names."""
        short = {
            "setting": "apartment",
            "antagonist": "system",
            "mechanism": "surveillance",
            "twist": "inevitability"
        }

        normalized = normalize_canonical_core(short)

        assert "setting_archetype" in normalized
        assert "antagonist_archetype" in normalized
        assert "threat_mechanism" in normalized
        assert "twist_family" in normalized

    def test_full_names_preserved(self):
        """Full field names should be preserved."""
        full = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        normalized = normalize_canonical_core(full)

        assert normalized == full

    def test_keys_sorted_alphabetically(self):
        """Keys should be sorted alphabetically."""
        unordered = {
            "twist_family": "inevitability",
            "setting_archetype": "apartment",
            "primary_fear": "isolation"
        }

        normalized = normalize_canonical_core(unordered)
        keys = list(normalized.keys())

        assert keys == sorted(keys)

    def test_none_input_returns_empty(self):
        """None input should return empty dict."""
        assert normalize_canonical_core(None) == {}


class TestSignaturePreview:
    """Tests for signature preview (debugging)."""

    def test_preview_includes_all_fields(self):
        """Preview should include signature, normalized data, and JSON."""
        canonical_core = {"setting": "apartment"}
        research_used = ["RC-001"]

        preview = compute_signature_preview(canonical_core, research_used)

        assert "signature" in preview
        assert "signature_short" in preview
        assert "normalized_core" in preview
        assert "sorted_research" in preview
        assert "json_input" in preview

    def test_signature_short_is_16_chars(self):
        """Short signature should be 16 characters."""
        preview = compute_signature_preview({"setting": "apartment"}, ["RC-001"])
        assert len(preview["signature_short"]) == 16


# =============================================================================
# Story Dedup Check Tests
# =============================================================================

class TestStoryDedupCheck:
    """Tests for story dedup checking."""

    def test_no_registry_returns_no_duplicate(self):
        """Without registry, should return no duplicate."""
        result = check_story_duplicate(
            {"setting": "apartment"},
            ["RC-001"],
            registry=None
        )

        assert result.is_duplicate is False
        assert result.reason == "no_registry"

    def test_unique_signature_returns_unique(self):
        """Unique signature should return unique result."""
        mock_registry = MagicMock()
        mock_registry.find_by_signature.return_value = None

        result = check_story_duplicate(
            {"setting": "apartment"},
            ["RC-001"],
            registry=mock_registry
        )

        assert result.is_duplicate is False
        assert result.reason == "unique"

    def test_duplicate_signature_detected(self):
        """Duplicate signature should be detected."""
        mock_registry = MagicMock()
        mock_registry.find_by_signature.return_value = {
            "id": "20260112_123456",
            "created_at": "2026-01-12T12:34:56",
            "title": "Existing Story"
        }

        result = check_story_duplicate(
            {"setting": "apartment"},
            ["RC-001"],
            registry=mock_registry,
            strict=False
        )

        assert result.is_duplicate is True
        assert result.existing_story_id == "20260112_123456"
        assert result.action == "warn"

    def test_strict_mode_raises_on_duplicate(self):
        """STRICT mode should raise ValueError on duplicate."""
        mock_registry = MagicMock()
        mock_registry.find_by_signature.return_value = {
            "id": "20260112_123456",
            "created_at": "2026-01-12T12:34:56"
        }

        with pytest.raises(ValueError) as exc_info:
            check_story_duplicate(
                {"setting": "apartment"},
                ["RC-001"],
                registry=mock_registry,
                strict=True
            )

        assert "duplicate detected" in str(exc_info.value).lower()


class TestStoryDedupResult:
    """Tests for StoryDedupResult dataclass."""

    def test_to_dict_unique(self):
        """Unique result should serialize correctly."""
        result = StoryDedupResult(
            signature="abc123",
            is_duplicate=False,
            reason="unique"
        )

        d = result.to_dict()

        assert d["story_signature"] == "abc123"
        assert d["story_dedup_result"] == "unique"
        assert d["story_dedup_reason"] == "unique"

    def test_to_dict_duplicate(self):
        """Duplicate result should serialize correctly."""
        result = StoryDedupResult(
            signature="abc123",
            is_duplicate=True,
            existing_story_id="old_story",
            reason="duplicate_of_old_story",
            action="warn"
        )

        d = result.to_dict()

        assert d["story_dedup_result"] == "duplicate"
        assert d["story_dedup_existing_id"] == "old_story"


# =============================================================================
# Integration Tests
# =============================================================================

class TestStoryDedupIntegration:
    """Integration tests for story dedup with registry."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        from src.registry.story_registry import StoryRegistry
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_registry.db")
            registry = StoryRegistry(db_path=db_path)
            yield registry
            registry.close()

    def test_registry_schema_migration(self, temp_registry):
        """Registry should have v1.1.0 schema with new columns."""
        # Check that we can add a story with new fields
        temp_registry.add_story(
            story_id="test_001",
            title="Test Story",
            template_id="T-001",
            template_name="Test Template",
            semantic_summary="Test summary",
            accepted=True,
            decision_reason="test",
            story_signature="abc123def456",
            canonical_core_json='{"setting": "apartment"}',
            research_used_json='["RC-001"]'
        )

        # Should be findable by signature
        found = temp_registry.find_by_signature("abc123def456")
        assert found is not None
        assert found["id"] == "test_001"

    def test_duplicate_detection_end_to_end(self, temp_registry):
        """Full flow: add story, then detect duplicate."""
        canonical_core = {"setting": "apartment", "primary_fear": "isolation"}
        research_used = ["RC-001", "RC-002"]

        # Compute signature
        signature = compute_story_signature(canonical_core, research_used)

        # Add first story
        temp_registry.add_story(
            story_id="story_001",
            title="First Story",
            template_id="T-001",
            template_name="Template",
            semantic_summary="Summary",
            accepted=True,
            decision_reason="test",
            story_signature=signature,
            canonical_core_json=json.dumps(canonical_core),
            research_used_json=json.dumps(research_used)
        )

        # Check for duplicate
        result = check_story_duplicate(
            canonical_core,
            research_used,
            registry=temp_registry
        )

        assert result.is_duplicate is True
        assert result.existing_story_id == "story_001"

    def test_different_research_not_duplicate(self, temp_registry):
        """Different research should not be detected as duplicate."""
        canonical_core = {"setting": "apartment"}

        # Add first story with research ["RC-001"]
        sig1 = compute_story_signature(canonical_core, ["RC-001"])
        temp_registry.add_story(
            story_id="story_001",
            title="First Story",
            template_id="T-001",
            template_name="Template",
            semantic_summary="Summary",
            accepted=True,
            decision_reason="test",
            story_signature=sig1
        )

        # Check with different research ["RC-002"]
        result = check_story_duplicate(
            canonical_core,
            ["RC-002"],
            registry=temp_registry
        )

        assert result.is_duplicate is False
