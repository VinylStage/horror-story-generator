"""
Pytest configuration and shared fixtures.
"""

import os
import pytest


@pytest.fixture(autouse=True, scope="function")
def reset_auth_module():
    """
    Reset auth module state before each test.

    This ensures tests run with API_AUTH_ENABLED=false by default,
    unless the test explicitly sets it otherwise.
    """
    # Store original values
    original_auth_enabled = os.environ.get("API_AUTH_ENABLED")
    original_api_key = os.environ.get("API_KEY")

    # Set defaults for tests (auth disabled)
    os.environ["API_AUTH_ENABLED"] = "false"

    yield

    # Restore original values
    if original_auth_enabled is not None:
        os.environ["API_AUTH_ENABLED"] = original_auth_enabled
    elif "API_AUTH_ENABLED" in os.environ:
        del os.environ["API_AUTH_ENABLED"]

    if original_api_key is not None:
        os.environ["API_KEY"] = original_api_key
    elif "API_KEY" in os.environ:
        del os.environ["API_KEY"]

    # Reload auth module to reset state
    try:
        import importlib
        import src.api.dependencies.auth as auth_module
        importlib.reload(auth_module)
    except ImportError:
        pass
