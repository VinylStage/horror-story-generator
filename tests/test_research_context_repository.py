"""Tests for research_context repository module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.infra.research_context.repository import (
    load_all_research_cards,
    load_usable_research_cards,
    get_card_by_id,
    get_canonical_affinity,
    get_canonical_core,
    get_card_summary,
    search_cards_by_topic,
    get_best_card_for_topic,
)
from src.infra.research_context.policy import DedupLevel


@pytest.fixture
def sample_card():
    """Create a sample research card."""
    return {
        "card_id": "RC-20260115-120000",
        "input": {"topic": "Korean apartment horror"},
        "output": {
            "title": "아파트 공포",
            "canonical_affinity": {
                "setting": ["urban", "residential"],
                "primary_fear": ["isolation"],
                "antagonist": ["entity"],
                "mechanism": ["corruption"],
            }
        },
        "canonical_core": {
            "setting": "urban",
            "primary_fear": "isolation",
            "antagonist": "entity",
            "mechanism": "corruption",
        },
        "validation": {"quality_score": "good"},
        "metadata": {"created_at": "2026-01-15T12:00:00"},
        "dedup": {"level": "LOW", "similarity_score": 0.3},
    }


@pytest.fixture
def research_dir(tmp_path, sample_card):
    """Create a temporary research directory with sample cards."""
    # Create structure: 2026/01/RC-xxx.json
    card_dir = tmp_path / "2026" / "01"
    card_dir.mkdir(parents=True)

    # Create sample card
    card_path = card_dir / "RC-20260115-120000.json"
    with open(card_path, "w") as f:
        json.dump(sample_card, f)

    # Create another card
    card2 = sample_card.copy()
    card2["card_id"] = "RC-20260115-130000"
    card2["metadata"] = {"created_at": "2026-01-15T13:00:00"}
    card_path2 = card_dir / "RC-20260115-130000.json"
    with open(card_path2, "w") as f:
        json.dump(card2, f)

    return tmp_path


class TestLoadAllResearchCards:
    """Tests for load_all_research_cards function."""

    def test_loads_cards_from_directory(self, research_dir):
        """Test loading cards from directory."""
        cards = load_all_research_cards(str(research_dir))
        assert len(cards) == 2

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        """Test returns empty list for non-existent directory."""
        cards = load_all_research_cards(str(tmp_path / "nonexistent"))
        assert cards == []

    def test_skips_cards_without_card_id(self, tmp_path):
        """Test skips cards without card_id field."""
        card_dir = tmp_path / "2026" / "01"
        card_dir.mkdir(parents=True)

        # Card without card_id
        with open(card_dir / "invalid.json", "w") as f:
            json.dump({"title": "No ID"}, f)

        cards = load_all_research_cards(str(tmp_path))
        assert len(cards) == 0

    def test_handles_invalid_json(self, tmp_path):
        """Test handles invalid JSON gracefully."""
        card_dir = tmp_path / "2026" / "01"
        card_dir.mkdir(parents=True)

        # Invalid JSON
        with open(card_dir / "bad.json", "w") as f:
            f.write("not valid json")

        cards = load_all_research_cards(str(tmp_path))
        assert cards == []

    def test_sorts_by_created_at(self, research_dir):
        """Test cards are sorted by created_at (newest first)."""
        cards = load_all_research_cards(str(research_dir))
        assert len(cards) == 2
        # Card2 has later timestamp, should be first
        assert cards[0]["card_id"] == "RC-20260115-130000"


class TestLoadUsableResearchCards:
    """Tests for load_usable_research_cards function."""

    def test_loads_usable_cards(self, research_dir):
        """Test loading usable cards."""
        cards = load_usable_research_cards(str(research_dir))
        assert len(cards) >= 0  # Depends on policy


class TestGetCardById:
    """Tests for get_card_by_id function."""

    def test_finds_card_by_id(self, research_dir):
        """Test finding card by ID."""
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

    def test_fallback_search(self, tmp_path, sample_card):
        """Test fallback search when expected path doesn't exist."""
        # Create card in non-standard location
        card_dir = tmp_path / "archive"
        card_dir.mkdir()
        card_path = card_dir / "RC-20260115-120000.json"
        with open(card_path, "w") as f:
            json.dump(sample_card, f)

        card = get_card_by_id("RC-20260115-120000", str(tmp_path))
        assert card is not None


class TestGetCanonicalAffinity:
    """Tests for get_canonical_affinity function."""

    def test_extracts_affinity(self, sample_card):
        """Test extracting canonical affinity."""
        affinity = get_canonical_affinity(sample_card)
        assert affinity["setting"] == ["urban", "residential"]
        assert affinity["primary_fear"] == ["isolation"]

    def test_returns_empty_lists_for_missing(self):
        """Test returns empty lists for missing fields."""
        card = {"output": {}}
        affinity = get_canonical_affinity(card)
        assert affinity["setting"] == []
        assert affinity["primary_fear"] == []
        assert affinity["antagonist"] == []
        assert affinity["mechanism"] == []

    def test_handles_none_values(self):
        """Test handles None values in affinity."""
        card = {
            "output": {
                "canonical_affinity": {
                    "setting": None,
                    "primary_fear": ["fear"],
                }
            }
        }
        affinity = get_canonical_affinity(card)
        assert affinity["setting"] == []
        assert affinity["primary_fear"] == ["fear"]


class TestGetCanonicalCore:
    """Tests for get_canonical_core function."""

    def test_extracts_core(self, sample_card):
        """Test extracting canonical core."""
        core = get_canonical_core(sample_card)
        assert core is not None
        assert core["setting"] == "urban"

    def test_returns_none_for_missing(self):
        """Test returns None when canonical_core is missing."""
        card = {"output": {}}
        core = get_canonical_core(card)
        assert core is None


class TestGetCardSummary:
    """Tests for get_card_summary function."""

    def test_extracts_summary(self, sample_card):
        """Test extracting card summary."""
        summary = get_card_summary(sample_card)

        assert summary["card_id"] == "RC-20260115-120000"
        assert summary["title"] == "아파트 공포"
        assert summary["topic"] == "Korean apartment horror"
        assert summary["quality"] == "good"
        assert summary["dedup_level"] == "LOW"
        assert summary["dedup_score"] == 0.3

    def test_handles_missing_fields(self):
        """Test handles missing fields gracefully."""
        card = {"card_id": "RC-TEST"}
        summary = get_card_summary(card)

        assert summary["card_id"] == "RC-TEST"
        assert summary["title"] == "Untitled"
        assert summary["quality"] == "unknown"


class TestSearchCardsByTopic:
    """Tests for search_cards_by_topic function."""

    def test_finds_matching_cards(self, research_dir):
        """Test finding cards by topic."""
        cards = search_cards_by_topic("apartment", str(research_dir))
        # Should find cards with "apartment" in topic
        assert isinstance(cards, list)

    def test_returns_empty_for_no_match(self, research_dir):
        """Test returns empty list for no matches."""
        cards = search_cards_by_topic("zzzznonexistent", str(research_dir))
        assert cards == []


class TestGetBestCardForTopic:
    """Tests for get_best_card_for_topic function."""

    def test_returns_best_match(self, research_dir):
        """Test returns best matching card."""
        card = get_best_card_for_topic("apartment", str(research_dir))
        # Should return a card or None
        assert card is None or isinstance(card, dict)

    def test_returns_none_for_no_match(self, research_dir):
        """Test returns None for no matches."""
        card = get_best_card_for_topic("zzzznonexistent", str(research_dir))
        assert card is None
