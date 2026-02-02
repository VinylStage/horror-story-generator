"""
Local Stable Diffusion image generation provider.

Uses ComfyUI API for local image generation.
Cost: Free (requires local GPU)
"""

import logging
import time
import uuid
import json
from http.client import HTTPConnection
from typing import Optional

from .base import ImageProvider, ImageResult
from ..config import LOCAL_SD_ENABLED, LOCAL_SD_HOST, LOCAL_SD_PORT, IMAGE_GENERATION_TIMEOUT

logger = logging.getLogger(__name__)


class LocalSDProvider(ImageProvider):
    """Local Stable Diffusion via ComfyUI API."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        enabled: Optional[bool] = None
    ):
        """
        Initialize Local SD provider.

        Args:
            host: ComfyUI host. Uses LOCAL_SD_HOST env var if not provided.
            port: ComfyUI port. Uses LOCAL_SD_PORT env var if not provided.
            enabled: Whether local SD is enabled. Uses LOCAL_SD_ENABLED env var if not provided.
        """
        self.host = host or LOCAL_SD_HOST
        self.port = port or LOCAL_SD_PORT
        self.enabled = enabled if enabled is not None else LOCAL_SD_ENABLED

    @property
    def name(self) -> str:
        return "local_sd"

    def is_available(self) -> bool:
        """
        Check if local SD is enabled and ComfyUI server is reachable.

        Returns:
            bool: True if enabled and server responds.
        """
        if not self.enabled:
            return False

        try:
            conn = HTTPConnection(self.host, self.port, timeout=5)
            conn.request("GET", "/system_stats")
            response = conn.getresponse()
            conn.close()
            return response.status == 200
        except Exception as e:
            logger.debug(f"ComfyUI server not reachable: {e}")
            return False

    def _get_workflow(self, prompt: str, width: int, height: int) -> dict:
        """
        Generate ComfyUI workflow JSON for image generation.

        This is a basic txt2img workflow. Can be customized for specific models.

        Args:
            prompt: Text prompt for image generation.
            width: Image width.
            height: Image height.

        Returns:
            ComfyUI workflow dict.
        """
        # Basic SDXL workflow
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": int(uuid.uuid4().int % (2**32)),
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sd_xl_base_1.0.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": height,
                    "width": width
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": prompt
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "text, words, blurry, low quality, watermark"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "horror_thumbnail",
                    "images": ["8", 0]
                }
            }
        }

    def _queue_prompt(self, workflow: dict) -> str:
        """
        Queue a prompt in ComfyUI.

        Args:
            workflow: ComfyUI workflow dict.

        Returns:
            Prompt ID for tracking.
        """
        prompt_id = str(uuid.uuid4())

        conn = HTTPConnection(self.host, self.port, timeout=IMAGE_GENERATION_TIMEOUT)
        conn.request(
            "POST",
            "/prompt",
            body=json.dumps({"prompt": workflow, "client_id": prompt_id}),
            headers={"Content-Type": "application/json"}
        )
        response = conn.getresponse()
        result = json.loads(response.read().decode())
        conn.close()

        return result.get("prompt_id", prompt_id)

    def _wait_for_completion(self, prompt_id: str, max_wait: int = 60) -> dict:
        """
        Wait for prompt to complete.

        Args:
            prompt_id: Prompt ID to wait for.
            max_wait: Maximum seconds to wait.

        Returns:
            History data for completed prompt.
        """
        start_time = time.time()
        last_log_time = 0

        logger.info(f"[LocalSD] Waiting for completion (timeout: {max_wait}s)...")

        while time.time() - start_time < max_wait:
            elapsed = int(time.time() - start_time)

            # Log progress every 10 seconds
            if elapsed > 0 and elapsed % 10 == 0 and elapsed != last_log_time:
                logger.info(f"[LocalSD] Processing... {elapsed}s elapsed")
                last_log_time = elapsed

            conn = HTTPConnection(self.host, self.port, timeout=10)
            conn.request("GET", f"/history/{prompt_id}")
            response = conn.getresponse()

            if response.status == 200:
                history = json.loads(response.read().decode())
                conn.close()

                if prompt_id in history:
                    elapsed = int(time.time() - start_time)
                    logger.info(f"[LocalSD] Completed in {elapsed}s")
                    return history[prompt_id]
            else:
                conn.close()

            time.sleep(1)

        raise Exception(f"Prompt timed out after {max_wait}s")

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 576,
        **kwargs
    ) -> ImageResult:
        """
        Generate image using local Stable Diffusion via ComfyUI.

        Args:
            prompt: Text description of desired image.
            width: Image width (default 1024 for SDXL).
            height: Image height (default 576 for 16:9 aspect).

        Returns:
            ImageResult with local file path or error.
        """
        if not self.enabled:
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error="LOCAL_SD_ENABLED is false"
            )

        if not self.is_available():
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=f"ComfyUI server not reachable at {self.host}:{self.port}"
            )

        try:
            logger.info(f"[LocalSD] Server: {self.host}:{self.port}")
            logger.info(f"[LocalSD] Resolution: {width}x{height}")

            # Generate and queue workflow
            workflow = self._get_workflow(prompt, width, height)
            prompt_id = self._queue_prompt(workflow)
            logger.info(f"[LocalSD] Queued prompt: {prompt_id}")

            # Wait for completion
            history = self._wait_for_completion(prompt_id, IMAGE_GENERATION_TIMEOUT)

            # Extract output image path
            outputs = history.get("outputs", {})
            for node_id, output in outputs.items():
                if "images" in output:
                    images = output["images"]
                    if images:
                        # ComfyUI stores images in output directory
                        image_info = images[0]
                        filename = image_info.get("filename")
                        subfolder = image_info.get("subfolder", "")

                        # Construct URL to access image via ComfyUI
                        if subfolder:
                            image_url = f"http://{self.host}:{self.port}/view?filename={filename}&subfolder={subfolder}"
                        else:
                            image_url = f"http://{self.host}:{self.port}/view?filename={filename}"

                        logger.info(f"[LocalSD] Generated: {filename}")

                        return ImageResult(
                            success=True,
                            url=image_url,
                            provider=self.name,
                            metadata={
                                "filename": filename,
                                "subfolder": subfolder,
                                "width": width,
                                "height": height,
                                "prompt_id": prompt_id
                            }
                        )

            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error="No output images found in ComfyUI response"
            )

        except Exception as e:
            error_msg = f"Local SD generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ImageResult(
                success=False,
                url=None,
                provider=self.name,
                error=error_msg
            )
