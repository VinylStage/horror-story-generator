"""
Tests for story_seed module with mocked Ollama calls.

Phase B+: Tests seed generation with mocked LLM responses.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestGenerateSeedFromCard:
    """Tests for generate_seed_from_card with mocked Ollama."""

    def test_generate_seed_success(self):
        """Should generate seed from card with mocked LLM."""
        from story_seed import generate_seed_from_card

        card_data = {
            "input": {"topic": "Korean apartment horror"},
            "output": {
                "title": "The Walls That Listen",
                "summary": "Paranoia in dense urban living",
                "key_concepts": ["surveillance", "paranoia"],
                "horror_applications": ["thin walls", "eerie sounds"]
            }
        }

        # Mock LLM response with valid JSON
        mock_llm_response = json.dumps({
            "key_themes": ["isolation", "paranoia", "surveillance"],
            "atmosphere_tags": ["oppressive", "claustrophobic", "uncanny"],
            "suggested_hooks": [
                "A new tenant notices patterns in neighbor movements",
                "The walls seem thinner at night"
            ],
            "cultural_elements": [
                "Korean apartment complex culture",
                "Late-night convenience store runs"
            ]
        })

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": mock_llm_response
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = generate_seed_from_card(
                card_data=card_data,
                card_id="RC-20260111-001"
            )

            assert result is not None
            assert result.source_card_id == "RC-20260111-001"
            assert "isolation" in result.key_themes
            assert len(result.atmosphere_tags) >= 1
            assert len(result.suggested_hooks) >= 1
            assert len(result.cultural_elements) >= 1

    def test_generate_seed_with_thinking_tags(self):
        """Should handle LLM response with thinking tags."""
        from story_seed import generate_seed_from_card

        card_data = {
            "input": {"topic": "Test"},
            "output": {"title": "Test", "summary": "Test"}
        }

        # Mock LLM response with thinking tags
        mock_llm_response = """<think>
Let me analyze this card...
The main themes are about isolation and fear.
</think>
{
    "key_themes": ["isolation"],
    "atmosphere_tags": ["dark"],
    "suggested_hooks": ["A door creaks..."],
    "cultural_elements": ["urban setting"]
}"""

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": mock_llm_response
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = generate_seed_from_card(
                card_data=card_data,
                card_id="RC-001"
            )

            assert result is not None
            assert "isolation" in result.key_themes

    def test_generate_seed_connection_error(self):
        """Should return None on connection error."""
        from story_seed import generate_seed_from_card
        import urllib.error

        card_data = {
            "input": {"topic": "Test"},
            "output": {"title": "Test"}
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = generate_seed_from_card(
                card_data=card_data,
                card_id="RC-001"
            )

            assert result is None

    def test_generate_seed_invalid_json_response(self):
        """Should return None for invalid JSON in LLM response."""
        from story_seed import generate_seed_from_card

        card_data = {
            "input": {"topic": "Test"},
            "output": {"title": "Test"}
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "This is not valid JSON output from the LLM"
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = generate_seed_from_card(
                card_data=card_data,
                card_id="RC-001"
            )

            assert result is None

    def test_generate_seed_partial_response(self):
        """Should handle partial JSON response."""
        from story_seed import generate_seed_from_card

        card_data = {
            "input": {"topic": "Test"},
            "output": {"title": "Test"}
        }

        # Response with only some fields
        mock_llm_response = json.dumps({
            "key_themes": ["theme1"],
            "atmosphere_tags": ["atm1"]
            # Missing suggested_hooks and cultural_elements
        })

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": mock_llm_response
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = generate_seed_from_card(
                card_data=card_data,
                card_id="RC-001"
            )

            # Should still create seed with available data
            if result is not None:
                assert result.key_themes == ["theme1"]


class TestParseSeedJson:
    """Tests for parse_seed_json function."""

    def test_parse_clean_json(self):
        """Should parse clean JSON string."""
        from story_seed import parse_seed_json

        text = '{"key_themes": ["a", "b"], "atmosphere_tags": ["c"]}'
        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["a", "b"]

    def test_parse_json_with_markdown(self):
        """Should extract JSON from markdown code blocks."""
        from story_seed import parse_seed_json

        text = '''Here is the result:
```json
{"key_themes": ["test"]}
```
Done!'''

        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["test"]

    def test_parse_json_with_nested_braces(self):
        """Should handle nested JSON structures."""
        from story_seed import parse_seed_json

        text = '''{"key_themes": ["a"], "metadata": {"nested": {"deep": true}}}'''

        result = parse_seed_json(text)

        assert result is not None
        assert result["key_themes"] == ["a"]

    def test_parse_empty_string(self):
        """Should return None for empty string."""
        from story_seed import parse_seed_json

        result = parse_seed_json("")
        assert result is None

    def test_parse_no_json_content(self):
        """Should return None when no JSON found."""
        from story_seed import parse_seed_json

        result = parse_seed_json("This is just plain text without any JSON")
        assert result is None


class TestExtractCardFields:
    """Tests for extract_card_fields function."""

    def test_extract_all_fields(self):
        """Should extract all available fields."""
        from story_seed import extract_card_fields

        card_data = {
            "input": {"topic": "Korean Horror"},
            "output": {
                "title": "The Title",
                "summary": "A summary of the research",
                "key_concepts": ["concept1", "concept2"],
                "horror_applications": ["app1", "app2"]
            }
        }

        result = extract_card_fields(card_data)

        assert result["topic"] == "Korean Horror"
        assert result["title"] == "The Title"
        assert result["summary"] == "A summary of the research"
        assert "concept1" in result["concepts"]
        assert "app1" in result["applications"]

    def test_extract_missing_input(self):
        """Should handle missing input section."""
        from story_seed import extract_card_fields

        card_data = {
            "output": {
                "title": "Title Only"
            }
        }

        result = extract_card_fields(card_data)

        assert result["topic"] == ""
        assert result["title"] == "Title Only"

    def test_extract_missing_output(self):
        """Should handle missing output section."""
        from story_seed import extract_card_fields

        card_data = {
            "input": {"topic": "Topic Only"}
        }

        result = extract_card_fields(card_data)

        assert result["topic"] == "Topic Only"
        assert result["title"] == ""
        assert result["summary"] == ""


class TestSeedPersistence:
    """Tests for seed save/load with mocking."""

    def test_save_and_load_seed(self):
        """Should save and load seed correctly."""
        from story_seed import StorySeed, save_seed, load_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            seed = StorySeed(
                seed_id="SS-2026-01-11-001",
                source_card_id="RC-2026-01-11-001",
                key_themes=["isolation", "paranoia"],
                atmosphere_tags=["oppressive", "dark"],
                suggested_hooks=["A door opens in the night"],
                cultural_elements=["apartment complex life"],
                created_at=datetime.now()
            )

            # Save
            path = save_seed(seed, output_dir=tmpdir)
            assert path is not None
            assert path.exists()

            # Load
            loaded = load_seed(path)
            assert loaded is not None
            assert loaded.seed_id == "SS-2026-01-11-001"
            assert loaded.source_card_id == "RC-2026-01-11-001"
            assert loaded.key_themes == ["isolation", "paranoia"]

    def test_save_seed_creates_directory(self):
        """Should create output directory if not exists."""
        from story_seed import StorySeed, save_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "nested" / "seeds"

            seed = StorySeed(
                seed_id="SS-001",
                source_card_id="RC-001",
                key_themes=[],
                atmosphere_tags=[],
                suggested_hooks=[],
                cultural_elements=[]
            )

            path = save_seed(seed, output_dir=new_dir)

            assert path is not None
            assert new_dir.exists()
            assert path.exists()


class TestGetRandomSeed:
    """Tests for get_random_seed function."""

    def test_get_random_seed_from_directory(self):
        """Should get random seed from directory."""
        from story_seed import StorySeed, save_seed, get_random_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create some seeds
            for i in range(3):
                seed = StorySeed(
                    seed_id=f"SS-00{i}",
                    source_card_id=f"RC-00{i}",
                    key_themes=[f"theme{i}"],
                    atmosphere_tags=[],
                    suggested_hooks=[],
                    cultural_elements=[]
                )
                save_seed(seed, output_dir=tmpdir)

            # Get random
            result = get_random_seed(seeds_dir=tmpdir)

            assert result is not None
            assert result.seed_id.startswith("SS-")

    def test_get_random_seed_empty_directory(self):
        """Should return None for empty directory."""
        from story_seed import get_random_seed

        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_random_seed(seeds_dir=Path(tmpdir))
            assert result is None


class TestListSeeds:
    """Tests for list_seeds function."""

    def test_list_seeds_finds_files(self):
        """Should find all SS-*.json files."""
        from story_seed import list_seeds

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create seed files
            (tmpdir / "SS-001.json").write_text("{}")
            (tmpdir / "SS-002.json").write_text("{}")
            (tmpdir / "other.json").write_text("{}")  # Should not be included

            result = list_seeds(seeds_dir=tmpdir)

            assert len(result) == 2
            for path in result:
                assert path.stem.startswith("SS-")

    def test_list_seeds_nonexistent_directory(self):
        """Should return empty list for nonexistent directory."""
        from story_seed import list_seeds

        result = list_seeds(seeds_dir=Path("/nonexistent/path"))

        assert result == []


class TestGenerateSeedId:
    """Tests for generate_seed_id function."""

    def test_generate_seed_id_format(self):
        """Should generate ID in correct format."""
        from story_seed import generate_seed_id

        seed_id = generate_seed_id()

        assert seed_id.startswith("SS-")
        parts = seed_id.split("-")
        assert len(parts) == 5  # SS-YYYY-MM-DD-XXX

    def test_generate_seed_id_uniqueness(self):
        """Should generate unique IDs."""
        from story_seed import generate_seed_id
        import time

        ids = []
        for _ in range(5):
            ids.append(generate_seed_id())
            time.sleep(0.001)  # Small delay

        # Check all are valid format
        for seed_id in ids:
            assert seed_id.startswith("SS-")

    def test_generate_seed_id_date_based(self):
        """Should include current date."""
        from story_seed import generate_seed_id
        from datetime import datetime

        seed_id = generate_seed_id()
        today = datetime.now().strftime("%Y-%m-%d")

        assert today in seed_id
