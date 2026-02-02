"""
Main thumbnail generator orchestrator.

Coordinates visual keyword extraction, prompt building, and image generation
across multiple providers with fallback support.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from .config import (
    is_image_generation_available,
    get_available_providers,
    validate_provider,
    IMAGE_PRIMARY_PROVIDER,
    IMAGE_FALLBACK_PROVIDER,
    OG_IMAGE_WIDTH,
    OG_IMAGE_HEIGHT,
)
from .prompt_builder import extract_visual_keywords, build_image_prompt, build_negative_prompt
from .providers import (
    DallEProvider,
    StabilityAIProvider,
    FluxReplicateProvider,
    LocalSDProvider,
    ImageProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class ThumbnailResult:
    """Result from thumbnail generation attempt."""

    success: bool
    thumbnail_url: str
    provider: str
    generated_at: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        if self.success:
            return f"ThumbnailResult(success=True, provider='{self.provider}')"
        return f"ThumbnailResult(success=False, error='{self.error}')"


def _get_provider_instance(provider_name: str) -> Optional[ImageProvider]:
    """
    Get provider instance by name.

    Args:
        provider_name: Provider identifier.

    Returns:
        ImageProvider instance or None if unknown.
    """
    providers = {
        "openai_dalle3": DallEProvider,
        "stability_ai": StabilityAIProvider,
        "flux": FluxReplicateProvider,
        "local_sd": LocalSDProvider,
    }

    provider_class = providers.get(provider_name)
    if provider_class:
        return provider_class()
    return None


def _get_providers_to_try(
    preferred_provider: Optional[str] = None
) -> List[ImageProvider]:
    """
    Get ordered list of providers to try.

    Args:
        preferred_provider: User-specified provider (will be tried first).

    Returns:
        List of provider instances in order of preference.
    """
    providers_to_try = []

    # If user specified a provider, try only that one
    if preferred_provider:
        if validate_provider(preferred_provider):
            provider = _get_provider_instance(preferred_provider)
            if provider:
                providers_to_try.append(provider)
        else:
            logger.warning(f"Unknown provider: {preferred_provider}")

        return providers_to_try

    # Otherwise, use primary and fallback
    for provider_name in [IMAGE_PRIMARY_PROVIDER, IMAGE_FALLBACK_PROVIDER]:
        provider = _get_provider_instance(provider_name)
        if provider and provider not in providers_to_try:
            providers_to_try.append(provider)

    # Add any other available providers as additional fallbacks
    available = get_available_providers()
    for provider_name in available:
        provider = _get_provider_instance(provider_name)
        if provider and provider not in providers_to_try:
            providers_to_try.append(provider)

    return providers_to_try


def generate_thumbnail(
    story_text: str,
    title: str,
    config: dict,
    provider: Optional[str] = None,
    width: int = OG_IMAGE_WIDTH,
    height: int = OG_IMAGE_HEIGHT,
    skip_keyword_extraction: bool = False,
    custom_prompt: Optional[str] = None,
) -> ThumbnailResult:
    """
    Generate thumbnail image for a horror story.

    Args:
        story_text: Full story text.
        title: Story title.
        config: API configuration (for Claude API keyword extraction).
        provider: Specific provider to use. If None, uses primary/fallback.
        width: Desired image width (default OG standard 1200).
        height: Desired image height (default OG standard 630).
        skip_keyword_extraction: If True, use default keywords.
        custom_prompt: If provided, use this prompt instead of generating one.

    Returns:
        ThumbnailResult with URL on success, empty string on failure.

    Note:
        This function never raises exceptions. All errors are captured
        and returned in ThumbnailResult.error with graceful degradation.
    """
    timestamp = datetime.now().isoformat()
    start_time = time.time()

    logger.info("[Thumbnail] Starting thumbnail generation")
    logger.info(f"[Thumbnail] Title: {title[:50]}..." if len(title) > 50 else f"[Thumbnail] Title: {title}")

    # Check if generation is enabled and available
    if not is_image_generation_available():
        logger.info("[Thumbnail] Skipped (disabled or no API keys)")
        return ThumbnailResult(
            success=False,
            thumbnail_url="",
            provider="none",
            generated_at=timestamp,
            error="Generation disabled or no API keys configured"
        )

    try:
        # Step 1: Extract visual keywords (or use custom prompt)
        if custom_prompt:
            logger.info("[Thumbnail] Using custom prompt")
            keywords = {}
        elif skip_keyword_extraction:
            logger.info("[Thumbnail] Using default keywords (extraction skipped)")
            keywords = {
                "setting": "dark atmospheric space",
                "mood": "unsettling, dark tones, low light",
                "central_element": "mysterious shadow",
                "horror_type": "psychological horror"
            }
        else:
            logger.info("[Thumbnail] Extracting visual keywords...")
            keywords = extract_visual_keywords(story_text, title, config)
            logger.info(f"[Thumbnail] Keywords: {keywords}")

        # Step 2: Get providers to try
        providers_to_try = _get_providers_to_try(provider)

        if not providers_to_try:
            logger.warning("[Thumbnail] No providers available")
            return ThumbnailResult(
                success=False,
                thumbnail_url="",
                provider="none",
                generated_at=timestamp,
                error="No image providers configured"
            )

        available_names = [p.name for p in providers_to_try]
        logger.info(f"[Thumbnail] Available providers: {available_names}")

        # Step 3: Try each provider in order
        last_error = None

        for image_provider in providers_to_try:
            if not image_provider.is_available():
                logger.debug(f"[Thumbnail] {image_provider.name} not available (no API key)")
                continue

            # Build provider-specific prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = build_image_prompt(keywords, image_provider.name, title)

            logger.info(f"[Thumbnail] Using provider: {image_provider.name}")
            logger.info(f"[Thumbnail] Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"[Thumbnail] Prompt: {prompt}")

            provider_start = time.time()

            # Generate image
            result = image_provider.generate_image(
                prompt=prompt,
                width=width,
                height=height
            )

            elapsed = time.time() - provider_start

            if result.success:
                total_elapsed = time.time() - start_time
                logger.info(f"[Thumbnail] Generated successfully ({elapsed:.1f}s)")
                logger.info(f"[Thumbnail] URL: {result.url}")
                logger.info(f"[Thumbnail] Total time: {total_elapsed:.1f}s")
                return ThumbnailResult(
                    success=True,
                    thumbnail_url=result.url,
                    provider=result.provider,
                    generated_at=timestamp,
                    metadata={
                        "keywords": keywords,
                        "prompt": prompt[:500],  # Truncate for storage
                        "generation_time_seconds": round(elapsed, 1),
                        **result.metadata
                    }
                )
            else:
                last_error = result.error
                logger.warning(f"[Thumbnail] {image_provider.name} failed ({elapsed:.1f}s): {result.error}")

        # All providers failed
        total_elapsed = time.time() - start_time
        logger.warning(f"[Thumbnail] All providers failed (total: {total_elapsed:.1f}s)")
        return ThumbnailResult(
            success=False,
            thumbnail_url="",
            provider="none",
            generated_at=timestamp,
            error=last_error or "All providers failed"
        )

    except Exception as e:
        logger.error(f"Thumbnail generation failed with exception: {e}", exc_info=True)
        return ThumbnailResult(
            success=False,
            thumbnail_url="",
            provider="error",
            generated_at=timestamp,
            error=str(e)
        )
