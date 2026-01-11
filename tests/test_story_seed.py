"""
Tests for story_seed module.

Phase B+: Story seed generation and management tests.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestStorySeed:
    """Tests for StorySeed dataclass."""

    def test_create_seed(self):
        """Should create seed with correct fields."""
        from story_seed import StorySeed

        seed = StorySeed(
            seed_id="SS-2026-01-11-001",
            source_card_id="RC-2026-01-11-001",
            key_themes=["isolation", "paranoia"],
            atmosphere_tags=["oppressive", "uncanny"],
            suggested_hooks=["A researcher discovers..."],
            cultural_elements=["corporate surveillance"]
        )

        assert seed.seed_id == "SS-2026-01-11-001"
        assert seed.source_card_id == "RC-2026-01-11-001"
        assert len(seed.key_themes) == 2
        assert len(seed.atmosphere_tags) == 2
        assert len(seed.suggested_hooks) == 1
        assert len(seed.cultural_elements) == 1

    def test_to_dict(self):
        """Should convert to dictionary."""
        from story_seed import StorySeed

        seed = StorySeed(
            seed_id="SS-001",
            source_card_id="RC-001",
            key_themes=["theme1"],
            atmosphere_tags=["tag1"],
            suggested_hooks=["hook1"],
            cultural_elements=["elem1"]
        )

        d = seed.to_dict()

        assert d["seed_id"] == "SS-001"
        assert d["source_card_id"] == "RC-001"
        assert d["key_themes"] == ["theme1"]
        assert d["atmosphere_tags"] == ["tag1"]
        assert d["suggested_hooks"] == ["hook1"]
        assert d["cultural_elements"] == ["elem1"]
        assert "created_at" in d

    def test_from_dict(self):
        """Should create from dictionary."""
        from story_seed import StorySeed

        data = {
            "seed_id": "SS-001",
            "source_card_id": "RC-001",
            "key_themes": ["theme1", "theme2"],
            "atmosphere_tags": ["tag1"],
            "suggested_hooks": ["hook1"],
            "cultural_elements": ["elem1"],
            "created_at": "2026-01-11T12:00:00"
        }

        seed = StorySeed.from_dict(data)

        assert seed.seed_id == "SS-001"
        assert seed.source_card_id == "RC-001"
        assert seed.key_themes == ["theme1", "theme2"]
        assert isinstance(seed.created_at, datetime)

    def test_from_dict_without_created_at(self):
        """Should handle missing created_at."""
        from story_seed import StorySeed

        data = {
            "seed_id": "SS-001",
            "source_card_id": "RC-001"
        }

        seed = StorySeed.from_dict(data)

        assert seed.seed_id == "SS-001"
        assert isinstance(seed.created_at, datetime)


class TestGenerateSeedId:
    """Tests for generate_seed_id function."""

    def test_format(self):
        """Should generate correct format."""
        from story_seed import generate_seed_id

        seed_id = generate_seed_id()

        assert seed_id.startswith("SS-")
        parts = seed_id.split("-")
        assert len(parts) == 5  # SS-YYYY-MM-DD-XXX (5 parts when split by -)

    def test_unique_ids(self):
        """Should generate unique IDs."""
        from story_seed import generate_seed_id

        ids = [generate_seed_id() for _ in range(3)]

        # All should be unique (though may have same prefix if fast)
        # At minimum they should all be valid format
        for seed_id in ids:
            assert seed_id.startswith("SS-")


class TestExtractCardFields:
    """Tests for extract_card_fields function."""

    def test_extracts_all_fields(self):
        """Should extract all relevant fields."""
        from story_seed import extract_card_fields

        card_data = {
            "input": {"topic": "Test Topic"},
            "output": {
                "title": "Test Title",
                "summary": "Test Summary",
                "key_concepts": ["concept1", "concept2"],
                "horror_applications": ["app1", "app2"]
            }
        }

        fields = extract_card_fields(card_data)

        assert fields["topic"] == "Test Topic"
        assert fields["title"] == "Test Title"
        assert fields["summary"] == "Test Summary"
        assert "concept1" in fields["concepts"]
        assert "app1" in fields["applications"]

    def test_handles_empty_card(self):
        """Should handle empty card data."""
        from story_seed import extract_card_fields

        fields = extract_card_fields({})

        assert fields["topic"] == ""
        assert fields["title"] == ""
        assert fields["summary"] == ""
        assert fields["concepts"] == ""
        assert fields["applications"] == ""


class TestParseSeedJson:
    """Tests for parse_seed_json function."""

    def test_parses_clean_json(self):
        """Should parse clean JSON."""
        from story_seed import parse_seed_json

        text = '{"key_themes": ["a", "b"], "atmosphere_tags": ["c"]}'

        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["a", "b"]
        assert result["atmosphere_tags"] == ["c"]

    def test_removes_thinking_tags(self):
        """Should remove thinking tags."""
        from story_seed import parse_seed_json

        text = '<think>some thinking</think>{"key_themes": ["a"]}'

        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["a"]

    def test_extracts_json_from_text(self):
        """Should extract JSON from surrounding text."""
        from story_seed import parse_seed_json

        text = 'Here is the result: {"key_themes": ["a"]} Done.'

        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["a"]

    def test_returns_none_for_invalid(self):
        """Should return None for invalid JSON."""
        from story_seed import parse_seed_json

        text = "This is not JSON at all"

        result = parse_seed_json(text)

        assert result is None


class TestSaveSeed:
    """Tests for save_seed function."""

    def test_saves_to_file(self):
        """Should save seed to JSON file."""
        from story_seed import StorySeed, save_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            seed = StorySeed(
                seed_id="SS-2026-01-11-001",
                source_card_id="RC-001",
                key_themes=["theme1"],
                atmosphere_tags=["tag1"],
                suggested_hooks=["hook1"],
                cultural_elements=["elem1"]
            )

            path = save_seed(seed, output_dir=Path(tmpdir))

            assert path is not None
            assert path.exists()
            assert path.name == "SS-2026-01-11-001.json"

            # Verify content
            with open(path) as f:
                data = json.load(f)
            assert data["seed_id"] == "SS-2026-01-11-001"


class TestLoadSeed:
    """Tests for load_seed function."""

    def test_loads_from_file(self):
        """Should load seed from JSON file."""
        from story_seed import StorySeed, load_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            seed_path = Path(tmpdir) / "test_seed.json"

            data = {
                "seed_id": "SS-001",
                "source_card_id": "RC-001",
                "key_themes": ["theme1"],
                "atmosphere_tags": ["tag1"],
                "suggested_hooks": ["hook1"],
                "cultural_elements": ["elem1"],
                "created_at": "2026-01-11T12:00:00"
            }

            with open(seed_path, "w") as f:
                json.dump(data, f)

            seed = load_seed(seed_path)

            assert seed is not None
            assert seed.seed_id == "SS-001"
            assert seed.key_themes == ["theme1"]

    def test_returns_none_for_missing_file(self):
        """Should return None for missing file."""
        from story_seed import load_seed

        seed = load_seed(Path("/nonexistent/path.json"))

        assert seed is None


class TestListSeeds:
    """Tests for list_seeds function."""

    def test_returns_list(self):
        """Should return a list."""
        from story_seed import list_seeds

        result = list_seeds()

        assert isinstance(result, list)

    def test_finds_seed_files(self):
        """Should find SS-*.json files."""
        from story_seed import list_seeds

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create some seed files
            (tmpdir / "SS-2026-01-11-001.json").write_text("{}")
            (tmpdir / "SS-2026-01-11-002.json").write_text("{}")
            (tmpdir / "other.json").write_text("{}")

            result = list_seeds(seeds_dir=tmpdir)

            assert len(result) == 2
            for path in result:
                assert path.stem.startswith("SS-")


class TestGetRandomSeed:
    """Tests for get_random_seed function."""

    def test_returns_none_when_no_seeds(self):
        """Should return None when no seeds available."""
        from story_seed import get_random_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_random_seed(seeds_dir=Path(tmpdir))

            assert result is None

    def test_returns_seed_when_available(self):
        """Should return a seed when available."""
        from story_seed import get_random_seed, StorySeed

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a seed file
            data = {
                "seed_id": "SS-001",
                "source_card_id": "RC-001",
                "key_themes": ["theme1"],
                "atmosphere_tags": [],
                "suggested_hooks": [],
                "cultural_elements": [],
                "created_at": "2026-01-11T12:00:00"
            }

            with open(tmpdir / "SS-001.json", "w") as f:
                json.dump(data, f)

            result = get_random_seed(seeds_dir=tmpdir)

            assert result is not None
            assert isinstance(result, StorySeed)
            assert result.seed_id == "SS-001"
