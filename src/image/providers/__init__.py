"""
Image generation providers.

Each provider implements the ImageProvider interface for generating
thumbnail images from text prompts.
"""

from .base import ImageProvider, ImageResult
from .openai_dalle import DallEProvider
from .stability_ai import StabilityAIProvider
from .flux_replicate import FluxReplicateProvider
from .local_sd import LocalSDProvider

__all__ = [
    "ImageProvider",
    "ImageResult",
    "DallEProvider",
    "StabilityAIProvider",
    "FluxReplicateProvider",
    "LocalSDProvider",
]
