"""
Tests for canonical affinity to canonical core collapsing.
"""

import pytest

from src.research.executor.canonical_collapse import (
    collapse_canonical_affinity,
    validate_canonical_core,
    select_primary_fear,
    select_single_value,
    VALID_SETTINGS,
    VALID_PRIMARY_FEARS,
)


class TestCanonicalCollapse:
    """Tests for collapsing canonical_affinity to canonical_core."""

    def test_collapse_single_values(self):
        """Single values in affinity should pass through."""
        affinity = {
            "setting": ["apartment"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        core = collapse_canonical_affinity(affinity)

        assert core["setting_archetype"] == "apartment"
        assert core["primary_fear"] == "isolation"
        assert core["antagonist_archetype"] == "system"
        assert core["threat_mechanism"] == "surveillance"
        assert core["twist_family"] == "inevitability"  # default

    def test_collapse_multiple_values_uses_first(self):
        """Multiple values should use first valid."""
        affinity = {
            "setting": ["apartment", "rural", "hospital"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        core = collapse_canonical_affinity(affinity)
        assert core["setting_archetype"] == "apartment"

    def test_collapse_empty_uses_defaults(self):
        """Empty affinity should use sensible defaults."""
        affinity = {}

        core = collapse_canonical_affinity(affinity)

        assert core["setting_archetype"] == "abstract"
        assert core["primary_fear"] == "isolation"
        assert core["antagonist_archetype"] == "unknown"
        assert core["threat_mechanism"] == "erosion"
        assert core["twist_family"] == "inevitability"

    def test_collapse_filters_invalid_values(self):
        """Invalid values should be filtered out."""
        affinity = {
            "setting": ["invalid_setting", "apartment"],  # first is invalid
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        core = collapse_canonical_affinity(affinity)
        assert core["setting_archetype"] == "apartment"  # skips invalid

    def test_collapse_with_twist(self):
        """Twist value should be included if provided."""
        affinity = {
            "setting": ["apartment"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"],
            "twist": ["revelation"]
        }

        core = collapse_canonical_affinity(affinity)
        assert core["twist_family"] == "revelation"


class TestPrimaryFearPriority:
    """Tests for primary_fear priority selection."""

    def test_most_fundamental_wins(self):
        """Most fundamental fear should win."""
        # annihilation is most fundamental
        values = ["isolation", "annihilation", "contamination"]
        result = select_primary_fear(values)
        assert result == "annihilation"

    def test_identity_over_autonomy(self):
        """identity_erasure > loss_of_autonomy."""
        values = ["loss_of_autonomy", "identity_erasure"]
        result = select_primary_fear(values)
        assert result == "identity_erasure"

    def test_single_value(self):
        """Single value should be returned."""
        values = ["contamination"]
        result = select_primary_fear(values)
        assert result == "contamination"

    def test_empty_returns_none(self):
        """Empty list should return None."""
        result = select_primary_fear([])
        assert result is None

    def test_invalid_values_filtered(self):
        """Invalid values should be filtered."""
        values = ["invalid_fear", "isolation"]
        result = select_primary_fear(values)
        assert result == "isolation"


class TestValidation:
    """Tests for canonical_core validation."""

    def test_valid_core(self):
        """Valid core should pass validation."""
        core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        is_valid, error = validate_canonical_core(core)
        assert is_valid is True
        assert error is None

    def test_missing_field(self):
        """Missing field should fail validation."""
        core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            # missing antagonist_archetype
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        is_valid, error = validate_canonical_core(core)
        assert is_valid is False
        assert "Missing required field" in error

    def test_invalid_value(self):
        """Invalid value should fail validation."""
        core = {
            "setting_archetype": "invalid_setting",  # invalid
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        is_valid, error = validate_canonical_core(core)
        assert is_valid is False
        assert "Invalid value" in error

    def test_all_dimensions_required(self):
        """All 5 dimensions must be present."""
        core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation"
        }

        is_valid, error = validate_canonical_core(core)
        assert is_valid is False


class TestSingleValueSelection:
    """Tests for single value selection helper."""

    def test_first_valid_selected(self):
        """First valid value should be selected."""
        values = ["apartment", "hospital"]
        result = select_single_value(values, VALID_SETTINGS)
        assert result == "apartment"

    def test_filters_invalid(self):
        """Invalid values should be skipped."""
        values = ["invalid", "apartment"]
        result = select_single_value(values, VALID_SETTINGS)
        assert result == "apartment"

    def test_empty_returns_none(self):
        """Empty list should return None."""
        result = select_single_value([], VALID_SETTINGS)
        assert result is None

    def test_all_invalid_returns_none(self):
        """All invalid values should return None."""
        values = ["invalid1", "invalid2"]
        result = select_single_value(values, VALID_SETTINGS)
        assert result is None
