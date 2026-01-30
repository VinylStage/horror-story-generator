"""
OpenAI DALL-E 3 image generation provider.

Uses the OpenAI Images API to generate high-quality images.
Cost: $0.04/image (standard), $0.08/image (HD)
"""

import logging
from typing import Optional

import httpx

from .base import ImageProvider, ImageResult
from ..config import OPENAI_API_KEY, IMAGE_GENERATION_TIMEOUT

logger = logging.getLogger(__name__)


class DallEProvider(ImageProvider):
    """OpenAI DALL-E 3 image generation provider."""

    API_URL = "https://api.openai.com/v1/images/generations"

    # DALL-E 3 supported sizes
    SUPPORTED_SIZES = ["1024x1024", "1792x1024", "1024x1792"]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DALL-E provider.

        Args:
            api_key: OpenAI API key. Uses OPENAI_API_KEY env var if not provided.
        """
        self.api_key = api_key or OPENAI_API_KEY

    @property
    def name(self) -> str:
        return "openai_dalle3"

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.api_key)

    def _get_best_size(self, width: int, height: int) -> str:
        """
        Get the closest supported DALL-E 3 size.

        DALL-E 3 only supports: 1024x1024, 1792x1024, 1024x1792
        For OG images (1200x630), we use 1792x1024 (landscape).

        Args:
            width: Requested width.
            height: Requested height.

        Returns:
            Supported size string.
        """
        aspect_ratio = width / height if height > 0 else 1

        if aspect_ratio > 1.5:
            # Landscape (OG images are ~1.9:1)
            return "1792x1024"
        elif aspect_ratio < 0.7:
            # Portrait
            return "1024x1792"
        else:
            # Square
            return "1024x1024"

    def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        quality: str = "standard",
        style: str = "vivid",
        **kwargs
    ) -> ImageResult:
        """
        Generate image using DALL-E 3.

        Args:
            prompt: Text description of desired image.
            width: Desired width (will be mapped to supported size).
            height: Desired height (will be mapped to supported size).
            quality: "standard" ($0.04) or "hd" ($0.08).
            style: "vivid" (hyper-real) or "natural" (less hyper-real).

        Returns:
            ImageResult with CDN URL (expires in 60 days).
        """
        if not self.is_available():
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error="OPENAI_API_KEY not configured"
            )

        dalle_size = self._get_best_size(width, height)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": dalle_size,
                "quality": quality,
                "style": style
            }

            logger.info(f"Calling DALL-E 3 API (size={dalle_size}, quality={quality})")
            logger.debug(f"Prompt: {prompt[:100]}...")

            with httpx.Client(timeout=IMAGE_GENERATION_TIMEOUT) as client:
                response = client.post(self.API_URL, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()
                image_url = data["data"][0]["url"]
                revised_prompt = data["data"][0].get("revised_prompt")

                logger.info(f"DALL-E 3 image generated successfully")

                return ImageResult(
                    success=True,
                    url=image_url,
                    provider=self.name,
                    metadata={
                        "model": "dall-e-3",
                        "size": dalle_size,
                        "quality": quality,
                        "style": style,
                        "revised_prompt": revised_prompt
                    }
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"DALL-E API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail.get('error', {}).get('message', str(error_detail))}"
            except Exception:
                error_msg += f" - {e.response.text[:200]}"

            logger.error(error_msg)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )

        except httpx.TimeoutException:
            error_msg = f"DALL-E API timeout after {IMAGE_GENERATION_TIMEOUT}s"
            logger.error(error_msg)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"DALL-E generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )
