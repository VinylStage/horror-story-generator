"""
API Dependencies package.

Cross-cutting concerns like authentication, rate limiting, etc.
"""

from .auth import verify_api_key, API_AUTH_ENABLED

__all__ = ["verify_api_key", "API_AUTH_ENABLED"]
