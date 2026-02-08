"""
Tests for research executor validator.

Covers:
- extract_json_from_response()
- validate_research_output()
- validate_canonical_values()
- process_llm_response()
"""

import json

import pytest

from src.research.executor.validator import (
    extract_json_from_response,
    validate_research_output,
    validate_canonical_values,
    process_llm_response,
)
from src.research.executor.config import (
    VALID_SETTINGS,
    VALID_PRIMARY_FEARS,
    VALID_ANTAGONISTS,
    VALID_MECHANISMS,
)

# ---------------------------------------------------------------------------
# Constants / Fixtures
# ---------------------------------------------------------------------------
VALID_OUTPUT = {
    "title": "Test Title",
    "summary": "A meaningful summary of the research.",
    "key_concepts": ["concept1", "concept2"],
    "horror_applications": ["app1", "app2"],
    "canonical_affinity": {
        "setting": ["apartment", "hospital"],
        "primary_fear": ["isolation"],
        "antagonist": ["system"],
        "mechanism": ["surveillance"],
    },
}


@pytest.fixture
def valid_json_response():
    """Raw LLM response containing valid JSON."""
    return json.dumps(VALID_OUTPUT)


@pytest.fixture
def full_parsed_output():
    """Fully populated parsed output dict."""
    return dict(VALID_OUTPUT)


# ===========================================================================
# extract_json_from_response
# ===========================================================================
class TestExtractJsonFromResponse:
    """Tests for extract_json_from_response()."""

    def test_valid_json_string(self, valid_json_response):
        parsed, error = extract_json_from_response(valid_json_response)
        assert parsed is not None
        assert error is None
        assert parsed["title"] == "Test Title"

    def test_markdown_code_block_json(self):
        raw = '```json\n{"title": "From Code Block"}\n```'
        parsed, error = extract_json_from_response(raw)
        assert parsed is not None
        assert error is None
        assert parsed["title"] == "From Code Block"

    def test_markdown_code_block_no_language(self):
        raw = '```\n{"title": "No Lang"}\n```'
        parsed, error = extract_json_from_response(raw)
        assert parsed is not None
        assert error is None
        assert parsed["title"] == "No Lang"

    def test_surrounding_text(self):
        raw = 'Here is the JSON:\n{"title": "Extracted"}\nHope this helps!'
        parsed, error = extract_json_from_response(raw)
        assert parsed is not None
        assert error is None
        assert parsed["title"] == "Extracted"

    def test_invalid_json(self):
        raw = "{this is not valid json at all"
        parsed, error = extract_json_from_response(raw)
        assert parsed is None
        assert error is not None

    def test_empty_string(self):
        parsed, error = extract_json_from_response("")
        assert parsed is None
        assert error == "Empty response"

    def test_whitespace_only(self):
        parsed, error = extract_json_from_response("   \n\t  ")
        assert parsed is None
        assert error == "Empty response"

    def test_none_input(self):
        parsed, error = extract_json_from_response(None)
        assert parsed is None
        assert error == "Empty response"

    def test_no_json_in_text(self):
        raw = "This is just plain text with no JSON at all."
        parsed, error = extract_json_from_response(raw)
        assert parsed is None
        assert error is not None

    def test_nested_json_object(self):
        raw = json.dumps({"outer": {"inner": "value"}})
        parsed, error = extract_json_from_response(raw)
        assert parsed is not None
        assert parsed["outer"]["inner"] == "value"


# ===========================================================================
# validate_research_output
# ===========================================================================
class TestValidateResearchOutput:
    """Tests for validate_research_output()."""

    def test_all_fields_present_good_quality(self, full_parsed_output):
        result = validate_research_output(full_parsed_output)
        assert result["has_title"] is True
        assert result["has_summary"] is True
        assert result["has_concepts"] is True
        assert result["has_applications"] is True
        assert result["canonical_parsed"] is True
        assert result["quality_score"] == "good"

    def test_empty_dict_incomplete(self):
        result = validate_research_output({})
        assert result["has_title"] is False
        assert result["has_summary"] is False
        assert result["has_concepts"] is False
        assert result["has_applications"] is False
        assert result["canonical_parsed"] is False
        assert result["quality_score"] == "incomplete"

    def test_partial_quality_three_fields(self):
        """Three out of five checks passing => partial."""
        data = {
            "title": "A Title",
            "summary": "A Summary",
            "key_concepts": ["c1"],
            "horror_applications": [],
            "canonical_affinity": {},
        }
        result = validate_research_output(data)
        assert result["quality_score"] == "partial"

    def test_title_must_be_non_empty_string(self):
        result = validate_research_output({"title": ""})
        assert result["has_title"] is False

        result = validate_research_output({"title": "   "})
        assert result["has_title"] is False

        result = validate_research_output({"title": 123})
        assert result["has_title"] is False

    def test_summary_must_be_non_empty_string(self):
        result = validate_research_output({"summary": ""})
        assert result["has_summary"] is False

        result = validate_research_output({"summary": "valid"})
        assert result["has_summary"] is True

    def test_concepts_must_be_non_empty_list(self):
        result = validate_research_output({"key_concepts": []})
        assert result["has_concepts"] is False

        result = validate_research_output({"key_concepts": "not a list"})
        assert result["has_concepts"] is False

        result = validate_research_output({"key_concepts": ["one"]})
        assert result["has_concepts"] is True

    def test_applications_must_be_non_empty_list(self):
        result = validate_research_output({"horror_applications": []})
        assert result["has_applications"] is False

        result = validate_research_output({"horror_applications": ["one"]})
        assert result["has_applications"] is True

    def test_canonical_affinity_requires_valid_list(self):
        """canonical_parsed needs at least one dimension with a non-empty list."""
        # No canonical_affinity key
        result = validate_research_output({})
        assert result["canonical_parsed"] is False

        # Empty dict
        result = validate_research_output({"canonical_affinity": {}})
        assert result["canonical_parsed"] is False

        # Empty lists
        result = validate_research_output(
            {"canonical_affinity": {"setting": [], "primary_fear": []}}
        )
        assert result["canonical_parsed"] is False

        # One valid dimension
        result = validate_research_output(
            {"canonical_affinity": {"setting": ["apartment"]}}
        )
        assert result["canonical_parsed"] is True

    @pytest.mark.parametrize(
        "passed_count,expected_score",
        [
            (5, "good"),
            (4, "partial"),
            (3, "partial"),
            (2, "incomplete"),
            (1, "incomplete"),
            (0, "incomplete"),
        ],
    )
    def test_quality_score_thresholds(self, passed_count, expected_score):
        """Quality score depends on how many of 5 checks pass."""
        fields = [
            ("title", "T"),
            ("summary", "S"),
            ("key_concepts", ["c"]),
            ("horror_applications", ["a"]),
            ("canonical_affinity", {"setting": ["apartment"]}),
        ]
        data = {}
        for i, (key, val) in enumerate(fields):
            if i < passed_count:
                data[key] = val
        result = validate_research_output(data)
        assert result["quality_score"] == expected_score


# ===========================================================================
# validate_canonical_values
# ===========================================================================
class TestValidateCanonicalValues:
    """Tests for validate_canonical_values()."""

    def test_all_valid_values(self):
        data = {
            "canonical_affinity": {
                "setting": [VALID_SETTINGS[0]],
                "primary_fear": [VALID_PRIMARY_FEARS[0]],
                "antagonist": [VALID_ANTAGONISTS[0]],
                "mechanism": [VALID_MECHANISMS[0]],
            }
        }
        result = validate_canonical_values(data)
        for dim in ["setting", "primary_fear", "antagonist", "mechanism"]:
            assert len(result[dim]["valid"]) == 1
            assert len(result[dim]["invalid"]) == 0

    def test_invalid_values(self):
        data = {
            "canonical_affinity": {
                "setting": ["nonexistent_setting"],
                "primary_fear": ["made_up_fear"],
                "antagonist": ["fake_antagonist"],
                "mechanism": ["unknown_mechanism"],
            }
        }
        result = validate_canonical_values(data)
        for dim in ["setting", "primary_fear", "antagonist", "mechanism"]:
            assert len(result[dim]["valid"]) == 0
            assert len(result[dim]["invalid"]) == 1

    def test_mixed_valid_invalid(self):
        data = {
            "canonical_affinity": {
                "setting": [VALID_SETTINGS[0], "fake_setting"],
            }
        }
        result = validate_canonical_values(data)
        assert len(result["setting"]["valid"]) == 1
        assert len(result["setting"]["invalid"]) == 1

    def test_missing_affinity(self):
        result = validate_canonical_values({})
        for dim in ["setting", "primary_fear", "antagonist", "mechanism"]:
            assert result[dim]["valid"] == []
            assert result[dim]["invalid"] == []

    def test_empty_affinity(self):
        result = validate_canonical_values({"canonical_affinity": {}})
        for dim in ["setting", "primary_fear", "antagonist", "mechanism"]:
            assert result[dim]["valid"] == []
            assert result[dim]["invalid"] == []

    def test_non_string_values_ignored(self):
        data = {
            "canonical_affinity": {
                "setting": [123, None, True, VALID_SETTINGS[0]],
            }
        }
        result = validate_canonical_values(data)
        assert len(result["setting"]["valid"]) == 1
        assert len(result["setting"]["invalid"]) == 0

    @pytest.mark.parametrize("dim,valid_set", [
        ("setting", VALID_SETTINGS),
        ("primary_fear", VALID_PRIMARY_FEARS),
        ("antagonist", VALID_ANTAGONISTS),
        ("mechanism", VALID_MECHANISMS),
    ])
    def test_all_valid_values_accepted(self, dim, valid_set):
        """Every value in each valid set should be accepted."""
        data = {"canonical_affinity": {dim: valid_set}}
        result = validate_canonical_values(data)
        assert len(result[dim]["valid"]) == len(valid_set)
        assert len(result[dim]["invalid"]) == 0


# ===========================================================================
# process_llm_response
# ===========================================================================
class TestProcessLlmResponse:
    """Tests for process_llm_response()."""

    def test_never_raises_on_empty(self):
        output, validation = process_llm_response("")
        assert isinstance(output, dict)
        assert isinstance(validation, dict)

    def test_never_raises_on_none(self):
        output, validation = process_llm_response(None)
        assert isinstance(output, dict)
        assert isinstance(validation, dict)

    def test_never_raises_on_garbage(self):
        output, validation = process_llm_response("not json at all {{{")
        assert isinstance(output, dict)
        assert isinstance(validation, dict)

    def test_empty_defaults(self):
        output, validation = process_llm_response("")
        assert output["title"] == ""
        assert output["summary"] == ""
        assert output["key_concepts"] == []
        assert output["horror_applications"] == []
        assert output["canonical_affinity"]["setting"] == []
        assert validation["quality_score"] == "parse_failed"

    def test_valid_response_parsed(self, valid_json_response):
        output, validation = process_llm_response(valid_json_response)
        assert output["title"] == "Test Title"
        assert output["summary"] == "A meaningful summary of the research."
        assert len(output["key_concepts"]) == 2
        assert len(output["horror_applications"]) == 2
        assert validation["parse_error"] is None

    def test_title_truncation(self):
        long_title = "A" * 200
        data = json.dumps({"title": long_title})
        output, _ = process_llm_response(data)
        assert len(output["title"]) == 80

    def test_key_concepts_item_limit(self):
        data = json.dumps({"key_concepts": [f"c{i}" for i in range(20)]})
        output, _ = process_llm_response(data)
        assert len(output["key_concepts"]) == 10

    def test_horror_applications_item_limit(self):
        data = json.dumps({"horror_applications": [f"a{i}" for i in range(20)]})
        output, _ = process_llm_response(data)
        assert len(output["horror_applications"]) == 10

    def test_raw_response_preserved(self, valid_json_response):
        output, _ = process_llm_response(valid_json_response)
        assert output["raw_response"] == valid_json_response

    def test_parse_error_on_invalid_json(self):
        _, validation = process_llm_response("no json here")
        assert validation["parse_error"] is not None
        assert validation["quality_score"] == "parse_failed"

    def test_canonical_affinity_merged(self):
        data = json.dumps({
            "canonical_affinity": {
                "setting": ["apartment"],
                "primary_fear": ["isolation"],
            }
        })
        output, _ = process_llm_response(data)
        assert output["canonical_affinity"]["setting"] == ["apartment"]
        assert output["canonical_affinity"]["primary_fear"] == ["isolation"]
        # Unspecified dimensions remain empty
        assert output["canonical_affinity"]["antagonist"] == []
        assert output["canonical_affinity"]["mechanism"] == []
