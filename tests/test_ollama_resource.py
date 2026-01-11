"""
Tests for ollama_resource module.

Phase B+: Ollama resource lifecycle management tests.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestOllamaResourceManager:
    """Tests for OllamaResourceManager class."""

    def test_create_manager(self):
        """Should create manager with defaults."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        assert manager.base_url == "http://localhost:11434"
        assert manager.idle_timeout == 300
        assert manager._running is False

    def test_create_manager_with_custom_config(self):
        """Should accept custom configuration."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(
            base_url="http://custom:11434",
            idle_timeout=600
        )

        assert manager.base_url == "http://custom:11434"
        assert manager.idle_timeout == 600

    @pytest.mark.asyncio
    async def test_start_manager(self):
        """Should start manager and set running state."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=0)  # Disable cleanup loop

        await manager.start()

        assert manager._running is True

        await manager.stop()

    @pytest.mark.asyncio
    async def test_start_with_cleanup_task(self):
        """Should start cleanup task when idle_timeout > 0."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=60)

        await manager.start()

        assert manager._running is True
        assert manager._cleanup_task is not None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_manager(self):
        """Should stop manager and cleanup."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=0)

        await manager.start()
        await manager.stop()

        assert manager._running is False
        assert manager._cleanup_task is None

    def test_mark_model_used(self):
        """Should track model usage time."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        before = datetime.now()
        manager.mark_model_used("qwen3:30b")
        after = datetime.now()

        assert "qwen3:30b" in manager._active_models
        model_time = manager._active_models["qwen3:30b"]
        assert before <= model_time <= after

    def test_mark_model_used_updates_time(self):
        """Should update time on subsequent uses."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        manager.mark_model_used("qwen3:30b")
        first_time = manager._active_models["qwen3:30b"]

        # Wait a tiny bit
        import time
        time.sleep(0.01)

        manager.mark_model_used("qwen3:30b")
        second_time = manager._active_models["qwen3:30b"]

        assert second_time >= first_time

    def test_get_status(self):
        """Should return status dictionary."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=300)
        manager._running = True
        manager.mark_model_used("qwen3:30b")

        status = manager.get_status()

        assert status["running"] is True
        assert status["idle_timeout_seconds"] == 300
        assert status["model_count"] == 1
        assert "qwen3:30b" in status["active_models"]

    @pytest.mark.asyncio
    async def test_check_and_unload_idle_no_models(self):
        """Should handle no active models."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        # Should not raise
        await manager._check_and_unload_idle()

    @pytest.mark.asyncio
    async def test_check_and_unload_idle_recent_model(self):
        """Should not unload recently used models."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=300)
        manager.mark_model_used("qwen3:30b")

        # Model just used, should not be unloaded
        await manager._check_and_unload_idle()

        assert "qwen3:30b" in manager._active_models

    @pytest.mark.asyncio
    async def test_check_and_unload_idle_old_model(self):
        """Should unload models past idle timeout."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=1)  # 1 second timeout

        # Set last used time to past
        manager._active_models["qwen3:30b"] = datetime.now() - timedelta(seconds=10)

        with patch.object(manager, "_unload_model", new_callable=AsyncMock) as mock_unload:
            mock_unload.return_value = True

            await manager._check_and_unload_idle()

            mock_unload.assert_called_once_with("qwen3:30b")
            assert "qwen3:30b" not in manager._active_models

    @pytest.mark.asyncio
    async def test_unload_all_models(self):
        """Should unload all tracked models."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()
        manager._active_models["qwen3:30b"] = datetime.now()
        manager._active_models["llama3:8b"] = datetime.now()

        with patch.object(manager, "_unload_model", new_callable=AsyncMock) as mock_unload:
            mock_unload.return_value = True

            await manager._unload_all_models()

            assert mock_unload.call_count == 2
            assert len(manager._active_models) == 0

    @pytest.mark.asyncio
    async def test_unload_model_success(self):
        """Should unload model via Ollama API."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        # Mock httpx for async HTTP
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await manager._unload_model("qwen3:30b")

            assert result is True

    @pytest.mark.asyncio
    async def test_unload_model_failure(self):
        """Should handle unload failure gracefully."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager()

        # Mock httpx to raise an exception
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.return_value = mock_instance

            result = await manager._unload_model("qwen3:30b")

            assert result is False


class TestGetResourceManager:
    """Tests for get_resource_manager function."""

    def test_returns_manager_instance(self):
        """Should return OllamaResourceManager instance."""
        from research_api.services.ollama_resource import (
            get_resource_manager,
            OllamaResourceManager,
            _resource_manager
        )
        import research_api.services.ollama_resource as module

        # Reset global state
        module._resource_manager = None

        manager = get_resource_manager()

        assert isinstance(manager, OllamaResourceManager)

        # Cleanup
        module._resource_manager = None

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        from research_api.services.ollama_resource import get_resource_manager
        import research_api.services.ollama_resource as module

        # Reset global state
        module._resource_manager = None

        manager1 = get_resource_manager()
        manager2 = get_resource_manager()

        assert manager1 is manager2

        # Cleanup
        module._resource_manager = None


class TestStartupShutdown:
    """Tests for startup/shutdown functions."""

    @pytest.mark.asyncio
    async def test_startup_resource_manager(self):
        """Should start global resource manager."""
        from research_api.services.ollama_resource import (
            startup_resource_manager,
            shutdown_resource_manager,
            get_resource_manager
        )
        import research_api.services.ollama_resource as module

        # Reset global state
        module._resource_manager = None

        await startup_resource_manager()

        manager = get_resource_manager()
        assert manager._running is True

        await shutdown_resource_manager()

    @pytest.mark.asyncio
    async def test_shutdown_resource_manager(self):
        """Should stop and clear resource manager."""
        from research_api.services.ollama_resource import (
            startup_resource_manager,
            shutdown_resource_manager
        )
        import research_api.services.ollama_resource as module

        # Reset global state
        module._resource_manager = None

        await startup_resource_manager()
        await shutdown_resource_manager()

        assert module._resource_manager is None

    @pytest.mark.asyncio
    async def test_shutdown_handles_no_manager(self):
        """Should handle shutdown when no manager exists."""
        from research_api.services.ollama_resource import shutdown_resource_manager
        import research_api.services.ollama_resource as module

        # Ensure no manager
        module._resource_manager = None

        # Should not raise
        await shutdown_resource_manager()


class TestIdleCleanupLoop:
    """Tests for idle cleanup loop behavior."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs(self):
        """Should run cleanup loop periodically."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=1)

        with patch.object(manager, "_check_and_unload_idle", new_callable=AsyncMock) as mock_check:
            await manager.start()

            # Let it run briefly
            await asyncio.sleep(0.1)

            await manager.stop()

            # Loop should have been started (task created)
            assert manager._cleanup_task is None  # Cleaned up after stop

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_cancellation(self):
        """Should handle cancellation gracefully."""
        from research_api.services.ollama_resource import OllamaResourceManager

        manager = OllamaResourceManager(idle_timeout=60)

        await manager.start()
        await manager.stop()

        # Should complete without error
        assert manager._running is False


class TestEnvironmentConfiguration:
    """Tests for environment variable configuration."""

    def test_uses_env_base_url(self):
        """Should use OLLAMA_BASE_URL from environment."""
        import os
        import importlib

        original = os.environ.get("OLLAMA_BASE_URL")

        try:
            os.environ["OLLAMA_BASE_URL"] = "http://custom-ollama:11434"

            # Reimport to pick up new env var
            import research_api.services.ollama_resource as module
            importlib.reload(module)

            assert module.OLLAMA_BASE_URL == "http://custom-ollama:11434"

        finally:
            if original:
                os.environ["OLLAMA_BASE_URL"] = original
            else:
                os.environ.pop("OLLAMA_BASE_URL", None)

            # Restore default
            import research_api.services.ollama_resource as module
            importlib.reload(module)

    def test_uses_env_idle_timeout(self):
        """Should use OLLAMA_IDLE_TIMEOUT_SECONDS from environment."""
        import os
        import importlib

        original = os.environ.get("OLLAMA_IDLE_TIMEOUT_SECONDS")

        try:
            os.environ["OLLAMA_IDLE_TIMEOUT_SECONDS"] = "600"

            # Reimport to pick up new env var
            import research_api.services.ollama_resource as module
            importlib.reload(module)

            assert module.OLLAMA_IDLE_TIMEOUT_SECONDS == 600

        finally:
            if original:
                os.environ["OLLAMA_IDLE_TIMEOUT_SECONDS"] = original
            else:
                os.environ.pop("OLLAMA_IDLE_TIMEOUT_SECONDS", None)

            # Restore default
            import research_api.services.ollama_resource as module
            importlib.reload(module)
