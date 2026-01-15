"""
API Key authentication dependency.

Optional authentication controlled by API_AUTH_ENABLED environment variable.
When enabled, requires X-API-Key header matching API_KEY env variable.
"""

import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# Environment configuration
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")

# Header definition
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,  # We handle the error ourselves for optional auth
    description="API key for authentication (required when API_AUTH_ENABLED=true)",
)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """
    Verify API key from X-API-Key header.

    Behavior:
    - When API_AUTH_ENABLED=false: Always passes (returns None)
    - When API_AUTH_ENABLED=true: Requires valid API key

    Raises:
        HTTPException: 401 if auth enabled and key is missing/invalid

    Returns:
        The API key if valid, None if auth disabled
    """
    # Auth disabled - allow all requests
    if not API_AUTH_ENABLED:
        return None

    # Auth enabled - validate key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
