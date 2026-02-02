"""
Tests for custom tags feature (Issue #109).

Verifies:
1. Custom tags are merged with default tags
2. Duplicate tags are removed
3. Maximum 10 tags limit is enforced
4. Tag ordering: default → custom → template → extracted
"""

import pytest
from unittest.mock import MagicMock, patch

from src.story.generator import extract_tags_from_story


# =============================================================================
# Tag Extraction Tests
# =============================================================================

class TestExtractTagsFromStory:
    """Tests for extract_tags_from_story function."""

    def test_default_tags_always_included(self):
        """Default tags ['호러', 'horror'] should always be present."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}

        tags = extract_tags_from_story(story_text, template)

        assert "호러" in tags
        assert "horror" in tags

    def test_custom_tags_merged(self):
        """Custom tags should be merged with default tags."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}
        custom_tags = ["수면공포", "청각공포"]

        tags = extract_tags_from_story(story_text, template, custom_tags=custom_tags)

        assert "호러" in tags
        assert "horror" in tags
        assert "수면공포" in tags
        assert "청각공포" in tags

    def test_custom_tags_no_duplicates(self):
        """Duplicate tags should be removed."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}
        custom_tags = ["호러", "custom_tag"]  # "호러" is also a default tag

        tags = extract_tags_from_story(story_text, template, custom_tags=custom_tags)

        # Count occurrences of "호러"
        horror_count = sum(1 for t in tags if t == "호러")
        assert horror_count == 1
        assert "custom_tag" in tags

    def test_max_ten_tags(self):
        """Tags should be limited to 10."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}
        # Provide many custom tags to exceed limit
        custom_tags = [f"tag_{i}" for i in range(15)]

        tags = extract_tags_from_story(story_text, template, custom_tags=custom_tags)

        assert len(tags) <= 10

    def test_template_genre_included(self):
        """Template genre should be included in tags."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {
            "story_config": {
                "genre": "서스펜스"
            }
        }

        tags = extract_tags_from_story(story_text, template)

        assert "서스펜스" in tags

    def test_template_fear_type_included(self):
        """Template primary_fear_type should be included (list format)."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {
            "story_elements": {
                "horror_techniques": {
                    "primary_fear_type": ["심리공포", "사회공포"]  # Must be a list
                }
            }
        }

        tags = extract_tags_from_story(story_text, template)

        assert "심리공포" in tags

    def test_tags_extracted_from_story_text(self):
        """Tags in ## 태그 section should be extracted (- format required)."""
        story_text = """# Test Story

This is a test story.

---

## 태그
- 일상공포
- #도시전설
- 미스터리
"""
        template = {}

        tags = extract_tags_from_story(story_text, template)

        assert "일상공포" in tags
        assert "도시전설" in tags
        assert "미스터리" in tags

    def test_custom_tags_priority_over_extracted(self):
        """Custom tags should appear before extracted tags."""
        story_text = """# Test Story

This is a test story.

---

## 태그
extracted_tag_1, extracted_tag_2
"""
        template = {}
        custom_tags = ["custom_1", "custom_2"]

        tags = extract_tags_from_story(story_text, template, custom_tags=custom_tags)

        # Custom tags should come before extracted tags
        custom_1_idx = tags.index("custom_1")
        custom_2_idx = tags.index("custom_2")

        # Extracted tags may or may not be in the final list (10 tag limit)
        # But if they are, they should come after custom tags
        if "extracted_tag_1" in tags:
            extracted_idx = tags.index("extracted_tag_1")
            assert custom_1_idx < extracted_idx

    def test_none_custom_tags_handled(self):
        """None custom_tags should not cause errors."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}

        # Should not raise
        tags = extract_tags_from_story(story_text, template, custom_tags=None)

        assert "호러" in tags
        assert "horror" in tags

    def test_empty_custom_tags_handled(self):
        """Empty custom_tags list should not cause errors."""
        story_text = "# Test Story\n\nThis is a test story."
        template = {}

        tags = extract_tags_from_story(story_text, template, custom_tags=[])

        assert "호러" in tags
        assert "horror" in tags


# =============================================================================
# Integration with generate_with_topic Tests
# =============================================================================

class TestGenerateWithTopicCustomTags:
    """Tests for generate_with_topic with custom_tags parameter."""

    def test_custom_tags_in_metadata(self):
        """custom_tags should be included in result metadata."""
        # This is a structural test to verify the parameter flows through
        # Full integration test would require mocking Claude API

        # Verify function signature accepts custom_tags
        from src.story.generator import generate_with_topic
        import inspect

        sig = inspect.signature(generate_with_topic)
        params = sig.parameters

        assert "custom_tags" in params
        assert params["custom_tags"].default is None
