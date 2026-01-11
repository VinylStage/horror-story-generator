"""
Tests for similarity module.
"""

import pytest

from src.dedup.similarity import (
    GenerationRecord,
    compute_text_similarity,
    observe_similarity,
    add_to_generation_memory,
    get_similarity_signal,
    should_accept_story,
    get_generation_memory_count,
    clear_generation_memory,
)


class TestComputeTextSimilarity:
    """Tests for compute_text_similarity function."""

    def test_identical_texts(self):
        """Test similarity of identical texts."""
        result = compute_text_similarity("hello world", "hello world")
        assert result == 1.0

    def test_completely_different_texts(self):
        """Test similarity of completely different texts."""
        result = compute_text_similarity("hello world", "foo bar baz")
        assert result == 0.0

    def test_partially_similar_texts(self):
        """Test similarity of partially similar texts."""
        result = compute_text_similarity(
            "hello world test",
            "hello world example"
        )
        # "hello" and "world" match, 2 out of 4 unique words = 0.5
        assert result == 0.5

    def test_empty_text(self):
        """Test similarity with empty text."""
        assert compute_text_similarity("", "hello") == 0.0
        assert compute_text_similarity("hello", "") == 0.0
        assert compute_text_similarity("", "") == 0.0

    def test_case_insensitive(self):
        """Test that similarity is case-insensitive."""
        result = compute_text_similarity("Hello World", "hello world")
        assert result == 1.0

    def test_korean_text(self):
        """Test similarity with Korean text."""
        result = compute_text_similarity(
            "안녕하세요 반갑습니다",
            "안녕하세요 감사합니다"
        )
        # "안녕하세요" matches, 1 out of 3 unique words
        assert result == pytest.approx(1/3, rel=0.01)


class TestGenerationRecord:
    """Tests for GenerationRecord dataclass."""

    def test_create_record(self):
        """Test creating a GenerationRecord."""
        record = GenerationRecord(
            story_id="test_001",
            template_id="T-001",
            title="Test Story",
            semantic_summary="This is a test story.",
            canonical_keys={"setting": "digital"},
            generated_at="2026-01-11T12:00:00"
        )

        assert record.story_id == "test_001"
        assert record.template_id == "T-001"
        assert record.title == "Test Story"
        assert record.semantic_summary == "This is a test story."
        assert record.canonical_keys == {"setting": "digital"}
        assert record.generated_at == "2026-01-11T12:00:00"


class TestGenerationMemory:
    """Tests for generation memory functions."""

    def setup_method(self):
        """Clear memory before each test."""
        clear_generation_memory()

    def teardown_method(self):
        """Clear memory after each test."""
        clear_generation_memory()

    def test_add_to_memory(self):
        """Test adding to generation memory."""
        assert get_generation_memory_count() == 0

        add_to_generation_memory(
            story_id="test_001",
            template_id="T-001",
            title="Test Story",
            semantic_summary="Test summary",
            canonical_keys={}
        )

        assert get_generation_memory_count() == 1

    def test_clear_memory(self):
        """Test clearing generation memory."""
        add_to_generation_memory(
            story_id="test_001",
            template_id="T-001",
            title="Test Story",
            semantic_summary="Test summary",
            canonical_keys={}
        )

        assert get_generation_memory_count() == 1
        clear_generation_memory()
        assert get_generation_memory_count() == 0


class TestObserveSimilarity:
    """Tests for observe_similarity function."""

    def setup_method(self):
        """Clear memory before each test."""
        clear_generation_memory()

    def teardown_method(self):
        """Clear memory after each test."""
        clear_generation_memory()

    def test_first_story_no_comparison(self):
        """Test that first story has no comparison."""
        result = observe_similarity(
            current_summary="Test summary",
            current_title="Test Story",
            canonical_keys={}
        )

        assert result is None

    def test_observe_low_similarity(self):
        """Test observing low similarity."""
        add_to_generation_memory(
            story_id="test_001",
            template_id="T-001",
            title="Story A",
            semantic_summary="A story about cats in the garden",
            canonical_keys={}
        )

        result = observe_similarity(
            current_summary="Completely different topic about technology and computers",
            current_title="Story B",
            canonical_keys={}
        )

        assert result is not None
        # Similarity should be LOW due to no word overlap
        assert result["signal"] == "LOW"

    def test_observe_high_similarity(self):
        """Test observing high similarity."""
        add_to_generation_memory(
            story_id="test_001",
            template_id="T-001",
            title="Story A",
            semantic_summary="A story about cats and dogs in the park",
            canonical_keys={}
        )

        result = observe_similarity(
            current_summary="A story about cats and dogs in the park running",
            current_title="Story B",
            canonical_keys={}
        )

        assert result is not None
        # Should be HIGH (>=0.5) due to high word overlap
        assert result["signal"] in ["MEDIUM", "HIGH"]


class TestSimilaritySignal:
    """Tests for get_similarity_signal function."""

    def test_none_observation(self):
        """Test signal for None observation."""
        assert get_similarity_signal(None) == "LOW"

    def test_low_signal(self):
        """Test LOW signal extraction."""
        observation = {"signal": "LOW"}
        assert get_similarity_signal(observation) == "LOW"

    def test_medium_signal(self):
        """Test MEDIUM signal extraction."""
        observation = {"signal": "MEDIUM"}
        assert get_similarity_signal(observation) == "MEDIUM"

    def test_high_signal(self):
        """Test HIGH signal extraction."""
        observation = {"signal": "HIGH"}
        assert get_similarity_signal(observation) == "HIGH"


class TestShouldAcceptStory:
    """Tests for should_accept_story function."""

    def test_accept_low(self):
        """Test accepting LOW signal."""
        assert should_accept_story("LOW") is True

    def test_accept_medium(self):
        """Test accepting MEDIUM signal."""
        assert should_accept_story("MEDIUM") is True

    def test_reject_high(self):
        """Test rejecting HIGH signal."""
        assert should_accept_story("HIGH") is False
