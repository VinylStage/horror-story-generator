"""Tests for research integration loader module."""

import json
import pytest
from pathlib import Path

from src.research.integration.loader import (
    load_research_cards,
    get_card_by_id,
    get_canonical_affinity,
    get_card_summary,
    ACCEPTABLE_QUALITY_SCORES,
)


@pytest.fixture
def sample_card():
    """Create a sample research card."""
    return {
        "card_id": "RC-20260115-120000",
        "input": {"topic": "Test topic"},
        "output": {
            "title": "Test Title",
            "canonical_affinity": {
                "setting": ["urban"],
                "primary_fear": ["isolation"],
                "antagonist": ["entity"],
                "mechanism": ["corruption"],
            }
        },
        "validation": {"quality_score": "good"},
        "metadata": {"created_at": "2026-01-15T12:00:00"},
    }


@pytest.fixture
def research_dir(tmp_path, sample_card):
    """Create a temporary research directory with sample cards."""
    card_dir = tmp_path / "2026" / "01"
    card_dir.mkdir(parents=True)

    # Create good quality card
    card_path = card_dir / "RC-20260115-120000.json"
    with open(card_path, "w") as f:
        json.dump(sample_card, f)

    # Create partial quality card
    partial_card = sample_card.copy()
    partial_card["card_id"] = "RC-20260115-130000"
    partial_card["validation"] = {"quality_score": "partial"}
    partial_card["metadata"] = {"created_at": "2026-01-15T13:00:00"}
    with open(card_dir / "RC-20260115-130000.json", "w") as f:
        json.dump(partial_card, f)

    # Create incomplete quality card
    incomplete_card = sample_card.copy()
    incomplete_card["card_id"] = "RC-20260115-140000"
    incomplete_card["validation"] = {"quality_score": "incomplete"}
    incomplete_card["metadata"] = {"created_at": "2026-01-15T14:00:00"}
    with open(card_dir / "RC-20260115-140000.json", "w") as f:
        json.dump(incomplete_card, f)

    return tmp_path


class TestLoadResearchCards:
    """Tests for load_research_cards function."""

    def test_loads_cards_from_directory(self, research_dir):
        """Test loading cards from directory."""
        cards = load_research_cards(str(research_dir), quality_filter=False)
        assert len(cards) == 3

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        """Test returns empty list for non-existent directory."""
        cards = load_research_cards(str(tmp_path / "nonexistent"))
        assert cards == []

    def test_filters_by_quality_partial(self, research_dir):
        """Test filtering by partial quality."""
        cards = load_research_cards(str(research_dir), quality_filter=True, min_quality="partial")
        # Should include good and partial, exclude incomplete
        assert len(cards) == 2
        qualities = [c.get("validation", {}).get("quality_score") for c in cards]
        assert "incomplete" not in qualities

    def test_filters_by_quality_good(self, research_dir):
        """Test filtering by good quality only."""
        cards = load_research_cards(str(research_dir), quality_filter=True, min_quality="good")
        # Should only include good quality
        assert len(cards) == 1
        assert cards[0]["validation"]["quality_score"] == "good"

    def test_skips_cards_without_card_id(self, tmp_path):
        """Test skips cards without card_id."""
        card_dir = tmp_path / "2026" / "01"
        card_dir.mkdir(parents=True)

        with open(card_dir / "invalid.json", "w") as f:
            json.dump({"title": "No ID"}, f)

        cards = load_research_cards(str(tmp_path))
        assert len(cards) == 0

    def test_handles_invalid_json(self, tmp_path):
        """Test handles invalid JSON gracefully."""
        card_dir = tmp_path / "2026" / "01"
        card_dir.mkdir(parents=True)

        with open(card_dir / "bad.json", "w") as f:
            f.write("not valid json")

        cards = load_research_cards(str(tmp_path))
        assert cards == []

    def test_sorts_by_created_at(self, research_dir):
        """Test cards are sorted by created_at (newest first)."""
        cards = load_research_cards(str(research_dir), quality_filter=False)
        timestamps = [c.get("metadata", {}).get("created_at", "") for c in cards]
        assert timestamps == sorted(timestamps, reverse=True)


class TestGetCardById:
    """Tests for get_card_by_id function."""

    def test_finds_card_by_id(self, research_dir):
        """Test finding card by ID using expected path."""
        card = get_card_by_id("RC-20260115-120000", str(research_dir))
        assert card is not None
        assert card["card_id"] == "RC-20260115-120000"

    def test_returns_none_for_nonexistent(self, research_dir):
        """Test returns None for non-existent card."""
        card = get_card_by_id("RC-99999999-999999", str(research_dir))
        assert card is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path):
        """Test returns None when directory doesn't exist."""
        card = get_card_by_id("RC-20260115-120000", str(tmp_path / "nonexistent"))
        assert card is None

    def test_fallback_search_finds_card(self, tmp_path, sample_card):
        """Test fallback search when expected path doesn't work."""
        # Create card with malformed ID (short date)
        card_dir = tmp_path / "archive"
        card_dir.mkdir()

        # Use a card ID that won't match expected path structure
        sample_card["card_id"] = "RC-BAD-FORMAT"
        card_path = card_dir / "RC-BAD-FORMAT.json"
        with open(card_path, "w") as f:
            json.dump(sample_card, f)

        card = get_card_by_id("RC-BAD-FORMAT", str(tmp_path))
        assert card is not None


class TestGetCanonicalAffinity:
    """Tests for get_canonical_affinity function."""

    def test_extracts_affinity(self, sample_card):
        """Test extracting canonical affinity."""
        affinity = get_canonical_affinity(sample_card)
        assert affinity["setting"] == ["urban"]
        assert affinity["primary_fear"] == ["isolation"]
        assert affinity["antagonist"] == ["entity"]
        assert affinity["mechanism"] == ["corruption"]

    def test_returns_empty_lists_for_missing(self):
        """Test returns empty lists for missing fields."""
        card = {"output": {}}
        affinity = get_canonical_affinity(card)
        assert affinity["setting"] == []
        assert affinity["primary_fear"] == []

    def test_handles_none_values(self):
        """Test handles None values in affinity."""
        card = {
            "output": {
                "canonical_affinity": {
                    "setting": None,
                }
            }
        }
        affinity = get_canonical_affinity(card)
        assert affinity["setting"] == []


class TestGetCardSummary:
    """Tests for get_card_summary function."""

    def test_extracts_summary(self, sample_card):
        """Test extracting card summary."""
        summary = get_card_summary(sample_card)

        assert summary["card_id"] == "RC-20260115-120000"
        assert summary["title"] == "Test Title"
        assert summary["topic"] == "Test topic"
        assert summary["quality"] == "good"
        assert summary["created_at"] == "2026-01-15T12:00:00"
        assert "canonical_affinity" in summary

    def test_handles_missing_fields(self):
        """Test handles missing fields gracefully."""
        card = {"card_id": "RC-TEST"}
        summary = get_card_summary(card)

        assert summary["card_id"] == "RC-TEST"
        assert summary["title"] == "Untitled"
        assert summary["quality"] == "unknown"


class TestAcceptableQualityScores:
    """Tests for quality score constants."""

    def test_acceptable_quality_scores(self):
        """Test acceptable quality scores constant."""
        assert "good" in ACCEPTABLE_QUALITY_SCORES
        assert "partial" in ACCEPTABLE_QUALITY_SCORES
        assert "incomplete" not in ACCEPTABLE_QUALITY_SCORES
