"""Tests for model_provider module."""

import json
import os
import pytest
import socket
from http.client import HTTPException
from unittest.mock import patch, MagicMock

from src.story.model_provider import (
    ModelInfo,
    GenerationResult,
    parse_model_spec,
    get_provider,
    get_model_info,
    ClaudeProvider,
    OllamaProvider,
)


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_model_info_creation(self):
        """Test creating a ModelInfo instance."""
        info = ModelInfo(
            provider="anthropic",
            model_name="claude-sonnet-4-5-20250929",
            full_spec="claude-sonnet-4-5-20250929"
        )
        assert info.provider == "anthropic"
        assert info.model_name == "claude-sonnet-4-5-20250929"


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_generation_result_creation(self):
        """Test creating a GenerationResult instance."""
        result = GenerationResult(
            text="Generated text",
            usage={"input_tokens": 100, "output_tokens": 50},
            provider="anthropic",
            model="claude-sonnet-4-5-20250929"
        )
        assert result.text == "Generated text"
        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 50


class TestParseModelSpec:
    """Tests for parse_model_spec function."""

    def test_parse_none_returns_default_claude(self):
        """Test that None returns default Claude model."""
        with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-test-model"}, clear=False):
            info = parse_model_spec(None)
            assert info.provider == "anthropic"
            assert info.model_name == "claude-test-model"

    def test_parse_none_without_env_uses_default(self):
        """Test that None without env var uses hardcoded default."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove CLAUDE_MODEL if it exists
            os.environ.pop("CLAUDE_MODEL", None)
            info = parse_model_spec(None)
            assert info.provider == "anthropic"
            assert info.model_name == "claude-sonnet-4-5-20250929"

    def test_parse_ollama_spec(self):
        """Test parsing ollama model spec."""
        info = parse_model_spec("ollama:llama3")
        assert info.provider == "ollama"
        assert info.model_name == "llama3"
        assert info.full_spec == "ollama:llama3"

    def test_parse_ollama_with_complex_name(self):
        """Test parsing ollama with complex model name."""
        info = parse_model_spec("ollama:qwen2:7b-instruct")
        assert info.provider == "ollama"
        assert info.model_name == "qwen2:7b-instruct"

    def test_parse_claude_model_direct(self):
        """Test parsing direct Claude model name."""
        info = parse_model_spec("claude-sonnet-4-5-20250929")
        assert info.provider == "anthropic"
        assert info.model_name == "claude-sonnet-4-5-20250929"


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_ollama_provider(self):
        """Test getting an Ollama provider."""
        provider = get_provider("ollama:llama3")
        assert isinstance(provider, OllamaProvider)
        assert provider.model_name == "llama3"

    def test_get_claude_provider(self):
        """Test getting a Claude provider."""
        provider = get_provider("claude-sonnet-4-5-20250929")
        assert isinstance(provider, ClaudeProvider)
        assert provider.model_name == "claude-sonnet-4-5-20250929"

    def test_get_default_provider(self):
        """Test getting default provider (Claude)."""
        provider = get_provider(None)
        assert isinstance(provider, ClaudeProvider)


class TestGetModelInfo:
    """Tests for get_model_info function."""

    def test_get_model_info_ollama(self):
        """Test getting model info for Ollama."""
        info = get_model_info("ollama:mistral")
        assert info.provider == "ollama"
        assert info.model_name == "mistral"

    def test_get_model_info_claude(self):
        """Test getting model info for Claude."""
        info = get_model_info("claude-opus")
        assert info.provider == "anthropic"
        assert info.model_name == "claude-opus"


class TestClaudeProvider:
    """Tests for ClaudeProvider class."""

    def test_provider_name(self):
        """Test provider_name property."""
        provider = ClaudeProvider("claude-test")
        assert provider.provider_name == "anthropic"

    def test_generate_success(self):
        """Test successful generation."""
        provider = ClaudeProvider("claude-test")

        # Mock the anthropic module
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Generated horror story")]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=500)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.generate(
                system_prompt="You are a horror writer",
                user_prompt="Write a scary story",
                config={"api_key": "test-key", "max_tokens": 1000, "temperature": 0.7}
            )

        assert result.text == "Generated horror story"
        assert result.provider == "anthropic"
        assert result.usage is not None
        assert result.usage["input_tokens"] == 100

    def test_generate_without_usage(self):
        """Test generation when usage is not available."""
        provider = ClaudeProvider("claude-test")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Story text")]
        mock_message.usage = None

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.generate(
                system_prompt="System",
                user_prompt="User",
                config={"api_key": "test-key"}
            )

        assert result.text == "Story text"
        assert result.usage is None

    def test_generate_raises_on_error(self):
        """Test that generation raises exception on error."""
        provider = ClaudeProvider("claude-test")

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")

        with patch("anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(Exception, match="API Error"):
                provider.generate(
                    system_prompt="System",
                    user_prompt="User",
                    config={"api_key": "test-key"}
                )


class TestOllamaProvider:
    """Tests for OllamaProvider class."""

    def test_init_default_host_port(self):
        """Test initialization with default host and port."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_HOST", None)
            os.environ.pop("OLLAMA_PORT", None)
            provider = OllamaProvider("llama3")
            assert provider.host == "localhost"
            assert provider.port == 11434

    def test_init_custom_host_port(self):
        """Test initialization with custom host and port."""
        with patch.dict(os.environ, {"OLLAMA_HOST": "192.168.1.100", "OLLAMA_PORT": "8080"}):
            provider = OllamaProvider("llama3")
            assert provider.host == "192.168.1.100"
            assert provider.port == 8080

    def test_provider_name(self):
        """Test provider_name property."""
        provider = OllamaProvider("llama3")
        assert provider.provider_name == "ollama"

    def test_generate_success(self):
        """Test successful generation with Ollama."""
        provider = OllamaProvider("llama3")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "A scary tale",
            "prompt_eval_count": 50,
            "eval_count": 200
        }).encode("utf-8")

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            result = provider.generate(
                system_prompt="Horror writer",
                user_prompt="Write story",
                config={"max_tokens": 1000, "temperature": 0.8}
            )

        assert result.text == "A scary tale"
        assert result.provider == "ollama"
        assert result.usage is not None
        assert result.usage["output_tokens"] == 200

    def test_generate_without_eval_count(self):
        """Test generation when eval_count is not in response."""
        provider = OllamaProvider("llama3")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "Story without metrics"
        }).encode("utf-8")

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            result = provider.generate(
                system_prompt="System",
                user_prompt="User",
                config={}
            )

        assert result.text == "Story without metrics"
        assert result.usage is None

    def test_generate_ollama_error(self):
        """Test handling of Ollama error response."""
        provider = OllamaProvider("llama3")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "error": "Model not found"
        }).encode("utf-8")

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            with pytest.raises(Exception, match="Ollama error"):
                provider.generate(
                    system_prompt="System",
                    user_prompt="User",
                    config={}
                )

    def test_generate_timeout(self):
        """Test handling of socket timeout."""
        provider = OllamaProvider("llama3")

        mock_conn = MagicMock()
        mock_conn.request.side_effect = socket.timeout("Connection timed out")

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            with pytest.raises(Exception, match="timeout"):
                provider.generate(
                    system_prompt="System",
                    user_prompt="User",
                    config={"timeout": 10}
                )

    def test_generate_connection_error(self):
        """Test handling of connection error."""
        provider = OllamaProvider("llama3")

        mock_conn = MagicMock()
        mock_conn.request.side_effect = socket.error("Connection refused")

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            with pytest.raises(Exception, match="connection failed"):
                provider.generate(
                    system_prompt="System",
                    user_prompt="User",
                    config={}
                )

    def test_generate_http_exception(self):
        """Test handling of HTTP exception."""
        provider = OllamaProvider("llama3")

        mock_conn = MagicMock()
        mock_conn.request.side_effect = HTTPException("HTTP error")

        with patch("src.story.model_provider.HTTPConnection", return_value=mock_conn):
            with pytest.raises(Exception, match="connection failed"):
                provider.generate(
                    system_prompt="System",
                    user_prompt="User",
                    config={}
                )
