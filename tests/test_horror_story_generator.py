"""
Tests for horror_story_generator module.
"""

import json
import os
import re
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

        # Validate filename pattern
        filename = os.path.basename(file_path)
        assert re.match(r'story-\d{8}-\d{6}\.md', filename)

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

        # Validate vinylog fields
        assert 'slug: "story-' in content
        assert 'category: "Horror"' in content
        assert 'excerpt:' in content
        assert re.search(r'readTime: "\d+ min read"', content)
        assert 'featured: false' in content
        assert 'thumbnail: ""' in content
        assert re.search(r'date: "\d{4}-\d{2}-\d{2}"', content)
        assert 'tags:\n  - ' in content  # YAML array format

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

        # Validate filename pattern
        filename = json_files[0].name
        assert re.match(r'story-\d{8}-\d{6}_metadata\.json', filename)

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


class TestVinylogHelperFunctions:
    """Tests for vinylog integration helper functions."""

    def test_generate_slug(self):
        """Test slug generation from story ID."""
        from src.story.generator import generate_slug

        assert generate_slug("20260118_183713") == "story-20260118-183713"
        assert generate_slug("20251231_235959") == "story-20251231-235959"

    def test_calculate_read_time(self):
        """Test read time calculation."""
        from src.story.generator import calculate_read_time

        assert calculate_read_time(4376) == "22 min read"
        assert calculate_read_time(200) == "1 min read"
        assert calculate_read_time(100) == "1 min read"  # minimum
        assert calculate_read_time(50) == "1 min read"  # rounds to minimum

    def test_generate_story_filename(self):
        """Test story filename generation."""
        from src.story.generator import generate_story_filename

        assert generate_story_filename("20260118_183713") == "story-20260118-183713.md"


class TestSaveStoryVinylogFormat:
    """Tests for vinylog-specific save_story behavior."""

    def test_frontmatter_field_order(self, tmp_path):
        """Test that frontmatter fields appear in expected order."""
        file_path = save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata=None,
            template=None
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = content.split("---")[1]

        assert frontmatter.index("title:") < frontmatter.index("slug:")
        assert frontmatter.index("slug:") < frontmatter.index("category:")
        assert frontmatter.index("category:") < frontmatter.index("date:")

    def test_tags_yaml_array_format(self, tmp_path):
        """Test that tags are formatted as YAML array, not JSON."""
        file_path = save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata=None,
            template=None
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert '["호러", "horror"]' not in content
        assert 'tags:\n  - 호러\n  - horror' in content

    def test_description_escaping(self, tmp_path):
        """Test that quotes in description are properly escaped."""
        story_with_quotes = '# Test Story\n\nShe said "hello" to me.'

        file_path = save_story(
            story_text=story_with_quotes,
            output_dir=str(tmp_path),
            metadata=None,
            template=None
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'excerpt: "She said \\"hello\\"' in content

    def test_metadata_json_filename_consistency(self, tmp_path):
        """Test that metadata JSON filename matches markdown filename."""
        save_story(
            story_text="# Test Story\n\nContent...",
            output_dir=str(tmp_path),
            metadata={"model": "claude-test"},
            template=None
        )

        md_files = list(tmp_path.glob("story-*.md"))
        json_files = list(tmp_path.glob("story-*_metadata.json"))

        assert len(md_files) == 1
        assert len(json_files) == 1

        md_id = md_files[0].stem
        json_id = json_files[0].stem.replace("_metadata", "")

        assert md_id == json_id
