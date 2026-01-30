"""
Unit tests for image generation module.

Tests configuration, providers, and graceful degradation without requiring API keys.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.image.config import (
    is_image_generation_available,
    get_available_providers,
    validate_provider,
    VALID_PROVIDERS,
)
from src.image.providers.base import ImageResult, ImageProvider
from src.image.prompt_builder import build_image_prompt, build_negative_prompt
from src.image.generator import generate_thumbnail, ThumbnailResult


class TestImageConfig:
    """Test configuration loading."""

    def test_valid_providers_list(self):
        """Test that VALID_PROVIDERS contains expected values."""
        assert "openai_dalle3" in VALID_PROVIDERS
        assert "stability_ai" in VALID_PROVIDERS
        assert "flux" in VALID_PROVIDERS
        assert "local_sd" in VALID_PROVIDERS
        assert len(VALID_PROVIDERS) == 4

    def test_validate_provider_valid(self):
        """Test validate_provider returns True for valid providers."""
        for provider in VALID_PROVIDERS:
            assert validate_provider(provider) is True

    def test_validate_provider_invalid(self):
        """Test validate_provider returns False for invalid providers."""
        assert validate_provider("invalid_provider") is False
        assert validate_provider("midjourney") is False
        assert validate_provider("") is False

    @patch.dict(os.environ, {"ENABLE_THUMBNAIL_GENERATION": "false"}, clear=False)
    def test_feature_disabled_by_default(self):
        """Test that generation is disabled when flag is false."""
        # Reload config module to pick up patched env
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        assert config_module.is_image_generation_available() is False

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_feature_enabled_with_api_key(self):
        """Test that generation is available when enabled with API key."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        assert config_module.is_image_generation_available() is True

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "",
        "STABILITY_AI_API_KEY": "",
        "REPLICATE_API_TOKEN": "",
        "LOCAL_SD_ENABLED": "false"
    }, clear=False)
    def test_feature_enabled_without_keys(self):
        """Test that generation is unavailable when enabled but no API keys."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        assert config_module.is_image_generation_available() is False


class TestImageResult:
    """Test ImageResult dataclass."""

    def test_success_result(self):
        """Test successful image result."""
        result = ImageResult(
            success=True,
            url="https://example.com/image.png",
            provider="openai_dalle3"
        )
        assert result.success is True
        assert result.url == "https://example.com/image.png"
        assert result.provider == "openai_dalle3"
        assert result.error is None
        assert result.metadata == {}

    def test_failure_result(self):
        """Test failed image result."""
        result = ImageResult(
            success=False,
            url=None,
            provider="stability_ai",
            error="API key not configured"
        )
        assert result.success is False
        assert result.url is None
        assert result.error == "API key not configured"

    def test_result_with_metadata(self):
        """Test image result with metadata."""
        result = ImageResult(
            success=True,
            url="https://example.com/image.png",
            provider="flux",
            metadata={"model": "flux-schnell", "width": 1024}
        )
        assert result.metadata["model"] == "flux-schnell"
        assert result.metadata["width"] == 1024


class TestPromptBuilder:
    """Test prompt building without API calls."""

    def test_build_dalle_prompt_format(self):
        """Test DALL-E prompt follows expected format."""
        keywords = {
            "setting": "dark apartment hallway",
            "mood": "unsettling, cold colors",
            "central_element": "shadow figure",
            "horror_type": "psychological horror"
        }
        prompt = build_image_prompt(keywords, "openai_dalle3")

        assert "Korean horror" in prompt
        assert "dark apartment hallway" in prompt
        assert "shadow figure" in prompt
        assert "No text" in prompt
        assert "no watermarks" in prompt

    def test_build_stability_prompt_format(self):
        """Test Stability AI prompt follows expected format."""
        keywords = {
            "setting": "hospital corridor",
            "mood": "cold, sterile atmosphere",
            "central_element": "bloody handprint",
            "horror_type": "body horror"
        }
        prompt = build_image_prompt(keywords, "stability_ai")

        assert "horror movie poster" in prompt
        assert "hospital corridor" in prompt
        assert "bloody handprint" in prompt

    def test_build_flux_prompt_format(self):
        """Test FLUX prompt follows expected format."""
        keywords = {
            "setting": "empty subway station",
            "mood": "eerie, fluorescent lighting",
            "central_element": "distorted reflection",
            "horror_type": "supernatural horror"
        }
        prompt = build_image_prompt(keywords, "flux")

        assert "Korean horror" in prompt
        assert "empty subway station" in prompt
        assert "distorted reflection" in prompt

    def test_build_local_sd_prompt_format(self):
        """Test Local SD prompt follows expected format."""
        keywords = {
            "setting": "old house attic",
            "mood": "dusty, dim lighting",
            "central_element": "antique mirror",
            "horror_type": "ghost story"
        }
        prompt = build_image_prompt(keywords, "local_sd")

        assert "masterpiece" in prompt
        assert "old house attic" in prompt
        assert "antique mirror" in prompt

    def test_build_negative_prompt_stability(self):
        """Test negative prompt for Stability AI."""
        negative = build_negative_prompt("stability_ai")
        assert "text" in negative
        assert "watermark" in negative
        assert "blurry" in negative

    def test_build_negative_prompt_dalle(self):
        """Test negative prompt for DALL-E (should be empty)."""
        negative = build_negative_prompt("openai_dalle3")
        assert negative == ""

    def test_default_keywords(self):
        """Test prompt building with default keywords."""
        keywords = {}  # Empty keywords
        prompt = build_image_prompt(keywords, "openai_dalle3")

        # Should use defaults
        assert "dark atmospheric space" in prompt
        assert "mysterious shadow" in prompt


class TestProviderAvailability:
    """Test provider availability checks."""

    def test_dalle_unavailable_without_key(self):
        """Test DALL-E provider is unavailable without API key."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key=None)
        assert provider.is_available() is False

    def test_dalle_available_with_key(self):
        """Test DALL-E provider is available with API key."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key="test-key")
        assert provider.is_available() is True
        assert provider.name == "openai_dalle3"

    def test_stability_unavailable_without_key(self):
        """Test Stability AI provider is unavailable without API key."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key=None)
        assert provider.is_available() is False

    def test_flux_unavailable_without_key(self):
        """Test FLUX provider is unavailable without API token."""
        from src.image.providers.flux_replicate import FluxReplicateProvider

        provider = FluxReplicateProvider(api_token=None)
        assert provider.is_available() is False

    def test_local_sd_unavailable_when_disabled(self):
        """Test Local SD provider is unavailable when disabled."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider(enabled=False)
        assert provider.is_available() is False


class TestGracefulDegradation:
    """Test graceful degradation when providers are unavailable."""

    @patch.dict(os.environ, {"ENABLE_THUMBNAIL_GENERATION": "false"}, clear=False)
    def test_disabled_returns_empty_url(self):
        """Test returns empty thumbnail when disabled."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        result = generate_thumbnail(
            story_text="Test horror story content",
            title="Test Title",
            config={}
        )

        assert result.success is False
        assert result.thumbnail_url == ""
        assert result.provider == "none"
        assert "disabled" in result.error.lower() or "no api" in result.error.lower()

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "",
        "STABILITY_AI_API_KEY": "",
        "REPLICATE_API_TOKEN": "",
        "LOCAL_SD_ENABLED": "false"
    }, clear=False)
    def test_no_providers_returns_empty_url(self):
        """Test returns empty thumbnail when no providers available."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        result = generate_thumbnail(
            story_text="Test horror story content",
            title="Test Title",
            config={}
        )

        assert result.success is False
        assert result.thumbnail_url == ""


class TestThumbnailResult:
    """Test ThumbnailResult dataclass."""

    def test_success_result(self):
        """Test successful thumbnail result."""
        result = ThumbnailResult(
            success=True,
            thumbnail_url="https://example.com/thumb.png",
            provider="openai_dalle3",
            generated_at="2026-01-30T12:00:00"
        )
        assert result.success is True
        assert result.thumbnail_url == "https://example.com/thumb.png"
        assert result.provider == "openai_dalle3"
        assert result.error is None

    def test_failure_result(self):
        """Test failed thumbnail result."""
        result = ThumbnailResult(
            success=False,
            thumbnail_url="",
            provider="none",
            generated_at="2026-01-30T12:00:00",
            error="All providers failed"
        )
        assert result.success is False
        assert result.thumbnail_url == ""
        assert result.error == "All providers failed"


class TestDallEProvider:
    """Test DALL-E provider without actual API calls."""

    def test_get_best_size_landscape(self):
        """Test size selection for landscape images."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key="test")
        size = provider._get_best_size(1200, 630)
        assert size == "1792x1024"  # Landscape

    def test_get_best_size_portrait(self):
        """Test size selection for portrait images."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key="test")
        size = provider._get_best_size(630, 1200)
        assert size == "1024x1792"  # Portrait

    def test_get_best_size_square(self):
        """Test size selection for square images."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key="test")
        size = provider._get_best_size(1024, 1024)
        assert size == "1024x1024"  # Square

    def test_generate_without_key_returns_error(self):
        """Test generation fails gracefully without API key."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key=None)
        result = provider.generate_image("test prompt")

        assert result.success is False
        assert "not configured" in result.error


class TestStabilityProvider:
    """Test Stability AI provider without actual API calls."""

    def test_get_aspect_ratio_landscape(self):
        """Test aspect ratio selection for landscape images."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key="test")
        ratio = provider._get_aspect_ratio(1200, 630)
        assert ratio == "16:9"

    def test_get_aspect_ratio_square(self):
        """Test aspect ratio selection for square images."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key="test")
        ratio = provider._get_aspect_ratio(1024, 1024)
        assert ratio == "1:1"

    def test_generate_without_key_returns_error(self):
        """Test generation fails gracefully without API key."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key=None)
        result = provider.generate_image("test prompt")

        assert result.success is False
        assert "not configured" in result.error
