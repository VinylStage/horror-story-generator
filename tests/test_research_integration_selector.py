"""Tests for research integration selector module."""

import pytest
from unittest.mock import patch

from src.research.integration.selector import (
    ResearchSelection,
    compute_affinity_score,
    DIMENSION_WEIGHTS,
    MIN_MATCH_SCORE,
    MAX_SELECTED_CARDS,
)


class TestResearchSelection:
    """Tests for ResearchSelection dataclass."""

    def test_has_matches_true(self):
        """Test has_matches returns True when cards exist."""
        selection = ResearchSelection(
            cards=[{"card_id": "RC-001"}],
            scores=[0.8],
            match_details=[{}],
            total_available=10,
            reason="Test"
        )
        assert selection.has_matches is True

    def test_has_matches_false(self):
        """Test has_matches returns False when no cards."""
        selection = ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=10,
            reason="No matches"
        )
        assert selection.has_matches is False

    def test_best_card_exists(self):
        """Test best_card returns first card."""
        selection = ResearchSelection(
            cards=[{"card_id": "RC-001"}, {"card_id": "RC-002"}],
            scores=[0.8, 0.6],
            match_details=[{}, {}],
            total_available=10,
            reason="Test"
        )
        assert selection.best_card["card_id"] == "RC-001"

    def test_best_card_none(self):
        """Test best_card returns None when empty."""
        selection = ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=0,
            reason="Empty"
        )
        assert selection.best_card is None

    def test_best_score_exists(self):
        """Test best_score returns first score."""
        selection = ResearchSelection(
            cards=[{"card_id": "RC-001"}],
            scores=[0.85],
            match_details=[{}],
            total_available=10,
            reason="Test"
        )
        assert selection.best_score == 0.85

    def test_best_score_zero(self):
        """Test best_score returns 0.0 when empty."""
        selection = ResearchSelection(
            cards=[],
            scores=[],
            match_details=[],
            total_available=0,
            reason="Empty"
        )
        assert selection.best_score == 0.0


class TestComputeAffinityScore:
    """Tests for compute_affinity_score function."""

    def test_full_match(self):
        """Test full match returns high score."""
        template = {
            "setting": "urban",
            "primary_fear": "isolation",
            "antagonist": "entity",
            "mechanism": "corruption",
        }
        card_affinity = {
            "setting": ["urban", "residential"],
            "primary_fear": ["isolation", "paranoia"],
            "antagonist": ["entity", "human"],
            "mechanism": ["corruption", "erosion"],
        }

        score, details = compute_affinity_score(template, card_affinity)

        assert score == 1.0
        assert details["setting"]["match"] is True
        assert details["primary_fear"]["match"] is True
        assert details["antagonist"]["match"] is True
        assert details["mechanism"]["match"] is True

    def test_no_match(self):
        """Test no match returns zero score."""
        template = {
            "setting": "rural",
            "primary_fear": "body_horror",
            "antagonist": "monster",
            "mechanism": "transformation",
        }
        card_affinity = {
            "setting": ["urban"],
            "primary_fear": ["isolation"],
            "antagonist": ["entity"],
            "mechanism": ["corruption"],
        }

        score, details = compute_affinity_score(template, card_affinity)

        assert score == 0.0
        assert details["setting"]["match"] is False

    def test_partial_match(self):
        """Test partial match returns intermediate score."""
        template = {
            "setting": "urban",
            "primary_fear": "isolation",
            "antagonist": "monster",  # No match
            "mechanism": "transformation",  # No match
        }
        card_affinity = {
            "setting": ["urban"],
            "primary_fear": ["isolation"],
            "antagonist": ["entity"],
            "mechanism": ["corruption"],
        }

        score, details = compute_affinity_score(template, card_affinity)

        assert 0.0 < score < 1.0
        assert details["setting"]["match"] is True
        assert details["primary_fear"]["match"] is True
        assert details["antagonist"]["match"] is False
        assert details["mechanism"]["match"] is False

    def test_empty_template(self):
        """Test empty template returns zero score."""
        template = {}
        card_affinity = {
            "setting": ["urban"],
            "primary_fear": ["isolation"],
        }

        score, details = compute_affinity_score(template, card_affinity)
        # Empty template values don't match
        assert score == 0.0

    def test_empty_card_affinity(self):
        """Test empty card affinity returns zero score."""
        template = {
            "setting": "urban",
            "primary_fear": "isolation",
        }
        card_affinity = {}

        score, details = compute_affinity_score(template, card_affinity)
        assert score == 0.0


class TestConstants:
    """Tests for module constants."""

    def test_dimension_weights_exist(self):
        """Test all dimensions have weights."""
        assert "setting" in DIMENSION_WEIGHTS
        assert "primary_fear" in DIMENSION_WEIGHTS
        assert "antagonist" in DIMENSION_WEIGHTS
        assert "mechanism" in DIMENSION_WEIGHTS

    def test_primary_fear_has_highest_weight(self):
        """Test primary_fear has highest weight."""
        assert DIMENSION_WEIGHTS["primary_fear"] >= DIMENSION_WEIGHTS["setting"]

    def test_min_match_score_valid(self):
        """Test min match score is valid."""
        assert 0.0 <= MIN_MATCH_SCORE <= 1.0

    def test_max_selected_cards_reasonable(self):
        """Test max selected cards is reasonable."""
        assert MAX_SELECTED_CARDS > 0
        assert MAX_SELECTED_CARDS <= 10
