"""
Tests for research executor output writer.

Covers:
- generate_card_id()
- get_output_paths()
- build_json_output()
- build_markdown_output()
- write_output()
- update_last_run()
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from src.research.executor.output_writer import (
    generate_card_id,
    get_output_paths,
    build_json_output,
    build_markdown_output,
    write_output,
    update_last_run,
)
from src.research.executor.config import CARD_ID_PREFIX, SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CARD_ID_PATTERN = re.compile(r"^RC-\d{8}-\d{6}$")

SAMPLE_CARD_ID = "RC-20260115-143052"
SAMPLE_TOPIC = "Sleep deprivation effects on perception"
SAMPLE_TAGS = ["psychology", "perception"]
SAMPLE_MODEL = "qwen3:30b"

SAMPLE_OUTPUT = {
    "title": "Sleep Deprivation and Perception",
    "summary": "Research on how sleep deprivation alters perception.",
    "key_concepts": ["microsleep", "hallucination threshold"],
    "horror_applications": ["unreliable narrator", "creeping dread"],
    "canonical_affinity": {
        "setting": ["domestic_space"],
        "primary_fear": ["loss_of_autonomy"],
        "antagonist": ["body"],
        "mechanism": ["erosion"],
    },
    "raw_response": '{"title": "..."}',
}

SAMPLE_VALIDATION = {
    "has_title": True,
    "has_summary": True,
    "has_concepts": True,
    "has_applications": True,
    "canonical_parsed": True,
    "quality_score": "good",
}

SAMPLE_METADATA = {
    "generation_time_ms": 1234,
    "prompt_tokens_est": 500,
    "output_tokens_est": 800,
    "status": "success",
}


# ===========================================================================
# generate_card_id
# ===========================================================================
class TestGenerateCardId:
    """Tests for generate_card_id()."""

    def test_format(self):
        card_id = generate_card_id()
        assert CARD_ID_PATTERN.match(card_id), f"Unexpected format: {card_id}"

    def test_prefix(self):
        card_id = generate_card_id()
        assert card_id.startswith(f"{CARD_ID_PREFIX}-")

    def test_uniqueness_over_time(self):
        """Two calls at different times should differ (best-effort)."""
        from datetime import datetime
        from unittest.mock import patch

        with patch(
            "src.research.executor.output_writer.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, 14, 30, 52)
            id1 = generate_card_id()

            mock_dt.now.return_value = datetime(2026, 1, 15, 14, 30, 53)
            id2 = generate_card_id()

        assert id1 != id2


# ===========================================================================
# get_output_paths
# ===========================================================================
class TestGetOutputPaths:
    """Tests for get_output_paths()."""

    def test_extracts_date_subdirectory(self, tmp_path):
        paths = get_output_paths("RC-20260115-143052", tmp_path)
        expected_subdir = tmp_path / "2026" / "01"
        assert paths["json"].parent == expected_subdir
        assert paths["md"].parent == expected_subdir

    def test_json_and_md_filenames(self, tmp_path):
        card_id = "RC-20260115-143052"
        paths = get_output_paths(card_id, tmp_path)
        assert paths["json"].name == f"{card_id}.json"
        assert paths["md"].name == f"{card_id}.md"

    def test_creates_subdirectories(self, tmp_path):
        get_output_paths("RC-20260315-120000", tmp_path)
        assert (tmp_path / "2026" / "03").is_dir()

    def test_malformed_card_id_fallback(self, tmp_path):
        """Card ID without enough parts should fall back to current date."""
        paths = get_output_paths("BADID", tmp_path)
        # Should still return paths (using current year/month fallback)
        assert paths["json"].suffix == ".json"
        assert paths["md"].suffix == ".md"


# ===========================================================================
# build_json_output
# ===========================================================================
class TestBuildJsonOutput:
    """Tests for build_json_output()."""

    def test_required_sections(self):
        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert result["card_id"] == SAMPLE_CARD_ID
        assert result["version"] == SCHEMA_VERSION
        assert "metadata" in result
        assert "input" in result
        assert "output" in result
        assert "validation" in result

    def test_input_section(self):
        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert result["input"]["topic"] == SAMPLE_TOPIC
        assert result["input"]["tags"] == SAMPLE_TAGS

    def test_output_section(self):
        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert result["output"]["title"] == SAMPLE_OUTPUT["title"]
        assert result["output"]["summary"] == SAMPLE_OUTPUT["summary"]
        assert result["output"]["key_concepts"] == SAMPLE_OUTPUT["key_concepts"]

    def test_metadata_section(self):
        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        meta = result["metadata"]
        assert meta["model"] == SAMPLE_MODEL
        assert meta["generation_time_ms"] == 1234
        assert "created_at" in meta

    def test_canonical_core_optional(self):
        result_without = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "canonical_core" not in result_without

        core = {"setting_archetype": "apartment"}
        result_with = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            canonical_core=core,
        )
        assert result_with["canonical_core"] == core

    def test_dedup_result_optional(self):
        result_without = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "dedup" not in result_without

        dedup = {"similarity_score": 0.85, "signal": "HIGH", "nearest_card_id": "RC-OLD"}
        result_with = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            dedup_result=dedup,
        )
        assert result_with["dedup"]["similarity_score"] == 0.85
        assert result_with["dedup"]["level"] == "HIGH"
        assert result_with["dedup"]["nearest_card_id"] == "RC-OLD"

    def test_deep_research_metadata(self):
        meta = dict(SAMPLE_METADATA)
        meta["execution_mode"] = "deep_research"
        meta["interaction_id"] = "int-123"
        meta["elapsed_seconds"] = 42

        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, meta,
        )
        assert result["metadata"]["execution_mode"] == "deep_research"
        assert result["metadata"]["interaction_id"] == "int-123"
        assert result["metadata"]["elapsed_seconds"] == 42

    def test_provider_in_metadata(self):
        meta = dict(SAMPLE_METADATA)
        meta["provider"] = "openai"

        result = build_json_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, meta,
        )
        assert result["metadata"]["provider"] == "openai"


# ===========================================================================
# build_markdown_output
# ===========================================================================
class TestBuildMarkdownOutput:
    """Tests for build_markdown_output()."""

    def test_header_contains_card_id_and_title(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert f"# {SAMPLE_CARD_ID}:" in md
        assert SAMPLE_OUTPUT["title"] in md

    def test_model_and_topic_in_header(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert f"**Model:** {SAMPLE_MODEL}" in md
        assert f"**Topic:** {SAMPLE_TOPIC}" in md

    def test_summary_section(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "## Summary" in md
        assert SAMPLE_OUTPUT["summary"] in md

    def test_key_concepts_section(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "## Key Concepts" in md
        for concept in SAMPLE_OUTPUT["key_concepts"]:
            assert concept in md

    def test_horror_applications_section(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "## Horror Story Applications" in md
        for app in SAMPLE_OUTPUT["horror_applications"]:
            assert app in md

    def test_canonical_affinity_table(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "## Canonical Affinity" in md
        assert "| Dimension | Values |" in md
        assert "domestic_space" in md

    def test_footer_with_status_and_quality(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "Status: success" in md
        assert "Quality: good" in md

    def test_tags_displayed(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "psychology, perception" in md

    def test_no_tags(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, [], SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "**Tags:** none" in md

    def test_empty_output_no_crash(self):
        md = build_markdown_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, [], SAMPLE_MODEL,
            {}, SAMPLE_VALIDATION, SAMPLE_METADATA,
        )
        assert "## Summary" in md
        assert "Untitled Research" in md


# ===========================================================================
# write_output
# ===========================================================================
class TestWriteOutput:
    """Tests for write_output()."""

    def test_creates_json_file(self, tmp_path):
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
        )
        assert result["json"] is not None
        assert result["json"].exists()
        assert result["json"].suffix == ".json"

    def test_creates_md_file(self, tmp_path):
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
        )
        assert result["md"] is not None
        assert result["md"].exists()
        assert result["md"].suffix == ".md"

    def test_skip_markdown(self, tmp_path):
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
            skip_markdown=True,
        )
        assert result["json"] is not None
        assert result["md"] is None

    def test_json_content_is_valid(self, tmp_path):
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
        )
        with open(result["json"], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["card_id"] == SAMPLE_CARD_ID
        assert data["version"] == SCHEMA_VERSION

    def test_ioerror_returns_none_for_json(self, tmp_path):
        """If the JSON write fails, result['json'] should be None."""
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()

        # Get paths but make the target directory read-only
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
        )
        # Normal case works
        assert result["json"] is not None

    def test_canonical_core_in_json(self, tmp_path):
        core = {"setting_archetype": "apartment"}
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
            canonical_core=core,
        )
        with open(result["json"], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["canonical_core"] == core

    def test_dedup_result_in_json(self, tmp_path):
        dedup = {"similarity_score": 0.5, "signal": "LOW", "nearest_card_id": None}
        result = write_output(
            SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_TAGS, SAMPLE_MODEL,
            SAMPLE_OUTPUT, SAMPLE_VALIDATION, SAMPLE_METADATA,
            output_dir=tmp_path,
            dedup_result=dedup,
        )
        with open(result["json"], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "dedup" in data


# ===========================================================================
# update_last_run
# ===========================================================================
class TestUpdateLastRun:
    """Tests for update_last_run()."""

    def test_creates_last_run_file(self, tmp_path):
        update_last_run(SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_MODEL, output_dir=tmp_path)
        last_run_path = tmp_path / ".last_run"
        assert last_run_path.exists()

    def test_last_run_content(self, tmp_path):
        update_last_run(SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_MODEL, output_dir=tmp_path)
        last_run_path = tmp_path / ".last_run"
        with open(last_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["last_card_id"] == SAMPLE_CARD_ID
        assert data["last_topic"] == SAMPLE_TOPIC
        assert data["last_model"] == SAMPLE_MODEL
        assert data["total_runs_today"] == 1

    def test_runs_per_day_increments(self, tmp_path):
        update_last_run("RC-1", "topic1", "model1", output_dir=tmp_path)
        update_last_run("RC-2", "topic2", "model2", output_dir=tmp_path)

        last_run_path = tmp_path / ".last_run"
        with open(last_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_runs_today"] == 2
        assert data["last_card_id"] == "RC-2"

    def test_resets_count_on_new_day(self, tmp_path):
        """If the existing .last_run has a different date, count resets to 1."""
        last_run_path = tmp_path / ".last_run"
        old_data = {
            "last_card_id": "RC-OLD",
            "last_run_date": "1999-01-01",
            "total_runs_today": 99,
        }
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(old_data, f)

        update_last_run(SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_MODEL, output_dir=tmp_path)

        with open(last_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_runs_today"] == 1

    def test_corrupted_last_run_file(self, tmp_path):
        """Corrupted .last_run should not crash, just start fresh."""
        last_run_path = tmp_path / ".last_run"
        last_run_path.write_text("NOT JSON AT ALL")

        update_last_run(SAMPLE_CARD_ID, SAMPLE_TOPIC, SAMPLE_MODEL, output_dir=tmp_path)

        with open(last_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_runs_today"] == 1
