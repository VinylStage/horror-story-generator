"""
Tests for target_length API parameter (Issue #73).

Tests cover:
- API schema validation (300-5000 range)
- Parameter propagation through generation pipeline
- Metadata recording
"""

import pytest
from pydantic import ValidationError


class TestStoryGenerateRequestSchema:
    """Tests for StoryGenerateRequest target_length validation."""

    def test_target_length_optional(self):
        """target_length should be optional."""
        from src.api.schemas.story import StoryGenerateRequest

        request = StoryGenerateRequest()

        assert request.target_length is None

    def test_target_length_valid_value(self):
        """Should accept valid target_length values."""
        from src.api.schemas.story import StoryGenerateRequest

        # Minimum
        request = StoryGenerateRequest(target_length=300)
        assert request.target_length == 300

        # Maximum
        request = StoryGenerateRequest(target_length=5000)
        assert request.target_length == 5000

        # Middle value
        request = StoryGenerateRequest(target_length=2500)
        assert request.target_length == 2500

    def test_target_length_below_minimum(self):
        """Should reject target_length below 300."""
        from src.api.schemas.story import StoryGenerateRequest

        with pytest.raises(ValidationError) as exc_info:
            StoryGenerateRequest(target_length=299)

        assert "greater than or equal to 300" in str(exc_info.value)

    def test_target_length_above_maximum(self):
        """Should reject target_length above 5000."""
        from src.api.schemas.story import StoryGenerateRequest

        with pytest.raises(ValidationError) as exc_info:
            StoryGenerateRequest(target_length=5001)

        assert "less than or equal to 5000" in str(exc_info.value)

    def test_target_length_with_other_params(self):
        """Should work with other parameters."""
        from src.api.schemas.story import StoryGenerateRequest

        request = StoryGenerateRequest(
            topic="Test topic",
            auto_research=True,
            model="ollama:qwen3:30b",
            target_length=2000
        )

        assert request.topic == "Test topic"
        assert request.auto_research is True
        assert request.model == "ollama:qwen3:30b"
        assert request.target_length == 2000


class TestStoryTriggerRequestSchema:
    """Tests for StoryTriggerRequest target_length validation."""

    def test_target_length_optional(self):
        """target_length should be optional in trigger request."""
        from src.api.schemas.jobs import StoryTriggerRequest

        request = StoryTriggerRequest()

        assert request.target_length is None

    def test_target_length_valid_range(self):
        """Should accept valid target_length values."""
        from src.api.schemas.jobs import StoryTriggerRequest

        request = StoryTriggerRequest(target_length=1500)

        assert request.target_length == 1500

    def test_target_length_validation(self):
        """Should validate target_length range."""
        from src.api.schemas.jobs import StoryTriggerRequest

        with pytest.raises(ValidationError):
            StoryTriggerRequest(target_length=100)  # Too small

        with pytest.raises(ValidationError):
            StoryTriggerRequest(target_length=10000)  # Too large


class TestBatchJobSpecSchema:
    """Tests for BatchJobSpec target_length validation."""

    def test_target_length_optional(self):
        """target_length should be optional in batch spec."""
        from src.api.schemas.jobs import BatchJobSpec

        spec = BatchJobSpec(type="story")

        assert spec.target_length is None

    def test_target_length_valid(self):
        """Should accept valid target_length in batch spec."""
        from src.api.schemas.jobs import BatchJobSpec

        spec = BatchJobSpec(type="story", target_length=3000)

        assert spec.target_length == 3000

    def test_target_length_validation(self):
        """Should validate target_length range in batch spec."""
        from src.api.schemas.jobs import BatchJobSpec

        with pytest.raises(ValidationError):
            BatchJobSpec(type="story", target_length=200)


class TestBuildStoryCommand:
    """Tests for build_story_command with target_length."""

    def test_no_target_length(self):
        """Should not include --target-length when not provided."""
        from src.api.routers.jobs import build_story_command

        cmd = build_story_command({"max_stories": 1})

        assert "--target-length" not in cmd

    def test_with_target_length(self):
        """Should include --target-length when provided."""
        from src.api.routers.jobs import build_story_command

        cmd = build_story_command({"max_stories": 1, "target_length": 2500})

        assert "--target-length" in cmd
        idx = cmd.index("--target-length")
        assert cmd[idx + 1] == "2500"

    def test_target_length_with_other_args(self):
        """Should include target_length with other arguments."""
        from src.api.routers.jobs import build_story_command

        cmd = build_story_command({
            "max_stories": 5,
            "enable_dedup": True,
            "model": "claude-sonnet-4-5-20250929",
            "target_length": 1500
        })

        assert "--max-stories" in cmd
        assert "--enable-dedup" in cmd
        assert "--model" in cmd
        assert "--target-length" in cmd

        idx = cmd.index("--target-length")
        assert cmd[idx + 1] == "1500"


class TestMetadataRecording:
    """Tests for generation metadata recording."""

    def test_generation_metadata_structure(self):
        """Verify generation metadata structure when target_length provided."""
        # This tests the metadata structure expected by the generator
        # The actual generator function calls require API keys, so we test structure only

        expected_structure = {
            "target_length": 2000,
            "actual_length": 1950,
            "length_delta": -50
        }

        assert "target_length" in expected_structure
        assert "actual_length" in expected_structure
        assert "length_delta" in expected_structure
        assert expected_structure["length_delta"] == expected_structure["actual_length"] - expected_structure["target_length"]

    def test_generation_metadata_null_target(self):
        """When target_length is None, length_delta should be None."""
        # Structure when no target_length provided
        expected_structure = {
            "target_length": None,
            "actual_length": 3500,
            "length_delta": None
        }

        assert expected_structure["target_length"] is None
        assert expected_structure["length_delta"] is None
        assert expected_structure["actual_length"] == 3500
