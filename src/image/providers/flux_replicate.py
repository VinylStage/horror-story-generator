"""
FLUX image generation provider via Replicate API.

Uses Black Forest Labs' FLUX model through Replicate.
Cost: ~$0.003/image (schnell), ~$0.025/image (dev)
"""

import logging
import time
from typing import Optional

import httpx

from .base import ImageProvider, ImageResult
from ..config import REPLICATE_API_TOKEN, IMAGE_GENERATION_TIMEOUT

logger = logging.getLogger(__name__)


class FluxReplicateProvider(ImageProvider):
    """FLUX image generation via Replicate API."""

    API_URL = "https://api.replicate.com/v1/predictions"

    # FLUX model versions on Replicate
    MODELS = {
        "schnell": "black-forest-labs/flux-schnell",  # Fast, cheap (~$0.003)
        "dev": "black-forest-labs/flux-dev",  # Higher quality (~$0.025)
    }

    def __init__(
        self,
        api_token: Optional[str] = None,
        model_variant: str = "schnell"
    ):
        """
        Initialize FLUX Replicate provider.

        Args:
            api_token: Replicate API token. Uses REPLICATE_API_TOKEN env var if not provided.
            model_variant: "schnell" (fast) or "dev" (high quality).
        """
        self.api_token = api_token or REPLICATE_API_TOKEN
        self.model_variant = model_variant
        self.model = self.MODELS.get(model_variant, self.MODELS["schnell"])

    @property
    def name(self) -> str:
        return "flux"

    def is_available(self) -> bool:
        """Check if Replicate API token is configured."""
        return bool(self.api_token)

    def _wait_for_prediction(
        self,
        prediction_url: str,
        headers: dict,
        max_wait: int = 60
    ) -> dict:
        """
        Poll for prediction completion.

        Replicate predictions are async, so we need to poll for completion.

        Args:
            prediction_url: URL to check prediction status.
            headers: Auth headers for API.
            max_wait: Maximum seconds to wait.

        Returns:
            Completed prediction data or raises exception.
        """
        start_time = time.time()

        with httpx.Client(timeout=10) as client:
            while time.time() - start_time < max_wait:
                response = client.get(prediction_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                status = data.get("status")

                if status == "succeeded":
                    return data
                elif status == "failed":
                    raise Exception(f"Prediction failed: {data.get('error')}")
                elif status == "canceled":
                    raise Exception("Prediction was canceled")

                # Still processing, wait and retry
                time.sleep(1)

        raise Exception(f"Prediction timed out after {max_wait}s")

    def generate_image(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        num_inference_steps: int = 4,
        **kwargs
    ) -> ImageResult:
        """
        Generate image using FLUX via Replicate.

        Args:
            prompt: Text description of desired image.
            width: Image width (FLUX supports custom sizes).
            height: Image height.
            num_inference_steps: Number of denoising steps (default 4 for schnell).

        Returns:
            ImageResult with generated image URL.
        """
        if not self.is_available():
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error="REPLICATE_API_TOKEN not configured"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }

            # FLUX input parameters
            payload = {
                "version": self.model,
                "input": {
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": num_inference_steps,
                    "output_format": "png"
                }
            }

            logger.info(f"Calling FLUX ({self.model_variant}) via Replicate API")
            logger.debug(f"Prompt: {prompt[:100]}...")

            with httpx.Client(timeout=IMAGE_GENERATION_TIMEOUT) as client:
                # Create prediction
                response = client.post(self.API_URL, json=payload, headers=headers)
                response.raise_for_status()

                prediction = response.json()
                prediction_url = prediction.get("urls", {}).get("get")

                if not prediction_url:
                    # Some responses include the result directly
                    if prediction.get("status") == "succeeded":
                        output = prediction.get("output")
                        if output:
                            image_url = output[0] if isinstance(output, list) else output
                            return ImageResult(
                                success=True,
                                url=image_url,
                                provider=self.name,
                                metadata={
                                    "model": self.model,
                                    "variant": self.model_variant,
                                    "width": width,
                                    "height": height
                                }
                            )
                    return ImageResult(
                        success=False,
                        url=None,
                        provider=self.name,
                        error="No prediction URL in response"
                    )

                # Poll for completion
                completed = self._wait_for_prediction(
                    prediction_url,
                    headers,
                    max_wait=IMAGE_GENERATION_TIMEOUT
                )

                output = completed.get("output")
                if not output:
                    return ImageResult(
                        success=False,
                        url=None,
                        provider=self.name,
                        error="No output in completed prediction"
                    )

                # Output can be a URL or list of URLs
                image_url = output[0] if isinstance(output, list) else output

                logger.info("FLUX image generated successfully")

                return ImageResult(
                    success=True,
                    url=image_url,
                    provider=self.name,
                    metadata={
                        "model": self.model,
                        "variant": self.model_variant,
                        "width": width,
                        "height": height,
                        "prediction_id": completed.get("id")
                    }
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"Replicate API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail.get('detail', str(error_detail))}"
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
            error_msg = f"Replicate API timeout after {IMAGE_GENERATION_TIMEOUT}s"
            logger.error(error_msg)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"FLUX generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )
