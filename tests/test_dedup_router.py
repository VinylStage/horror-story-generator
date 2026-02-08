"""
Tests for the dedup router (POST /dedup/evaluate).

Verifies:
1. Success response with full canonical_core
2. None canonical_core converted to None (no dict sent to service)
3. Response transformation: signal, similarity_score, similar_stories
4. Missing fields in service response default to empty/zero
"""

import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from src.api.routers.dedup import router
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EVALUATE_URL = "/dedup/evaluate"

FULL_CANONICAL_CORE = {
    "setting": "apartment",
    "primary_fear": "isolation",
    "antagonist": "system",
    "mechanism": "surveillance",
    "twist": "inevitability",
}

SAMPLE_SIMILAR_STORY = {
    "story_id": "story_001",
    "template_id": "T-001",
    "similarity_score": 0.85,
    "matched_dimensions": ["setting", "primary_fear"],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def app():
    """Create a minimal FastAPI app with only the dedup router."""
    _app = FastAPI()
    _app.include_router(router, prefix="/dedup")
    return _app


@pytest.fixture()
async def client(app):
    """Async HTTP client for the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /dedup/evaluate
# ---------------------------------------------------------------------------
class TestEvaluateDedup:
    """Tests for the evaluate_dedup endpoint."""

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_success_with_full_canonical_core(self, mock_eval, client):
        """Full canonical_core should be forwarded and response mapped correctly."""
        mock_eval.return_value = {
            "signal": "HIGH",
            "similarity_score": 0.92,
            "similar_stories": [SAMPLE_SIMILAR_STORY],
            "message": "High similarity detected",
        }

        resp = await client.post(
            EVALUATE_URL,
            json={
                "template_id": "T-001",
                "canonical_core": FULL_CANONICAL_CORE,
                "title": "Test Story",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["signal"] == "HIGH"
        assert body["similarity_score"] == 0.92
        assert len(body["similar_stories"]) == 1
        assert body["similar_stories"][0]["story_id"] == "story_001"
        assert body["message"] == "High similarity detected"

        # Verify service received converted dict
        call_kwargs = mock_eval.call_args.kwargs
        assert call_kwargs["template_id"] == "T-001"
        assert call_kwargs["canonical_core"]["setting"] == "apartment"
        assert call_kwargs["title"] == "Test Story"

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_none_canonical_core(self, mock_eval, client):
        """When canonical_core is None, service should receive None."""
        mock_eval.return_value = {
            "signal": "LOW",
            "similarity_score": 0.0,
            "similar_stories": [],
            "message": None,
        }

        resp = await client.post(
            EVALUATE_URL,
            json={"template_id": "T-001"},
        )

        assert resp.status_code == 200
        call_kwargs = mock_eval.call_args.kwargs
        assert call_kwargs["canonical_core"] is None

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_canonical_core_none_fields_become_empty_strings(self, mock_eval, client):
        """None fields in canonical_core should be converted to empty strings."""
        mock_eval.return_value = {
            "signal": "LOW",
            "similarity_score": 0.0,
            "similar_stories": [],
        }

        resp = await client.post(
            EVALUATE_URL,
            json={
                "canonical_core": {
                    "setting": "apartment",
                    # other fields omitted → None
                },
            },
        )

        assert resp.status_code == 200
        call_kwargs = mock_eval.call_args.kwargs
        core = call_kwargs["canonical_core"]
        assert core["setting"] == "apartment"
        assert core["primary_fear"] == ""
        assert core["antagonist"] == ""
        assert core["mechanism"] == ""
        assert core["twist"] == ""

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_response_defaults_for_missing_fields(self, mock_eval, client):
        """Missing keys in service response should use safe defaults."""
        mock_eval.return_value = {}  # Completely empty response

        resp = await client.post(
            EVALUATE_URL,
            json={"template_id": "T-001"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["signal"] == "LOW"
        assert body["similarity_score"] == 0.0
        assert body["similar_stories"] == []
        assert body["message"] is None

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_multiple_similar_stories(self, mock_eval, client):
        """Multiple similar stories should all be returned."""
        stories = [
            {
                "story_id": f"story_{i:03d}",
                "template_id": f"T-{i:03d}",
                "similarity_score": 0.9 - i * 0.1,
                "matched_dimensions": ["setting"],
            }
            for i in range(3)
        ]
        mock_eval.return_value = {
            "signal": "MEDIUM",
            "similarity_score": 0.55,
            "similar_stories": stories,
        }

        resp = await client.post(
            EVALUATE_URL,
            json={"template_id": "T-001", "canonical_core": FULL_CANONICAL_CORE},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["similar_stories"]) == 3
        assert body["similar_stories"][0]["story_id"] == "story_000"

    @patch("src.api.routers.dedup.dedup_service.evaluate_dedup", new_callable=AsyncMock)
    async def test_empty_request_body(self, mock_eval, client):
        """An empty request body should be accepted (all fields optional)."""
        mock_eval.return_value = {
            "signal": "LOW",
            "similarity_score": 0.0,
            "similar_stories": [],
        }

        resp = await client.post(EVALUATE_URL, json={})

        assert resp.status_code == 200
        call_kwargs = mock_eval.call_args.kwargs
        assert call_kwargs["template_id"] is None
        assert call_kwargs["canonical_core"] is None
        assert call_kwargs["title"] is None
