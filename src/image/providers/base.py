"""
Base interface for image generation providers.

All image providers must implement the ImageProvider abstract class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ImageResult:
    """Result from an image generation attempt."""

    success: bool
    url: Optional[str]
    provider: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        if self.success:
            return f"ImageResult(success=True, provider='{self.provider}', url='{self.url[:50]}...')"
        return f"ImageResult(success=False, provider='{self.provider}', error='{self.error}')"


class ImageProvider(ABC):
    """
    Abstract base class for image generation providers.

    All providers must implement:
    - generate_image(): Generate image from text prompt
    - is_available(): Check if provider has required configuration
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name identifier."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available for use.

        Returns:
            bool: True if provider has necessary API keys/configuration.
        """
        pass

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        **kwargs
    ) -> ImageResult:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of desired image.
            width: Desired image width (may be adjusted by provider).
            height: Desired image height (may be adjusted by provider).
            **kwargs: Provider-specific options.

        Returns:
            ImageResult with success status and URL or error.

        Note:
            This method should never raise exceptions. All errors should
            be captured and returned in ImageResult.error.
        """
        pass
