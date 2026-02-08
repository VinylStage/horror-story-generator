"""
Tests for story signature computation.

Covers:
- normalize_canonical_core()
- compute_story_signature()
- compute_signature_preview()
"""

import pytest

from src.story.dedup.story_signature import (
    normalize_canonical_core,
    compute_story_signature,
    compute_signature_preview,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FULL_CANONICAL_CORE = {
    "setting_archetype": "apartment",
    "primary_fear": "isolation",
    "antagonist_archetype": "system",
    "threat_mechanism": "surveillance",
    "twist_family": "inevitability",
}

SHORT_CANONICAL_CORE = {
    "setting": "apartment",
    "primary_fear": "isolation",
    "antagonist": "system",
    "mechanism": "surveillance",
    "twist": "inevitability",
}

RESEARCH_IDS = ["RC-20260112-082330", "RC-20260113-143052"]

SHA256_HEX_LENGTH = 64


# ===========================================================================
# normalize_canonical_core
# ===========================================================================
class TestNormalizeCanonicalCore:
    """Tests for normalize_canonical_core()."""

    def test_none_input_returns_empty_dict(self):
        assert normalize_canonical_core(None) == {}

    def test_empty_dict_returns_empty_dict(self):
        assert normalize_canonical_core({}) == {}

    def test_full_names_pass_through(self):
        result = normalize_canonical_core(FULL_CANONICAL_CORE)
        for key in FULL_CANONICAL_CORE:
            assert key in result
            assert result[key] == FULL_CANONICAL_CORE[key]

    def test_short_names_mapped_to_full(self):
        result = normalize_canonical_core(SHORT_CANONICAL_CORE)
        assert result["setting_archetype"] == "apartment"
        assert result["antagonist_archetype"] == "system"
        assert result["threat_mechanism"] == "surveillance"
        assert result["twist_family"] == "inevitability"
        # primary_fear has no short alias — stays as-is
        assert result["primary_fear"] == "isolation"

    def test_unknown_keys_pass_through(self):
        data = {"custom_dimension": "value", "another": "thing"}
        result = normalize_canonical_core(data)
        assert result["custom_dimension"] == "value"
        assert result["another"] == "thing"

    def test_output_is_alphabetically_sorted(self):
        data = {"twist": "x", "setting": "y", "primary_fear": "z"}
        result = normalize_canonical_core(data)
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_mixed_short_and_full_names(self):
        data = {
            "setting_archetype": "apartment",
            "antagonist": "system",  # short
            "primary_fear": "isolation",
        }
        result = normalize_canonical_core(data)
        assert "setting_archetype" in result
        assert "antagonist_archetype" in result
        assert "primary_fear" in result

    @pytest.mark.parametrize(
        "short,full",
        [
            ("setting", "setting_archetype"),
            ("antagonist", "antagonist_archetype"),
            ("mechanism", "threat_mechanism"),
            ("twist", "twist_family"),
        ],
    )
    def test_each_short_name_mapping(self, short, full):
        result = normalize_canonical_core({short: "test_value"})
        assert full in result
        assert result[full] == "test_value"


# ===========================================================================
# compute_story_signature
# ===========================================================================
class TestComputeStorySignature:
    """Tests for compute_story_signature()."""

    def test_returns_64_char_hex(self):
        sig = compute_story_signature(FULL_CANONICAL_CORE, RESEARCH_IDS)
        assert len(sig) == SHA256_HEX_LENGTH
        assert all(c in "0123456789abcdef" for c in sig)

    def test_deterministic_same_inputs(self):
        sig1 = compute_story_signature(FULL_CANONICAL_CORE, RESEARCH_IDS)
        sig2 = compute_story_signature(FULL_CANONICAL_CORE, RESEARCH_IDS)
        assert sig1 == sig2

    def test_order_independent_research(self):
        """Research IDs in different order should produce the same signature."""
        sig_forward = compute_story_signature(
            FULL_CANONICAL_CORE, ["RC-A", "RC-B", "RC-C"]
        )
        sig_reverse = compute_story_signature(
            FULL_CANONICAL_CORE, ["RC-C", "RC-A", "RC-B"]
        )
        assert sig_forward == sig_reverse

    def test_none_canonical_core(self):
        sig = compute_story_signature(None, RESEARCH_IDS)
        assert len(sig) == SHA256_HEX_LENGTH

    def test_none_research_used(self):
        sig = compute_story_signature(FULL_CANONICAL_CORE, None)
        assert len(sig) == SHA256_HEX_LENGTH

    def test_both_none(self):
        sig = compute_story_signature(None, None)
        assert len(sig) == SHA256_HEX_LENGTH

    def test_different_core_different_signature(self):
        core_a = {"setting_archetype": "apartment"}
        core_b = {"setting_archetype": "hospital"}
        sig_a = compute_story_signature(core_a, RESEARCH_IDS)
        sig_b = compute_story_signature(core_b, RESEARCH_IDS)
        assert sig_a != sig_b

    def test_different_research_different_signature(self):
        sig_a = compute_story_signature(FULL_CANONICAL_CORE, ["RC-A"])
        sig_b = compute_story_signature(FULL_CANONICAL_CORE, ["RC-B"])
        assert sig_a != sig_b

    def test_short_and_full_names_produce_same_signature(self):
        """Short-name core normalizes to full-name core => same signature."""
        sig_full = compute_story_signature(FULL_CANONICAL_CORE, RESEARCH_IDS)
        sig_short = compute_story_signature(SHORT_CANONICAL_CORE, RESEARCH_IDS)
        assert sig_full == sig_short

    def test_empty_research_list(self):
        sig = compute_story_signature(FULL_CANONICAL_CORE, [])
        assert len(sig) == SHA256_HEX_LENGTH


# ===========================================================================
# compute_signature_preview
# ===========================================================================
class TestComputeSignaturePreview:
    """Tests for compute_signature_preview()."""

    def test_returns_dict_with_required_keys(self):
        result = compute_signature_preview(FULL_CANONICAL_CORE, RESEARCH_IDS)
        assert "signature" in result
        assert "signature_short" in result
        assert "normalized_core" in result
        assert "sorted_research" in result
        assert "json_input" in result

    def test_signature_matches_compute(self):
        """Preview signature must match compute_story_signature."""
        preview = compute_signature_preview(FULL_CANONICAL_CORE, RESEARCH_IDS)
        direct = compute_story_signature(FULL_CANONICAL_CORE, RESEARCH_IDS)
        assert preview["signature"] == direct

    def test_signature_short_is_first_16_chars(self):
        preview = compute_signature_preview(FULL_CANONICAL_CORE, RESEARCH_IDS)
        assert preview["signature_short"] == preview["signature"][:16]
        assert len(preview["signature_short"]) == 16

    def test_normalized_core_is_sorted(self):
        preview = compute_signature_preview(SHORT_CANONICAL_CORE, RESEARCH_IDS)
        keys = list(preview["normalized_core"].keys())
        assert keys == sorted(keys)

    def test_sorted_research_is_sorted(self):
        preview = compute_signature_preview(
            FULL_CANONICAL_CORE, ["RC-C", "RC-A", "RC-B"]
        )
        assert preview["sorted_research"] == ["RC-A", "RC-B", "RC-C"]

    def test_json_input_is_valid_json(self):
        import json

        preview = compute_signature_preview(FULL_CANONICAL_CORE, RESEARCH_IDS)
        parsed = json.loads(preview["json_input"])
        assert "canonical_core" in parsed
        assert "research_used" in parsed

    def test_none_inputs(self):
        preview = compute_signature_preview(None, None)
        assert preview["normalized_core"] == {}
        assert preview["sorted_research"] == []
        assert len(preview["signature"]) == SHA256_HEX_LENGTH
