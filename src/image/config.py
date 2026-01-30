"""
Configuration module for image generation.

Handles environment variables and feature flags for thumbnail generation.
"""

import os
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Feature Flags
# =============================================================================

ENABLE_THUMBNAIL_GENERATION = os.getenv(
    "ENABLE_THUMBNAIL_GENERATION", "false"
).lower() == "true"

# =============================================================================
# API Keys
# =============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STABILITY_AI_API_KEY = os.getenv("STABILITY_AI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# =============================================================================
# Local Stable Diffusion (ComfyUI)
# =============================================================================

LOCAL_SD_ENABLED = os.getenv("LOCAL_SD_ENABLED", "false").lower() == "true"
LOCAL_SD_HOST = os.getenv("LOCAL_SD_HOST", "localhost")
LOCAL_SD_PORT = int(os.getenv("LOCAL_SD_PORT", "8188"))

# =============================================================================
# Provider Selection
# =============================================================================

IMAGE_PRIMARY_PROVIDER = os.getenv("IMAGE_PRIMARY_PROVIDER", "openai_dalle3")
IMAGE_FALLBACK_PROVIDER = os.getenv("IMAGE_FALLBACK_PROVIDER", "stability_ai")

# Valid provider names
VALID_PROVIDERS = ["openai_dalle3", "stability_ai", "flux", "local_sd"]

# =============================================================================
# Generation Parameters
# =============================================================================

IMAGE_GENERATION_TIMEOUT = int(os.getenv("IMAGE_GENERATION_TIMEOUT", "30"))
IMAGE_MAX_RETRIES = int(os.getenv("IMAGE_MAX_RETRIES", "1"))

# OG Image standard size
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630


def is_image_generation_available() -> bool:
    """
    Check if image generation is enabled and at least one provider is configured.

    Returns:
        bool: True if generation is available, False otherwise.
    """
    if not ENABLE_THUMBNAIL_GENERATION:
        logger.debug("Thumbnail generation disabled via ENABLE_THUMBNAIL_GENERATION=false")
        return False

    # Check if any provider has API keys configured
    has_cloud_keys = bool(OPENAI_API_KEY or STABILITY_AI_API_KEY or REPLICATE_API_TOKEN)
    has_local = LOCAL_SD_ENABLED

    if not (has_cloud_keys or has_local):
        logger.info(
            "No image API keys configured. Set one of: "
            "OPENAI_API_KEY, STABILITY_AI_API_KEY, REPLICATE_API_TOKEN, or LOCAL_SD_ENABLED=true"
        )
        return False

    return True


def get_available_providers() -> list:
    """
    Get list of available providers based on configured API keys.

    Returns:
        list: List of available provider names.
    """
    available = []

    if OPENAI_API_KEY:
        available.append("openai_dalle3")
    if STABILITY_AI_API_KEY:
        available.append("stability_ai")
    if REPLICATE_API_TOKEN:
        available.append("flux")
    if LOCAL_SD_ENABLED:
        available.append("local_sd")

    return available


def validate_provider(provider: str) -> bool:
    """
    Check if a provider name is valid.

    Args:
        provider: Provider name to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    return provider in VALID_PROVIDERS
