"""
Ollama Resource Manager.

Phase B+: Manages Ollama model lifecycle for optimal resource usage.

Features:
- Auto-cleanup on server shutdown
- Idle timeout for model unloading (configurable)
- Track model usage and last activity time
- Async HTTP via httpx for better performance

Configuration:
- OLLAMA_IDLE_TIMEOUT_SECONDS: Time before unloading idle model (default: 300s = 5 minutes)
- Set to 0 to disable auto-unload
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    import json
    import urllib.request
    import urllib.error
    HTTPX_AVAILABLE = False

logger = logging.getLogger("horror_story_generator")

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Idle timeout in seconds (default 5 minutes)
# Set to 0 to disable auto-unload
OLLAMA_IDLE_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_IDLE_TIMEOUT_SECONDS", "300"))


class OllamaResourceManager:
    """
    Manages Ollama model resource lifecycle.

    Tracks model usage and automatically unloads models after idle timeout.
    Ensures clean shutdown when API server stops.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        idle_timeout: int = OLLAMA_IDLE_TIMEOUT_SECONDS
    ):
        """
        Initialize resource manager.

        Args:
            base_url: Ollama API base URL
            idle_timeout: Seconds before unloading idle model (0 to disable)
        """
        self.base_url = base_url
        self.idle_timeout = idle_timeout

        # Track loaded models and last activity
        self._active_models: dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the resource manager background task."""
        if self._running:
            return

        self._running = True

        if self.idle_timeout > 0:
            self._cleanup_task = asyncio.create_task(self._idle_cleanup_loop())
            logger.info(
                f"[OllamaResource] Started with idle timeout: {self.idle_timeout}s"
            )
        else:
            logger.info("[OllamaResource] Started (idle cleanup disabled)")

    async def stop(self) -> None:
        """Stop resource manager and cleanup all models."""
        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Unload all active models
        logger.info("[OllamaResource] Shutting down - unloading models...")
        await self._unload_all_models()
        logger.info("[OllamaResource] Shutdown complete")

    def mark_model_used(self, model: str) -> None:
        """
        Mark a model as actively used.

        Should be called when a model is used for inference.

        Args:
            model: Model name (e.g., "qwen3:30b")
        """
        self._active_models[model] = datetime.now()
        logger.debug(f"[OllamaResource] Model used: {model}")

    async def _idle_cleanup_loop(self) -> None:
        """Background loop to check for idle models and unload them."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                if not self._running:
                    break

                await self._check_and_unload_idle()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[OllamaResource] Cleanup loop error: {e}")

    async def _check_and_unload_idle(self) -> None:
        """Check for idle models and unload them."""
        if not self._active_models:
            return

        now = datetime.now()
        idle_threshold = timedelta(seconds=self.idle_timeout)

        models_to_unload = []
        for model, last_used in list(self._active_models.items()):
            if now - last_used > idle_threshold:
                models_to_unload.append(model)

        for model in models_to_unload:
            logger.info(f"[OllamaResource] Unloading idle model: {model}")
            if await self._unload_model(model):
                del self._active_models[model]

    async def _unload_all_models(self) -> None:
        """Unload all tracked models."""
        for model in list(self._active_models.keys()):
            await self._unload_model(model)
        self._active_models.clear()

    async def _unload_model(self, model: str) -> bool:
        """
        Unload a model from Ollama memory.

        Uses the Ollama API with keep_alive=0 to unload.

        Args:
            model: Model name to unload

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": "",
            "keep_alive": 0,  # This tells Ollama to unload the model
        }

        try:
            if HTTPX_AVAILABLE:
                # Use httpx for async HTTP (preferred)
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(url, json=payload)
                    result = response.status_code < 400
            else:
                # Fallback to urllib in thread pool
                import json as json_module

                def _do_request():
                    data = json_module.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            return True
                    except Exception:
                        return False

                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, _do_request)

            if result:
                logger.info(f"[OllamaResource] Unloaded model: {model}")
            else:
                logger.warning(f"[OllamaResource] Failed to unload: {model}")

            return result

        except Exception as e:
            logger.error(f"[OllamaResource] Unload error for {model}: {e}")
            return False

    def get_status(self) -> dict:
        """Get resource manager status."""
        return {
            "running": self._running,
            "idle_timeout_seconds": self.idle_timeout,
            "active_models": {
                model: last_used.isoformat()
                for model, last_used in self._active_models.items()
            },
            "model_count": len(self._active_models),
        }


# Global resource manager instance
_resource_manager: Optional[OllamaResourceManager] = None


def get_resource_manager() -> OllamaResourceManager:
    """
    Get or create global resource manager instance.

    Returns:
        OllamaResourceManager instance
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = OllamaResourceManager()
    return _resource_manager


async def startup_resource_manager() -> None:
    """Start the resource manager. Called on FastAPI startup."""
    manager = get_resource_manager()
    await manager.start()


async def shutdown_resource_manager() -> None:
    """Stop the resource manager. Called on FastAPI shutdown."""
    global _resource_manager
    if _resource_manager is not None:
        await _resource_manager.stop()
        _resource_manager = None
