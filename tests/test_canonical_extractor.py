"""
Tests for story canonical key extractor.

Issue #19: Generate Canonical Key for story outputs.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.story.canonical_extractor import (
    extract_canonical_from_story,
    compare_canonical_cores,
    _parse_extraction_response,
    _validate_affinity_structure,
    EXTRACTION_SYSTEM_PROMPT,
)


class TestParseExtractionResponse:
    """Tests for parsing LLM extraction responses."""

    def test_parse_valid_json(self):
        """Valid JSON response should be parsed correctly."""
        response = json.dumps({
            "canonical_affinity": {
                "setting": ["apartment"],
                "primary_fear": ["isolation"],
                "antagonist": ["system"],
                "mechanism": ["surveillance"],
                "twist": ["inevitability"]
            },
            "analysis_notes": "Test analysis"
        })

        result = _parse_extraction_response(response)

        assert result is not None
        assert result["canonical_affinity"]["setting"] == ["apartment"]
        assert result["canonical_core"]["setting_archetype"] == "apartment"
        assert result["canonical_core"]["primary_fear"] == "isolation"
        assert result["analysis_notes"] == "Test analysis"

    def test_parse_json_in_markdown_code_block(self):
        """JSON wrapped in markdown code block should be extracted."""
        response = """```json
{
    "canonical_affinity": {
        "setting": ["hospital"],
        "primary_fear": ["annihilation"],
        "antagonist": ["body"],
        "mechanism": ["infection"]
    },
    "analysis_notes": "Hospital horror"
}
```"""

        result = _parse_extraction_response(response)

        assert result is not None
        assert result["canonical_affinity"]["setting"] == ["hospital"]
        assert result["canonical_core"]["setting_archetype"] == "hospital"

    def test_parse_json_in_plain_code_block(self):
        """JSON wrapped in plain code block should be extracted."""
        response = """```
{
    "canonical_affinity": {
        "setting": ["rural"],
        "primary_fear": ["isolation"],
        "antagonist": ["unknown"],
        "mechanism": ["erosion"]
    }
}
```"""

        result = _parse_extraction_response(response)

        assert result is not None
        assert result["canonical_core"]["setting_archetype"] == "rural"

    def test_parse_invalid_json(self):
        """Invalid JSON should return None."""
        response = "This is not JSON at all"

        result = _parse_extraction_response(response)

        assert result is None

    def test_parse_missing_canonical_affinity(self):
        """Response without canonical_affinity should return None."""
        response = json.dumps({
            "analysis_notes": "No affinity provided"
        })

        result = _parse_extraction_response(response)

        assert result is None

    def test_parse_multiple_values_collapsed(self):
        """Multiple values should be collapsed to single canonical_core."""
        response = json.dumps({
            "canonical_affinity": {
                "setting": ["apartment", "hospital"],
                "primary_fear": ["isolation", "annihilation"],
                "antagonist": ["system", "technology"],
                "mechanism": ["surveillance", "confinement"]
            }
        })

        result = _parse_extraction_response(response)

        assert result is not None
        # Should use first valid for most, priority for primary_fear
        assert result["canonical_core"]["setting_archetype"] == "apartment"
        assert result["canonical_core"]["primary_fear"] == "annihilation"  # higher priority


class TestValidateAffinityStructure:
    """Tests for affinity structure validation."""

    def test_valid_structure(self):
        """Valid structure should pass."""
        affinity = {
            "setting": ["apartment"],
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        assert _validate_affinity_structure(affinity) is True

    def test_missing_required_key(self):
        """Missing required key should fail."""
        affinity = {
            "setting": ["apartment"],
            "primary_fear": ["isolation"],
            # missing antagonist
            "mechanism": ["surveillance"]
        }

        assert _validate_affinity_structure(affinity) is False

    def test_non_list_value(self):
        """Non-list value should fail."""
        affinity = {
            "setting": "apartment",  # should be list
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        assert _validate_affinity_structure(affinity) is False

    def test_empty_list_value(self):
        """Empty list should fail."""
        affinity = {
            "setting": [],  # empty
            "primary_fear": ["isolation"],
            "antagonist": ["system"],
            "mechanism": ["surveillance"]
        }

        assert _validate_affinity_structure(affinity) is False


class TestCompareCanonicalCores:
    """Tests for comparing template and story canonical cores."""

    def test_perfect_match(self):
        """Identical cores should have 100% match."""
        template_core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }
        story_core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        result = compare_canonical_cores(template_core, story_core)

        assert result["match_score"] == 1.0
        assert result["match_count"] == 5
        assert len(result["matches"]) == 5
        assert len(result["divergences"]) == 0

    def test_partial_match(self):
        """Partial matches should be calculated correctly."""
        template_core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }
        story_core = {
            "setting_archetype": "apartment",
            "primary_fear": "annihilation",  # different
            "antagonist_archetype": "system",
            "threat_mechanism": "confinement",  # different
            "twist_family": "inevitability"
        }

        result = compare_canonical_cores(template_core, story_core)

        assert result["match_score"] == 0.6  # 3/5
        assert result["match_count"] == 3
        assert len(result["divergences"]) == 2

        # Check divergence details
        divergent_dims = [d["dimension"] for d in result["divergences"]]
        assert "primary_fear" in divergent_dims
        assert "threat_mechanism" in divergent_dims

    def test_no_match(self):
        """Completely different cores should have 0% match."""
        template_core = {
            "setting_archetype": "apartment",
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }
        story_core = {
            "setting_archetype": "hospital",
            "primary_fear": "annihilation",
            "antagonist_archetype": "body",
            "threat_mechanism": "infection",
            "twist_family": "revelation"
        }

        result = compare_canonical_cores(template_core, story_core)

        assert result["match_score"] == 0.0
        assert result["match_count"] == 0
        assert len(result["divergences"]) == 5

    def test_abbreviated_key_names(self):
        """Should handle abbreviated key names (setting vs setting_archetype)."""
        template_core = {
            "setting": "apartment",  # abbreviated
            "primary_fear": "isolation",
            "antagonist": "system",  # abbreviated
            "mechanism": "surveillance",  # abbreviated
            "twist": "inevitability"  # abbreviated
        }
        story_core = {
            "setting_archetype": "apartment",  # full name
            "primary_fear": "isolation",
            "antagonist_archetype": "system",
            "threat_mechanism": "surveillance",
            "twist_family": "inevitability"
        }

        result = compare_canonical_cores(template_core, story_core)

        # Should match despite different key naming
        assert result["match_score"] == 1.0


class TestExtractCanonicalFromStory:
    """Tests for the main extraction function."""

    @patch("src.story.canonical_extractor.ENABLE_STORY_CK_EXTRACTION", False)
    def test_extraction_disabled(self):
        """Should return None when extraction is disabled."""
        result = extract_canonical_from_story(
            story_text="Some horror story",
            config={"api_key": "test", "model": "test"}
        )

        assert result is None

    @patch("src.story.canonical_extractor.ENABLE_STORY_CK_EXTRACTION", True)
    @patch("src.story.api_client.call_claude_api")
    def test_extraction_success(self, mock_api):
        """Successful extraction should return canonical data."""
        mock_api.return_value = {
            "story_text": json.dumps({
                "canonical_affinity": {
                    "setting": ["apartment"],
                    "primary_fear": ["social_displacement"],
                    "antagonist": ["collective"],
                    "mechanism": ["surveillance"],
                    "twist": ["inevitability"]
                },
                "analysis_notes": "Social horror in apartment setting"
            }),
            "usage": {}
        }

        result = extract_canonical_from_story(
            story_text="A story about neighbors watching...",
            config={"api_key": "test", "model": "claude-test"}
        )

        assert result is not None
        assert result["canonical_core"]["setting_archetype"] == "apartment"
        assert result["canonical_core"]["primary_fear"] == "social_displacement"
        assert result["extraction_model"] == "claude-test"

    @patch("src.story.canonical_extractor.ENABLE_STORY_CK_EXTRACTION", True)
    @patch("src.story.api_client.call_claude_api")
    def test_extraction_api_failure(self, mock_api):
        """API failure should return None gracefully."""
        mock_api.side_effect = Exception("API Error")

        result = extract_canonical_from_story(
            story_text="Some story",
            config={"api_key": "test", "model": "test"}
        )

        assert result is None

    @patch("src.story.canonical_extractor.ENABLE_STORY_CK_EXTRACTION", True)
    @patch("src.story.api_client.call_claude_api")
    def test_story_truncation(self, mock_api):
        """Long stories should be truncated for extraction."""
        mock_api.return_value = {
            "story_text": json.dumps({
                "canonical_affinity": {
                    "setting": ["apartment"],
                    "primary_fear": ["isolation"],
                    "antagonist": ["system"],
                    "mechanism": ["surveillance"]
                }
            }),
            "usage": {}
        }

        # Create a very long story
        long_story = "A" * 10000

        result = extract_canonical_from_story(
            story_text=long_story,
            config={"api_key": "test", "model": "test"}
        )

        assert result is not None
        assert result["story_truncated"] is True

    @patch("src.story.canonical_extractor.ENABLE_STORY_CK_EXTRACTION", True)
    @patch("src.story.api_client.call_llm_api")
    def test_ollama_model_spec(self, mock_llm_api):
        """Should use Ollama API when model_spec starts with ollama:"""
        mock_llm_api.return_value = {
            "story_text": json.dumps({
                "canonical_affinity": {
                    "setting": ["digital"],
                    "primary_fear": ["identity_erasure"],
                    "antagonist": ["technology"],
                    "mechanism": ["impersonation"]
                }
            }),
            "usage": {}
        }

        result = extract_canonical_from_story(
            story_text="A digital horror story",
            config={"api_key": "test", "model": "test"},
            model_spec="ollama:qwen3:30b"
        )

        assert result is not None
        mock_llm_api.assert_called_once()
        assert result["extraction_model"] == "ollama:qwen3:30b"


class TestPromptContent:
    """Tests for extraction prompt content."""

    def test_system_prompt_has_all_dimensions(self):
        """System prompt should mention all canonical dimensions."""
        assert "setting" in EXTRACTION_SYSTEM_PROMPT
        assert "primary_fear" in EXTRACTION_SYSTEM_PROMPT
        assert "antagonist" in EXTRACTION_SYSTEM_PROMPT
        assert "mechanism" in EXTRACTION_SYSTEM_PROMPT
        assert "twist" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_has_valid_values(self):
        """System prompt should list valid enum values."""
        # Settings
        assert "apartment" in EXTRACTION_SYSTEM_PROMPT
        assert "hospital" in EXTRACTION_SYSTEM_PROMPT
        assert "digital" in EXTRACTION_SYSTEM_PROMPT

        # Primary fears
        assert "isolation" in EXTRACTION_SYSTEM_PROMPT
        assert "annihilation" in EXTRACTION_SYSTEM_PROMPT

        # Antagonists
        assert "system" in EXTRACTION_SYSTEM_PROMPT
        assert "technology" in EXTRACTION_SYSTEM_PROMPT

        # Mechanisms
        assert "surveillance" in EXTRACTION_SYSTEM_PROMPT
        assert "infection" in EXTRACTION_SYSTEM_PROMPT

        # Twists
        assert "revelation" in EXTRACTION_SYSTEM_PROMPT
        assert "inevitability" in EXTRACTION_SYSTEM_PROMPT
