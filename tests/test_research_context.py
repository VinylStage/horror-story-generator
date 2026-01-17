"""
Tests for the unified research context module.

Tests the shared selector, policy, and formatter used by both CLI and API.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.infra.research_context.policy import (
    DedupLevel,
    get_dedup_level,
    is_usable_card,
    DEDUP_THRESHOLD_MEDIUM,
    DEDUP_THRESHOLD_HIGH,
)
from src.infra.research_context.selector import (
    ResearchSelection,
    TemplateSelection,
    compute_affinity_score,
    compute_reverse_affinity_score,
    select_research_for_template,
    select_templates_for_research,
)
from src.infra.research_context.formatter import (
    build_research_context,
    format_research_for_prompt,
    format_research_for_metadata,
)


# =============================================================================
# Policy Tests
# =============================================================================

class TestDedupPolicy:
    """Tests for dedup level policy."""

    def test_get_dedup_level_low(self):
        """Similarity < 0.70 should be LOW."""
        assert get_dedup_level(0.0) == DedupLevel.LOW
        assert get_dedup_level(0.5) == DedupLevel.LOW
        assert get_dedup_level(0.69) == DedupLevel.LOW

    def test_get_dedup_level_medium(self):
        """0.70 <= similarity < 0.85 should be MEDIUM."""
        assert get_dedup_level(0.70) == DedupLevel.MEDIUM
        assert get_dedup_level(0.75) == DedupLevel.MEDIUM
        assert get_dedup_level(0.84) == DedupLevel.MEDIUM

    def test_get_dedup_level_high(self):
        """Similarity >= 0.85 should be HIGH."""
        assert get_dedup_level(0.85) == DedupLevel.HIGH
        assert get_dedup_level(0.90) == DedupLevel.HIGH
        assert get_dedup_level(1.0) == DedupLevel.HIGH

    def test_is_usable_card_low_dedup(self):
        """LOW dedup cards should be usable."""
        card = {
            "validation": {"quality_score": "good"},
            "dedup": {"level": "LOW", "similarity_score": 0.3}
        }
        assert is_usable_card(card) is True

    def test_is_usable_card_medium_dedup(self):
        """MEDIUM dedup cards should be usable by default."""
        card = {
            "validation": {"quality_score": "good"},
            "dedup": {"level": "MEDIUM", "similarity_score": 0.75}
        }
        assert is_usable_card(card) is True

    def test_is_usable_card_high_dedup_excluded(self):
        """HIGH dedup cards should be excluded by default."""
        card = {
            "validation": {"quality_score": "good"},
            "dedup": {"level": "HIGH", "similarity_score": 0.90}
        }
        assert is_usable_card(card) is False

    def test_is_usable_card_bad_quality(self):
        """Cards with bad quality should not be usable."""
        card = {
            "validation": {"quality_score": "incomplete"},
            "dedup": {"level": "LOW"}
        }
        assert is_usable_card(card) is False

    def test_is_usable_card_partial_quality(self):
        """Cards with partial quality should be usable."""
        card = {
            "validation": {"quality_score": "partial"},
            "dedup": {"level": "LOW"}
        }
        assert is_usable_card(card) is True

    def test_is_usable_card_no_dedup_info(self):
        """Cards without dedup info should be usable (assume LOW)."""
        card = {
            "validation": {"quality_score": "good"}
        }
        assert is_usable_card(card) is True


# =============================================================================
# Selector Tests
# =============================================================================

class TestAffinityScoring:
    """Tests for canonical affinity scoring."""

    def test_perfect_match(self):
        """All dimensions match should score 1.0."""
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        card_affinity = {
            "setting": ["apartment", "urban"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance", "confinement"]
        }
        score, details = compute_affinity_score(template_canonical, card_affinity)
        assert score == 1.0

    def test_no_match(self):
        """No matching dimensions should score 0.0."""
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        card_affinity = {
            "setting": ["rural"],
            "primary_fear": ["annihilation"],
            "antagonist": ["ghost"],
            "mechanism": ["possession"]
        }
        score, details = compute_affinity_score(template_canonical, card_affinity)
        assert score == 0.0

    def test_partial_match(self):
        """Partial matches should score proportionally."""
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        card_affinity = {
            "setting": ["apartment"],  # match
            "primary_fear": ["annihilation"],  # no match
            "antagonist": ["system"],  # match
            "mechanism": ["possession"]  # no match
        }
        score, details = compute_affinity_score(template_canonical, card_affinity)
        # 2 matches out of 4 dimensions (with weighting)
        assert 0.3 < score < 0.7

    def test_empty_affinity(self):
        """Empty card affinity should score 0.0."""
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation"
        }
        card_affinity = {}
        score, details = compute_affinity_score(template_canonical, card_affinity)
        assert score == 0.0


class TestResearchSelection:
    """Tests for research card selection."""

    def test_selection_excludes_high_duplicates(self):
        """Selection should exclude HIGH duplicate cards."""
        mock_cards = [
            {
                "card_id": "RC-001",
                "validation": {"quality_score": "good"},
                "dedup": {"level": "LOW"},
                "output": {
                    "canonical_affinity": {
                        "setting": ["apartment"],
                        "primary_fear": ["isolation"]
                    }
                }
            },
            {
                "card_id": "RC-002",
                "validation": {"quality_score": "good"},
                "dedup": {"level": "HIGH"},  # Should be excluded
                "output": {
                    "canonical_affinity": {
                        "setting": ["apartment"],
                        "primary_fear": ["isolation"]
                    }
                }
            }
        ]

        skeleton = {
            "template_id": "T-001",
            "canonical_core": {"setting": "apartment", "primary_fear": "isolation"}
        }

        with patch('src.infra.research_context.repository.load_all_research_cards') as mock_load:
            mock_load.return_value = mock_cards

            selection = select_research_for_template(skeleton)

            # Only RC-001 should be selected (RC-002 is HIGH)
            assert len(selection.cards) <= 1
            if selection.cards:
                assert selection.cards[0]["card_id"] == "RC-001"

    def test_selection_traceability(self):
        """Selection should provide card_ids for traceability."""
        selection = ResearchSelection(
            cards=[{"card_id": "RC-001"}, {"card_id": "RC-002"}],
            scores=[0.8, 0.6],
            match_details=[{}, {}],
            total_available=5,
            reason="test",
            card_ids=["RC-001", "RC-002"]
        )

        trace = selection.to_traceability_dict()
        assert trace["research_used"] == ["RC-001", "RC-002"]
        assert trace["selection_score"] == 0.8


# =============================================================================
# Formatter Tests
# =============================================================================

class TestFormatter:
    """Tests for research context formatting."""

    def test_build_research_context(self):
        """build_research_context should aggregate content from cards."""
        selection = ResearchSelection(
            cards=[
                {
                    "card_id": "RC-001",
                    "output": {
                        "title": "Test Card",
                        "key_concepts": ["concept1", "concept2"],
                        "horror_applications": ["app1"]
                    }
                }
            ],
            scores=[0.8],
            match_details=[{}],
            total_available=1,
            reason="test",
            card_ids=["RC-001"]
        )

        context = build_research_context(selection)

        assert context is not None
        assert "RC-001" in context["source_cards"]
        assert "concept1" in context["key_concepts"]
        assert "app1" in context["horror_applications"]

    def test_build_research_context_empty(self):
        """Empty selection should return None."""
        selection = ResearchSelection()
        context = build_research_context(selection)
        assert context is None

    def test_format_research_for_prompt(self):
        """format_research_for_prompt should produce formatted string."""
        context = {
            "key_concepts": ["concept1"],
            "horror_applications": ["app1"]
        }

        formatted = format_research_for_prompt(context)

        assert "Research Context" in formatted
        assert "concept1" in formatted
        assert "app1" in formatted

    def test_format_research_for_prompt_none(self):
        """None context should return empty string."""
        formatted = format_research_for_prompt(None)
        assert formatted == ""

    def test_format_research_for_metadata(self):
        """format_research_for_metadata should include traceability."""
        selection = ResearchSelection(
            cards=[{"card_id": "RC-001"}],
            scores=[0.8],
            match_details=[{}],
            total_available=5,
            reason="test selection",
            card_ids=["RC-001"]
        )

        metadata = format_research_for_metadata(selection, injection_mode="auto")

        assert metadata["research_used"] == ["RC-001"]
        assert metadata["research_injection_mode"] == "auto"
        assert "research_selection_reason" in metadata

    def test_format_research_for_metadata_empty(self):
        """Empty selection should still produce valid metadata."""
        selection = ResearchSelection(reason="no matches")
        metadata = format_research_for_metadata(selection, injection_mode="auto")

        assert metadata["research_used"] == []
        assert metadata["research_injection_mode"] == "auto"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_usable_cards_flow(self):
        """Test complete flow from loading to formatting."""
        # This is a simplified integration test
        # In real tests, we'd use fixtures with actual card data

        selection = ResearchSelection(
            cards=[
                {
                    "card_id": "RC-TEST",
                    "validation": {"quality_score": "good"},
                    "dedup": {"level": "LOW"},
                    "output": {
                        "title": "Test Research",
                        "key_concepts": ["test concept"],
                        "horror_applications": ["test app"],
                        "canonical_affinity": {
                            "setting": ["apartment"],
                            "primary_fear": ["isolation"]
                        }
                    }
                }
            ],
            scores=[0.9],
            match_details=[{}],
            total_available=1,
            reason="Selected 1/1 cards for test",
            card_ids=["RC-TEST"]
        )

        # Build context
        context = build_research_context(selection)
        assert context is not None
        assert "RC-TEST" in context["source_cards"]

        # Format for prompt
        prompt_section = format_research_for_prompt(context)
        assert "test concept" in prompt_section

        # Format for metadata
        metadata = format_research_for_metadata(selection)
        assert metadata["research_used"] == ["RC-TEST"]


# =============================================================================
# Issue #21: Reverse Matching Tests (Research → Templates)
# =============================================================================


class TestReverseAffinityScoring:
    """Tests for reverse canonical affinity scoring (Issue #21)."""

    def test_reverse_perfect_match(self):
        """All dimensions match should score 1.0 (reverse direction)."""
        card_affinity = {
            "setting": ["apartment", "urban"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance", "confinement"]
        }
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        score, details = compute_reverse_affinity_score(card_affinity, template_canonical)
        assert score == 1.0

    def test_reverse_no_match(self):
        """No matching dimensions should score 0.0."""
        card_affinity = {
            "setting": ["rural"],
            "primary_fear": ["annihilation"],
            "antagonist": ["ghost"],
            "mechanism": ["possession"]
        }
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        score, details = compute_reverse_affinity_score(card_affinity, template_canonical)
        assert score == 0.0

    def test_reverse_partial_match(self):
        """Partial matches should score proportionally."""
        card_affinity = {
            "setting": ["apartment"],  # match
            "primary_fear": ["annihilation"],  # no match
            "antagonist": ["system"],  # match
            "mechanism": ["possession"]  # no match
        }
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        score, details = compute_reverse_affinity_score(card_affinity, template_canonical)
        # 2 matches out of 4 dimensions (with weighting)
        assert 0.3 < score < 0.7

    def test_reverse_empty_affinity(self):
        """Empty card affinity should score 0.0."""
        card_affinity = {}
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation"
        }
        score, details = compute_reverse_affinity_score(card_affinity, template_canonical)
        assert score == 0.0

    def test_symmetry_with_forward_matching(self):
        """Reverse matching should produce same score as forward for same data."""
        template_canonical = {
            "setting": "apartment",
            "primary_fear": "isolation",
            "antagonist": "system",
            "mechanism": "surveillance"
        }
        card_affinity = {
            "setting": ["apartment", "urban"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance", "confinement"]
        }

        forward_score, _ = compute_affinity_score(template_canonical, card_affinity)
        reverse_score, _ = compute_reverse_affinity_score(card_affinity, template_canonical)

        assert forward_score == reverse_score


class TestTemplateSelection:
    """Tests for template selection from research card (Issue #21)."""

    def test_template_selection_basic(self):
        """select_templates_for_research should return matching templates."""
        mock_card = {
            "card_id": "RC-TEST",
            "output": {
                "canonical_affinity": {
                    "setting": ["apartment", "domestic_space"],
                    "primary_fear": ["isolation", "loss_of_autonomy"],
                    "antagonist": ["system"],
                    "mechanism": ["surveillance", "confinement"]
                }
            }
        }

        mock_templates = [
            {
                "template_id": "T-APT-001",
                "template_name": "Apartment Social Surveillance",
                "canonical_core": {
                    "setting": "apartment",
                    "primary_fear": "social_displacement",  # no match
                    "antagonist": "system",
                    "mechanism": "surveillance"
                }
            },
            {
                "template_id": "T-DOM-002",
                "template_name": "Smart Home Surveillance",
                "canonical_core": {
                    "setting": "domestic_space",
                    "primary_fear": "loss_of_autonomy",
                    "antagonist": "technology",  # no match
                    "mechanism": "surveillance"
                }
            },
            {
                "template_id": "T-NO-MATCH",
                "template_name": "No Match Template",
                "canonical_core": {
                    "setting": "rural",
                    "primary_fear": "annihilation",
                    "antagonist": "ghost",
                    "mechanism": "possession"
                }
            }
        ]

        # Use lower threshold for this test
        selection = select_templates_for_research(
            card=mock_card,
            templates=mock_templates,
            min_score=0.25  # Lower threshold for test
        )

        # Should have matches
        assert selection.has_matches
        assert len(selection.templates) >= 1
        # T-NO-MATCH should not be in results
        assert "T-NO-MATCH" not in selection.template_ids

    def test_template_selection_traceability(self):
        """TemplateSelection should provide template_ids for traceability."""
        selection = TemplateSelection(
            templates=[
                {"template_id": "T-001", "template_name": "Test 1"},
                {"template_id": "T-002", "template_name": "Test 2"}
            ],
            scores=[0.8, 0.6],
            match_details=[{}, {}],
            total_available=15,
            reason="test",
            template_ids=["T-001", "T-002"]
        )

        trace = selection.to_traceability_dict()
        assert trace["matching_templates"] == ["T-001", "T-002"]
        assert trace["best_match_score"] == 0.8

    def test_template_selection_empty_affinity(self):
        """Card with empty affinity should return no matches."""
        mock_card = {
            "card_id": "RC-EMPTY",
            "output": {
                "canonical_affinity": {}
            }
        }

        mock_templates = [
            {
                "template_id": "T-001",
                "template_name": "Test Template",
                "canonical_core": {
                    "setting": "apartment",
                    "primary_fear": "isolation",
                    "antagonist": "system",
                    "mechanism": "surveillance"
                }
            }
        ]

        selection = select_templates_for_research(
            card=mock_card,
            templates=mock_templates,
            min_score=0.5
        )

        assert not selection.has_matches
        assert len(selection.templates) == 0

    def test_template_selection_higher_threshold(self):
        """Higher min_score threshold should filter out partial matches."""
        mock_card = {
            "card_id": "RC-PARTIAL",
            "output": {
                "canonical_affinity": {
                    "setting": ["apartment"],  # 1 match
                    "primary_fear": ["annihilation"],  # different
                    "antagonist": ["ghost"],  # different
                    "mechanism": ["possession"]  # different
                }
            }
        }

        mock_templates = [
            {
                "template_id": "T-001",
                "template_name": "Test Template",
                "canonical_core": {
                    "setting": "apartment",
                    "primary_fear": "isolation",
                    "antagonist": "system",
                    "mechanism": "surveillance"
                }
            }
        ]

        # With high threshold (0.5), should not match (only 1/4 match ~= 0.2)
        selection = select_templates_for_research(
            card=mock_card,
            templates=mock_templates,
            min_score=0.5
        )

        assert not selection.has_matches

    def test_best_template_property(self):
        """best_template should return highest-scoring template."""
        selection = TemplateSelection(
            templates=[
                {"template_id": "T-001"},
                {"template_id": "T-002"}
            ],
            scores=[0.9, 0.7],
            match_details=[{}, {}],
            total_available=15,
            reason="test",
            template_ids=["T-001", "T-002"]
        )

        assert selection.best_template["template_id"] == "T-001"
        assert selection.best_score == 0.9
