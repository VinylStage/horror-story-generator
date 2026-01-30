"""
Stability AI image generation provider.

Uses Stability AI's SD 3.5 model for image generation.
Cost: ~$0.035/image
"""

import logging
from typing import Optional

import httpx

from .base import ImageProvider, ImageResult
from ..config import STABILITY_AI_API_KEY, IMAGE_GENERATION_TIMEOUT

logger = logging.getLogger(__name__)


class StabilityAIProvider(ImageProvider):
    """Stability AI SD 3.5 image generation provider."""

    API_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

    # Supported aspect ratios
    ASPECT_RATIOS = ["16:9", "1:1", "21:9", "2:3", "3:2", "4:5", "5:4", "9:16", "9:21"]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stability AI provider.

        Args:
            api_key: Stability AI API key. Uses STABILITY_AI_API_KEY env var if not provided.
        """
        self.api_key = api_key or STABILITY_AI_API_KEY

    @property
    def name(self) -> str:
        return "stability_ai"

    def is_available(self) -> bool:
        """Check if Stability AI API key is configured."""
        return bool(self.api_key)

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """
        Get the closest supported aspect ratio.

        Args:
            width: Requested width.
            height: Requested height.

        Returns:
            Supported aspect ratio string.
        """
        if height == 0:
            return "16:9"

        ratio = width / height

        # Map to closest supported ratio
        if ratio >= 2.0:
            return "21:9"
        elif ratio >= 1.6:
            return "16:9"  # Best for OG images (1200x630 = 1.9:1)
        elif ratio >= 1.4:
            return "3:2"
        elif ratio >= 1.1:
            return "5:4"
        elif ratio >= 0.9:
            return "1:1"
        elif ratio >= 0.75:
            return "4:5"
        elif ratio >= 0.6:
            return "2:3"
        elif ratio >= 0.5:
            return "9:16"
        else:
            return "9:21"

    def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        model: str = "sd3.5-medium",
        negative_prompt: Optional[str] = None,
        **kwargs
    ) -> ImageResult:
        """
        Generate image using Stability AI SD 3.5.

        Args:
            prompt: Text description of desired image.
            width: Desired width (used to calculate aspect ratio).
            height: Desired height (used to calculate aspect ratio).
            model: Model to use ("sd3.5-medium" or "sd3.5-large").
            negative_prompt: Things to avoid in the image.

        Returns:
            ImageResult with image URL.
        """
        if not self.is_available():
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error="STABILITY_AI_API_KEY not configured"
            )

        aspect_ratio = self._get_aspect_ratio(width, height)

        # Default negative prompt for horror images
        if negative_prompt is None:
            negative_prompt = (
                "text, words, letters, watermark, logo, signature, "
                "blurry, low quality, distorted, deformed"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }

            # Stability AI uses multipart form data
            data = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "aspect_ratio": aspect_ratio,
                "model": model,
                "output_format": "png"
            }

            logger.info(f"Calling Stability AI API (model={model}, aspect_ratio={aspect_ratio})")
            logger.debug(f"Prompt: {prompt[:100]}...")

            with httpx.Client(timeout=IMAGE_GENERATION_TIMEOUT) as client:
                response = client.post(
                    self.API_URL,
                    headers=headers,
                    data=data
                )
                response.raise_for_status()

                result = response.json()

                # Stability AI returns base64 or URL depending on configuration
                image_url = result.get("image")
                if not image_url and "artifacts" in result:
                    # Some API versions return artifacts array
                    artifacts = result.get("artifacts", [])
                    if artifacts:
                        image_url = artifacts[0].get("url") or artifacts[0].get("base64")

                if not image_url:
                    return ImageResult(
                        success=False,
                        url=None,
                        provider=self.name,
                        error="No image URL in response"
                    )

                logger.info("Stability AI image generated successfully")

                return ImageResult(
                    success=True,
                    url=image_url,
                    provider=self.name,
                    metadata={
                        "model": model,
                        "aspect_ratio": aspect_ratio,
                        "seed": result.get("seed")
                    }
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"Stability AI API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail.get('message', str(error_detail))}"
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
            error_msg = f"Stability AI API timeout after {IMAGE_GENERATION_TIMEOUT}s"
            logger.error(error_msg)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"Stability AI generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )
