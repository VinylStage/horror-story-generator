"""
Tests for api_client module.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from api_client import call_claude_api, generate_semantic_summary


class TestCallClaudeApi:
    """Tests for call_claude_api function."""

    def test_successful_api_call(self):
        """Test successful API call."""
        mock_message = Mock()
        mock_message.content = [Mock(text="Generated story text")]
        mock_message.usage = Mock(input_tokens=100, output_tokens=500)

        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_message
            mock_anthropic.return_value = mock_client

            config = {
                "api_key": "test-key",
                "model": "claude-test",
                "max_tokens": 8192,
                "temperature": 0.8
            }

            result = call_claude_api(
                system_prompt="System prompt",
                user_prompt="User prompt",
                config=config
            )

            assert result["story_text"] == "Generated story text"
            assert result["usage"]["input_tokens"] == 100
            assert result["usage"]["output_tokens"] == 500
            assert result["usage"]["total_tokens"] == 600

    def test_api_call_without_usage(self):
        """Test API call when usage info is missing."""
        mock_message = Mock()
        mock_message.content = [Mock(text="Generated story text")]
        mock_message.usage = None

        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_message
            mock_anthropic.return_value = mock_client

            config = {
                "api_key": "test-key",
                "model": "claude-test",
                "max_tokens": 8192,
                "temperature": 0.8
            }

            result = call_claude_api(
                system_prompt="System prompt",
                user_prompt="User prompt",
                config=config
            )

            assert result["story_text"] == "Generated story text"
            assert result["usage"] is None

    def test_api_call_error(self):
        """Test API call error handling."""
        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.return_value = mock_client

            config = {
                "api_key": "test-key",
                "model": "claude-test",
                "max_tokens": 8192,
                "temperature": 0.8
            }

            with pytest.raises(Exception) as exc_info:
                call_claude_api(
                    system_prompt="System prompt",
                    user_prompt="User prompt",
                    config=config
                )

            assert "API Error" in str(exc_info.value)


class TestGenerateSemanticSummary:
    """Tests for generate_semantic_summary function."""

    def test_successful_summary_generation(self):
        """Test successful summary generation."""
        mock_message = Mock()
        mock_message.content = [Mock(text="This is a summary of the story.")]

        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_message
            mock_anthropic.return_value = mock_client

            config = {"api_key": "test-key", "model": "claude-test"}

            result = generate_semantic_summary(
                story_text="Long story text here...",
                title="Test Story",
                config=config
            )

            assert result == "This is a summary of the story."

    def test_summary_fallback_on_error(self):
        """Test fallback to story snippet on error."""
        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.return_value = mock_client

            config = {"api_key": "test-key", "model": "claude-test"}

            story_text = "This is the beginning of the story that should be used as fallback."
            result = generate_semantic_summary(
                story_text=story_text,
                title="Test Story",
                config=config
            )

            # Should return first 200 chars of story as fallback
            assert len(result) <= 200
            assert result == story_text[:200].strip()

    def test_summary_api_call_parameters(self):
        """Test that summary generation uses correct API parameters."""
        mock_message = Mock()
        mock_message.content = [Mock(text="Summary")]

        with patch("api_client.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_message
            mock_anthropic.return_value = mock_client

            config = {"api_key": "test-key", "model": "claude-test"}

            generate_semantic_summary(
                story_text="Story text",
                title="Test Story",
                config=config
            )

            # Verify API was called with correct parameters
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["model"] == "claude-test"
            assert call_args.kwargs["max_tokens"] == 200
            assert call_args.kwargs["temperature"] == 0.0  # Deterministic
