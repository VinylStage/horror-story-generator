"""
Tests for API authentication.

Tests X-API-Key header authentication when API_AUTH_ENABLED=true.
"""

import importlib

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


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
                mock_manager = MagicMock()
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


@pytest.fixture
def auth_disabled(monkeypatch):
    """Configure auth module with authentication disabled."""
    import src.api.dependencies.auth as auth_module
    monkeypatch.setattr(auth_module, "API_AUTH_ENABLED", False)
    monkeypatch.setattr(auth_module, "API_KEY", "")


@pytest.fixture
def auth_enabled(monkeypatch):
    """Configure auth module with authentication enabled.

    Requires importlib.reload of main module because auth_dependency
    (the router dependency list) is computed at module load time from
    API_AUTH_ENABLED.  Monkeypatching the auth module alone is not
    sufficient to re-register routes with the dependency.
    """
    import src.api.dependencies.auth as auth_module
    monkeypatch.setattr(auth_module, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(auth_module, "API_KEY", TEST_API_KEY)

    # Reload main so that auth_dependency = [Depends(verify_api_key)]
    # picks up the patched API_AUTH_ENABLED value.
    import src.api.main as main_module
    importlib.reload(main_module)

    yield main_module

    # Reload again to restore default (auth disabled) for other tests
    monkeypatch.setattr(auth_module, "API_AUTH_ENABLED", False)
    monkeypatch.setattr(auth_module, "API_KEY", "")
    importlib.reload(main_module)


class TestAuthDisabled:
    """Tests when authentication is disabled (default)."""

    def test_health_no_auth_required(self, mock_resource_manager, auth_disabled):
        """Health endpoint should work without auth."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_resource_status_no_auth_required(self, mock_resource_manager, auth_disabled):
        """Resource status endpoint should work without auth."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/resource/status")

        assert response.status_code == 200


class TestAuthEnabled:
    """Tests when authentication is enabled."""

    def test_health_no_auth_required_even_when_enabled(self, mock_resource_manager, auth_enabled):
        """Health endpoint should work without auth even when auth is enabled."""
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_protected_endpoint_requires_auth(self, mock_resource_manager, auth_enabled):
        """Protected endpoints should require auth when enabled."""
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)

        # No API key - should fail
        response = client.get("/story/list")

        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_protected_endpoint_with_valid_key(self, mock_resource_manager, auth_enabled):
        """Protected endpoints should work with valid API key."""
        from fastapi.testclient import TestClient

        # Mock the story registry
        with patch("src.registry.story_registry.StoryRegistry") as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.load_recent_accepted.return_value = []

            client = TestClient(auth_enabled.app)
            response = client.get(
                "/story/list", headers={"X-API-Key": TEST_API_KEY}
            )

            # Should pass auth (not 401)
            assert response.status_code == 200

    def test_protected_endpoint_with_invalid_key(self, mock_resource_manager, auth_enabled):
        """Protected endpoints should reject invalid API key."""
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)

        response = client.get("/story/list", headers={"X-API-Key": "wrong-key"})

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_all_routers_require_auth_when_enabled(self, mock_resource_manager, auth_enabled):
        """All routers should require auth when enabled."""
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)

        # Test various endpoints across routers
        protected_endpoints = [
            ("GET", "/story/list"),
            ("GET", "/tasks"),
            ("GET", "/research/list"),
        ]

        for method, path in protected_endpoints:
            response = client.get(path)
            assert response.status_code == 401, f"Expected 401 for {method} {path}"
