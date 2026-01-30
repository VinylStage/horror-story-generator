"""
Image generation module for story thumbnails.

This module provides automatic thumbnail generation for horror stories
using multiple image providers (OpenAI DALL-E 3, Stability AI, FLUX, Local SD).
"""

from .generator import generate_thumbnail, ThumbnailResult
from .config import is_image_generation_available, ENABLE_THUMBNAIL_GENERATION

__all__ = [
    "generate_thumbnail",
    "ThumbnailResult",
    "is_image_generation_available",
    "ENABLE_THUMBNAIL_GENERATION",
]
