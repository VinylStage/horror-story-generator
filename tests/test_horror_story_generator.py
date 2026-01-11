"""
Tests for horror_story_generator module.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.story.generator import (
    load_prompt_template,
    extract_title_from_story,
    extract_tags_from_story,
    generate_description,
    save_story,
)


class TestExtractTitleFromStory:
    """Tests for extract_title_from_story function."""

    def test_extract_title_with_markdown(self):
        """Test extracting title from markdown format."""
        story = "# The Haunted House\n\nOnce upon a time..."
        title = extract_title_from_story(story)
        assert title == "The Haunted House"

    def test_extract_title_with_korean(self):
        """Test extracting Korean title."""
        story = "# 귀신의 집\n\n옛날 옛적에..."
        title = extract_title_from_story(story)
        assert title == "귀신의 집"

    def test_no_title_returns_default(self):
        """Test that missing title returns default."""
        story = "Once upon a time..."
        title = extract_title_from_story(story)
        assert title == "무제"

    def test_title_with_extra_whitespace(self):
        """Test title with extra whitespace."""
        story = "#   Test Title   \n\nContent..."
        title = extract_title_from_story(story)
        assert title == "Test Title"


class TestExtractTagsFromStory:
    """Tests for extract_tags_from_story function."""

    def test_default_tags(self):
        """Test that default tags are included."""
        story = "# Test\n\nContent..."
        template = {}
        tags = extract_tags_from_story(story, template)

        assert "호러" in tags
        assert "horror" in tags

    def test_genre_from_template(self):
        """Test genre tag from template."""
        story = "# Test\n\nContent..."
        template = {"story_config": {"genre": "psychological_horror"}}
        tags = extract_tags_from_story(story, template)

        assert "psychological_horror" in tags

    def test_tag_section_extraction(self):
        """Test extracting tags from story's tag section."""
        story = "# Test\n\n## 태그\n- #공포\n- #심리\n\n## 본문\nContent..."
        template = {}
        tags = extract_tags_from_story(story, template)

        assert "공포" in tags
        assert "심리" in tags

    def test_unique_tags(self):
        """Test that duplicate tags are removed."""
        story = "# Test\n\n## 태그\n- #horror\n- #horror\n\n## 본문\nContent..."
        template = {}
        tags = extract_tags_from_story(story, template)

        # Count occurrences of 'horror' (case-insensitive)
        horror_count = sum(1 for t in tags if t.lower() == "horror")
        assert horror_count == 1

    def test_max_tags_limit(self):
        """Test that tags are limited to 10."""
        story = "# Test\n\n## 태그\n" + "\n".join([f"- #tag{i}" for i in range(20)])
        template = {"story_config": {"genre": "test_genre"}}
        tags = extract_tags_from_story(story, template)

        assert len(tags) <= 10


class TestGenerateDescription:
    """Tests for generate_description function."""

    def test_description_from_first_paragraph(self):
        """Test description extraction from first paragraph."""
        story = "# Title\n\nThis is the first paragraph.\n\nSecond paragraph."
        desc = generate_description(story)

        assert "This is the first paragraph" in desc

    def test_description_max_length(self):
        """Test that description is limited to 200 chars."""
        long_text = "A" * 500
        story = f"# Title\n\n{long_text}"
        desc = generate_description(story)

        assert len(desc) <= 203  # 200 + "..."

    def test_description_ellipsis(self):
        """Test ellipsis for truncated description."""
        long_text = "A" * 500
        story = f"# Title\n\n{long_text}"
        desc = generate_description(story)

        assert desc.endswith("...")


class TestSaveStory:
    """Tests for save_story function."""

    def test_save_creates_directory(self, tmp_path):
        """Test that save_story creates output directory."""
        output_dir = tmp_path / "new_dir"
        assert not output_dir.exists()

        save_story(
            story_text="# Test\n\nContent...",
            output_dir=str(output_dir),
            metadata=None,
            template=None
        )

        assert output_dir.exists()

    def test_save_creates_md_file(self, tmp_path):
        """Test that save_story creates markdown file."""
        file_path = save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata=None,
            template=None
        )

        assert file_path.endswith(".md")
        assert os.path.exists(file_path)

    def test_save_with_frontmatter(self, tmp_path):
        """Test that saved file includes YAML frontmatter."""
        file_path = save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata={"model": "claude-test"},
            template=None
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert content.startswith("---")
        assert 'title: "Test Story"' in content
        assert "draft: false" in content

    def test_save_creates_metadata_json(self, tmp_path):
        """Test that save_story creates metadata JSON file."""
        save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata={"model": "claude-test"},
            template=None
        )

        json_files = list(tmp_path.glob("*_metadata.json"))
        assert len(json_files) == 1

        with open(json_files[0], "r", encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["model"] == "claude-test"
        assert metadata["title"] == "Test Story"


class TestLoadPromptTemplate:
    """Tests for load_prompt_template function."""

    def test_load_existing_template(self, tmp_path):
        """Test loading an existing template file."""
        template_data = {
            "story_config": {"genre": "horror"},
            "story_elements": {"setting": {"location": "hospital"}}
        }

        template_path = tmp_path / "test_template.json"
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f)

        loaded = load_prompt_template(str(template_path))

        assert loaded["story_config"]["genre"] == "horror"
        assert loaded["story_elements"]["setting"]["location"] == "hospital"

    def test_load_nonexistent_template(self):
        """Test loading a non-existent template file raises error."""
        with pytest.raises(FileNotFoundError):
            load_prompt_template("/nonexistent/path/template.json")
