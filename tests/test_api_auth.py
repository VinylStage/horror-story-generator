"""
Tests for API authentication.

Tests X-API-Key header authentication when API_AUTH_ENABLED=true.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock


# Test API key for testing
TEST_API_KEY = "test-secret-key-12345"


@pytest.fixture
def mock_resource_manager():
    """Mock the Ollama resource manager for all tests."""
    with patch(
        "src.api.main.startup_resource_manager", new_callable=AsyncMock
    ) as mock_startup:
        with patch(
            "src.api.main.shutdown_resource_manager", new_callable=AsyncMock
        ) as mock_shutdown:
            with patch("src.api.main.get_resource_manager") as mock_get:
                mock_manager = AsyncMock()
                mock_manager.get_status.return_value = {
                    "active_models": [],
                    "idle_timeout": 300,
                }
                mock_get.return_value = mock_manager
                yield {
                    "startup": mock_startup,
                    "shutdown": mock_shutdown,
                    "manager": mock_manager,
                }


class TestAuthDisabled:
    """Tests when authentication is disabled (default)."""

    def test_health_no_auth_required(self, mock_resource_manager):
        """Health endpoint should work without auth."""
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}, clear=False):
            # Reload auth module to pick up env change
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            # Re-import main to get fresh app with reloaded auth
            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_resource_status_no_auth_required(self, mock_resource_manager):
        """Resource status endpoint should work without auth."""
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}, clear=False):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)
            response = client.get("/resource/status")

            assert response.status_code == 200


class TestAuthEnabled:
    """Tests when authentication is enabled."""

    def test_health_no_auth_required_even_when_enabled(self, mock_resource_manager):
        """Health endpoint should work without auth even when auth is enabled."""
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEY": TEST_API_KEY},
            clear=False,
        ):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_protected_endpoint_requires_auth(self, mock_resource_manager):
        """Protected endpoints should require auth when enabled."""
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEY": TEST_API_KEY},
            clear=False,
        ):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)

            # No API key - should fail
            response = client.get("/story/list")

            assert response.status_code == 401
            assert "Missing API key" in response.json()["detail"]

    def test_protected_endpoint_with_valid_key(self, mock_resource_manager):
        """Protected endpoints should work with valid API key."""
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEY": TEST_API_KEY},
            clear=False,
        ):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            # Mock the story registry
            with patch("src.registry.story_registry.StoryRegistry") as MockRegistry:
                mock_registry = MockRegistry.return_value
                mock_registry.load_recent_accepted.return_value = []

                client = TestClient(main_module.app)
                response = client.get(
                    "/story/list", headers={"X-API-Key": TEST_API_KEY}
                )

                # Should pass auth (not 401)
                assert response.status_code == 200

    def test_protected_endpoint_with_invalid_key(self, mock_resource_manager):
        """Protected endpoints should reject invalid API key."""
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEY": TEST_API_KEY},
            clear=False,
        ):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)

            response = client.get("/story/list", headers={"X-API-Key": "wrong-key"})

            assert response.status_code == 401
            assert "Invalid API key" in response.json()["detail"]

    def test_all_routers_require_auth_when_enabled(self, mock_resource_manager):
        """All routers should require auth when enabled."""
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEY": TEST_API_KEY},
            clear=False,
        ):
            import importlib
            import src.api.dependencies.auth as auth_module

            importlib.reload(auth_module)

            import src.api.main as main_module

            importlib.reload(main_module)

            from fastapi.testclient import TestClient

            client = TestClient(main_module.app)

            # Test various endpoints across routers
            protected_endpoints = [
                ("GET", "/story/list"),
                ("GET", "/jobs"),
                ("GET", "/research/list"),
            ]

            for method, path in protected_endpoints:
                response = client.get(path)
                assert response.status_code == 401, f"Expected 401 for {method} {path}"
