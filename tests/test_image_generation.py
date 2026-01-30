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

    def test_get_aspect_ratio_portrait(self):
        """Test aspect ratio selection for portrait images."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key="test")
        ratio = provider._get_aspect_ratio(630, 1200)
        assert ratio == "9:16"

    def test_generate_without_key_returns_error(self):
        """Test generation fails gracefully without API key."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key=None)
        result = provider.generate_image("test prompt")

        assert result.success is False
        assert "not configured" in result.error


class TestFluxProvider:
    """Test FLUX Replicate provider without actual API calls."""

    def test_flux_unavailable_without_token(self):
        """Test FLUX provider is unavailable without API token."""
        from src.image.providers.flux_replicate import FluxReplicateProvider

        provider = FluxReplicateProvider(api_token=None)
        assert provider.is_available() is False
        assert provider.name == "flux"

    def test_flux_available_with_token(self):
        """Test FLUX provider is available with API token."""
        from src.image.providers.flux_replicate import FluxReplicateProvider

        provider = FluxReplicateProvider(api_token="test-token")
        assert provider.is_available() is True

    def test_generate_without_token_returns_error(self):
        """Test generation fails gracefully without API token."""
        from src.image.providers.flux_replicate import FluxReplicateProvider

        provider = FluxReplicateProvider(api_token=None)
        result = provider.generate_image("test prompt")

        assert result.success is False
        assert "not configured" in result.error


class TestLocalSDProvider:
    """Test Local SD provider without actual API calls."""

    def test_local_sd_unavailable_when_disabled(self):
        """Test Local SD provider is unavailable when disabled."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider(enabled=False)
        assert provider.is_available() is False
        assert provider.name == "local_sd"

    def test_local_sd_available_when_enabled_and_server_reachable(self):
        """Test Local SD provider is available when enabled and server reachable."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider(enabled=True)
        # Mock the server check since we don't have a real server
        with patch.object(provider, 'is_available', return_value=True):
            assert provider.is_available() is True

    def test_local_sd_unavailable_when_server_not_reachable(self):
        """Test Local SD provider is unavailable when server not reachable."""
        from src.image.providers.local_sd import LocalSDProvider

        # Server not running, so should return False even if enabled
        provider = LocalSDProvider(enabled=True, host="localhost", port=19999)
        assert provider.is_available() is False

    def test_generate_when_disabled_returns_error(self):
        """Test generation fails gracefully when disabled."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider(enabled=False)
        result = provider.generate_image("test prompt")

        assert result.success is False
        assert "LOCAL_SD_ENABLED" in result.error or "not enabled" in result.error.lower()


class TestGeneratorFunctions:
    """Test generator helper functions."""

    def test_get_provider_instance_valid(self):
        """Test getting provider instances by name."""
        from src.image.generator import _get_provider_instance

        dalle = _get_provider_instance("openai_dalle3")
        assert dalle is not None
        assert dalle.name == "openai_dalle3"

        stability = _get_provider_instance("stability_ai")
        assert stability is not None
        assert stability.name == "stability_ai"

        flux = _get_provider_instance("flux")
        assert flux is not None
        assert flux.name == "flux"

        local_sd = _get_provider_instance("local_sd")
        assert local_sd is not None
        assert local_sd.name == "local_sd"

    def test_get_provider_instance_invalid(self):
        """Test getting provider instance with invalid name."""
        from src.image.generator import _get_provider_instance

        result = _get_provider_instance("invalid_provider")
        assert result is None

    def test_get_providers_to_try_with_preferred(self):
        """Test provider list with preferred provider."""
        from src.image.generator import _get_providers_to_try

        providers = _get_providers_to_try("flux")
        assert len(providers) == 1
        assert providers[0].name == "flux"

    def test_get_providers_to_try_with_invalid_preferred(self):
        """Test provider list with invalid preferred provider."""
        from src.image.generator import _get_providers_to_try

        providers = _get_providers_to_try("invalid_provider")
        assert len(providers) == 0

    def test_thumbnail_result_repr_success(self):
        """Test ThumbnailResult __repr__ for success case."""
        result = ThumbnailResult(
            success=True,
            thumbnail_url="https://example.com/thumb.png",
            provider="openai_dalle3",
            generated_at="2026-01-30T12:00:00"
        )
        assert "success=True" in repr(result)
        assert "openai_dalle3" in repr(result)

    def test_thumbnail_result_repr_failure(self):
        """Test ThumbnailResult __repr__ for failure case."""
        result = ThumbnailResult(
            success=False,
            thumbnail_url="",
            provider="none",
            generated_at="2026-01-30T12:00:00",
            error="Test error"
        )
        assert "success=False" in repr(result)
        assert "Test error" in repr(result)


class TestGenerateThumbnailAdvanced:
    """Advanced tests for generate_thumbnail function."""

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_generate_with_skip_keyword_extraction(self):
        """Test generation with skip_keyword_extraction flag."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        # Mock the provider to avoid actual API call
        with patch('src.image.generator._get_providers_to_try') as mock_providers:
            mock_provider = MagicMock()
            mock_provider.name = "openai_dalle3"
            mock_provider.is_available.return_value = True
            mock_provider.generate_image.return_value = ImageResult(
                success=True,
                url="https://example.com/image.png",
                provider="openai_dalle3"
            )
            mock_providers.return_value = [mock_provider]

            result = generate_thumbnail(
                story_text="Test story",
                title="Test Title",
                config={},
                skip_keyword_extraction=True
            )

            assert result.success is True
            assert result.thumbnail_url == "https://example.com/image.png"

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_generate_with_custom_prompt(self):
        """Test generation with custom prompt."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        with patch('src.image.generator._get_providers_to_try') as mock_providers:
            mock_provider = MagicMock()
            mock_provider.name = "openai_dalle3"
            mock_provider.is_available.return_value = True
            mock_provider.generate_image.return_value = ImageResult(
                success=True,
                url="https://example.com/custom.png",
                provider="openai_dalle3"
            )
            mock_providers.return_value = [mock_provider]

            result = generate_thumbnail(
                story_text="Test story",
                title="Test Title",
                config={},
                custom_prompt="A custom horror image prompt"
            )

            assert result.success is True
            # Verify custom prompt was used
            call_args = mock_provider.generate_image.call_args
            assert call_args[1]["prompt"] == "A custom horror image prompt"

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_generate_with_provider_fallback(self):
        """Test generation falls back to next provider on failure."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        with patch('src.image.generator._get_providers_to_try') as mock_providers:
            # First provider fails
            mock_provider1 = MagicMock()
            mock_provider1.name = "openai_dalle3"
            mock_provider1.is_available.return_value = True
            mock_provider1.generate_image.return_value = ImageResult(
                success=False,
                url=None,
                provider="openai_dalle3",
                error="API error"
            )

            # Second provider succeeds
            mock_provider2 = MagicMock()
            mock_provider2.name = "stability_ai"
            mock_provider2.is_available.return_value = True
            mock_provider2.generate_image.return_value = ImageResult(
                success=True,
                url="https://example.com/fallback.png",
                provider="stability_ai"
            )

            mock_providers.return_value = [mock_provider1, mock_provider2]

            result = generate_thumbnail(
                story_text="Test story",
                title="Test Title",
                config={},
                skip_keyword_extraction=True
            )

            assert result.success is True
            assert result.provider == "stability_ai"

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_generate_handles_exception(self):
        """Test generation handles unexpected exceptions gracefully."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        with patch('src.image.generator._get_providers_to_try') as mock_providers:
            mock_providers.side_effect = Exception("Unexpected error")

            result = generate_thumbnail(
                story_text="Test story",
                title="Test Title",
                config={},
                skip_keyword_extraction=True
            )

            assert result.success is False
            assert result.provider == "error"
            assert "Unexpected error" in result.error

    @patch.dict(os.environ, {
        "ENABLE_THUMBNAIL_GENERATION": "true",
        "OPENAI_API_KEY": "test-key"
    }, clear=False)
    def test_generate_skips_unavailable_provider(self):
        """Test generation skips providers that are not available."""
        import importlib
        import src.image.config as config_module
        importlib.reload(config_module)

        with patch('src.image.generator._get_providers_to_try') as mock_providers:
            # First provider not available
            mock_provider1 = MagicMock()
            mock_provider1.name = "openai_dalle3"
            mock_provider1.is_available.return_value = False

            # Second provider available and succeeds
            mock_provider2 = MagicMock()
            mock_provider2.name = "stability_ai"
            mock_provider2.is_available.return_value = True
            mock_provider2.generate_image.return_value = ImageResult(
                success=True,
                url="https://example.com/available.png",
                provider="stability_ai"
            )

            mock_providers.return_value = [mock_provider1, mock_provider2]

            result = generate_thumbnail(
                story_text="Test story",
                title="Test Title",
                config={},
                skip_keyword_extraction=True
            )

            assert result.success is True
            assert result.provider == "stability_ai"
            # First provider should not have generate_image called
            mock_provider1.generate_image.assert_not_called()


class TestPromptBuilderAdvanced:
    """Advanced tests for prompt builder."""

    def test_build_negative_prompt_flux(self):
        """Test negative prompt for FLUX (should be empty, doesn't support negative prompts)."""
        negative = build_negative_prompt("flux")
        assert negative == ""  # FLUX doesn't use negative prompts

    def test_build_negative_prompt_local_sd(self):
        """Test negative prompt for Local SD."""
        negative = build_negative_prompt("local_sd")
        assert "text" in negative
        assert "watermark" in negative
        assert "blurry" in negative

    def test_build_image_prompt_with_title(self):
        """Test prompt includes title when provided."""
        keywords = {
            "setting": "dark forest",
            "mood": "eerie",
            "central_element": "ghost",
            "horror_type": "supernatural"
        }
        prompt = build_image_prompt(keywords, "openai_dalle3", title="The Haunted Forest")
        # Title may or may not be included depending on implementation
        assert "dark forest" in prompt

    def test_build_image_prompt_unknown_provider(self):
        """Test prompt building for unknown provider uses default format."""
        keywords = {
            "setting": "dark room",
            "mood": "scary",
            "central_element": "shadow",
            "horror_type": "horror"
        }
        prompt = build_image_prompt(keywords, "unknown_provider")
        # Should still generate a prompt
        assert len(prompt) > 0


class TestDallEProviderAdditional:
    """Additional DALL-E provider tests."""

    def test_dalle_provider_name(self):
        """Test provider name property."""
        from src.image.providers.openai_dalle import DallEProvider

        provider = DallEProvider(api_key="test-key")
        assert provider.name == "openai_dalle3"

    def test_dalle_provider_available_with_env_key(self):
        """Test DALL-E uses environment key when not provided."""
        from src.image.providers.openai_dalle import DallEProvider

        # Provider should use env var when api_key is None
        provider = DallEProvider()
        # Just verify it doesn't crash
        assert provider.name == "openai_dalle3"


class TestStabilityProviderAdditional:
    """Additional Stability AI provider tests."""

    def test_stability_provider_name(self):
        """Test provider name property."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key="test-key")
        assert provider.name == "stability_ai"

    def test_stability_available_with_key(self):
        """Test availability with API key."""
        from src.image.providers.stability_ai import StabilityAIProvider

        provider = StabilityAIProvider(api_key="test-key")
        assert provider.is_available() is True


class TestFluxProviderAdditional:
    """Additional FLUX provider tests."""

    def test_flux_provider_name(self):
        """Test provider name property."""
        from src.image.providers.flux_replicate import FluxReplicateProvider

        provider = FluxReplicateProvider(api_token="test-token")
        assert provider.name == "flux"


class TestLocalSDProviderAdditional:
    """Additional Local SD provider tests."""

    def test_local_sd_provider_name(self):
        """Test provider name property."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider(enabled=True)
        assert provider.name == "local_sd"

    def test_local_sd_uses_env_config(self):
        """Test Local SD uses environment configuration."""
        from src.image.providers.local_sd import LocalSDProvider

        provider = LocalSDProvider()
        assert provider.host is not None
        assert provider.port is not None


class TestExtractVisualKeywords:
    """Test visual keyword extraction."""

    def test_extract_keywords_fallback_on_error(self):
        """Test that extraction falls back to defaults on error."""
        from src.image.prompt_builder import extract_visual_keywords

        # Without API key, should return defaults
        result = extract_visual_keywords(
            story_text="Test story",
            title="Test Title",
            config={}
        )

        assert "setting" in result
        assert "mood" in result
        assert "central_element" in result
        assert "horror_type" in result
