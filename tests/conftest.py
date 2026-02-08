"""
Pytest configuration and shared fixtures.
"""

import pytest


@pytest.fixture(scope="function")
def reset_auth_module(monkeypatch):
    """
    Reset auth module state for a test.

    Sets API_AUTH_ENABLED=false by default and patches the module-level
    constants in the auth module. Tests that need auth enabled should
    use monkeypatch to override.
    """
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    monkeypatch.delenv("API_KEY", raising=False)

    import src.api.dependencies.auth as auth_module
    monkeypatch.setattr(auth_module, "API_AUTH_ENABLED", False)
    monkeypatch.setattr(auth_module, "API_KEY", "")
