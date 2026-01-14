"""
Tests for FastAPI endpoints.

Phase B+: API router tests using TestClient with mocked services.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Should return health status."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                client = TestClient(app)
                response = client.get("/health")

                assert response.status_code == 200
                assert response.json()["status"] == "ok"
                assert "version" in response.json()


class TestResourceStatusEndpoint:
    """Tests for resource status endpoint."""

    def test_resource_status(self):
        """Should return resource manager status."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_status = {
            "running": True,
            "idle_timeout_seconds": 300,
            "active_models": {},
            "model_count": 0
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.main.get_resource_manager") as mock_get:
                    mock_manager = MagicMock()
                    mock_manager.get_status.return_value = mock_status
                    mock_get.return_value = mock_manager

                    client = TestClient(app)
                    response = client.get("/resource/status")

                    assert response.status_code == 200
                    assert response.json()["running"] is True


class TestResearchRunEndpoint:
    """Tests for POST /research/run endpoint."""

    def test_run_research_success(self):
        """Should execute research and return card info."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "card_id": "RC-20260111-120000",
            "status": "complete",
            "message": "Research completed",
            "output_path": "/path/to/card.json"
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
                    mock_exec.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/research/run",
                        json={"topic": "Korean apartment horror", "tags": ["urban", "psychological"]}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["card_id"] == "RC-20260111-120000"
                    assert data["status"] == "complete"

    def test_run_research_error(self):
        """Should return 502 when research execution fails (Issue #2)."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "card_id": "",
            "status": "error",
            "message": "Ollama connection failed",
            "output_path": None
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
                    mock_exec.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/research/run",
                        json={"topic": "Test topic"}
                    )

                    # Error responses are propagated as HTTP errors (Issue #2)
                    assert response.status_code == 502
                    data = response.json()
                    assert "Ollama" in data["detail"]

    def test_run_research_with_model_override(self):
        """Should pass model override to service."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
                    mock_exec.return_value = {"card_id": "RC-001", "status": "complete"}

                    client = TestClient(app)
                    response = client.post(
                        "/research/run",
                        json={"topic": "Test", "model": "llama3:8b", "timeout": 600}
                    )

                    assert response.status_code == 200
                    mock_exec.assert_called_once()
                    call_kwargs = mock_exec.call_args[1]
                    assert call_kwargs["model"] == "llama3:8b"
                    assert call_kwargs["timeout"] == 600


class TestResearchValidateEndpoint:
    """Tests for POST /research/validate endpoint."""

    def test_validate_success(self):
        """Should validate research card successfully."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "card_id": "RC-20260111-001",
            "is_valid": True,
            "quality_score": "good",
            "message": "Validation passed"
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.validate_card", new_callable=AsyncMock) as mock_validate:
                    mock_validate.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/research/validate",
                        json={"card_id": "RC-20260111-001"}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["is_valid"] is True
                    assert data["quality_score"] == "good"

    def test_validate_not_found(self):
        """Should handle card not found."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "card_id": "RC-NOTFOUND",
            "is_valid": False,
            "quality_score": "not_found",
            "message": "Card not found"
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.validate_card", new_callable=AsyncMock) as mock_validate:
                    mock_validate.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/research/validate",
                        json={"card_id": "RC-NOTFOUND"}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["is_valid"] is False


class TestResearchListEndpoint:
    """Tests for GET /research/list endpoint."""

    def test_list_cards(self):
        """Should list research cards."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "cards": [
                {
                    "card_id": "RC-001",
                    "title": "Test Card 1",
                    "topic": "Topic 1",
                    "quality_score": "good",
                    "created_at": "2026-01-11"
                },
                {
                    "card_id": "RC-002",
                    "title": "Test Card 2",
                    "topic": "Topic 2",
                    "quality_score": "excellent",
                    "created_at": "2026-01-10"
                }
            ],
            "total": 2,
            "limit": 10,
            "offset": 0
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.list_cards", new_callable=AsyncMock) as mock_list:
                    mock_list.return_value = mock_result

                    client = TestClient(app)
                    response = client.get("/research/list")

                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["cards"]) == 2
                    assert data["total"] == 2

    def test_list_cards_with_pagination(self):
        """Should respect pagination parameters."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.list_cards", new_callable=AsyncMock) as mock_list:
                    mock_list.return_value = {"cards": [], "total": 0, "limit": 5, "offset": 10}

                    client = TestClient(app)
                    response = client.get("/research/list?limit=5&offset=10")

                    assert response.status_code == 200
                    mock_list.assert_called_once()
                    call_kwargs = mock_list.call_args[1]
                    assert call_kwargs["limit"] == 5
                    assert call_kwargs["offset"] == 10

    def test_list_cards_with_quality_filter(self):
        """Should filter by quality."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.research_service.list_cards", new_callable=AsyncMock) as mock_list:
                    mock_list.return_value = {"cards": [], "total": 0, "limit": 10, "offset": 0}

                    client = TestClient(app)
                    response = client.get("/research/list?quality=good")

                    assert response.status_code == 200
                    call_kwargs = mock_list.call_args[1]
                    assert call_kwargs["quality"] == "good"


class TestDedupEvaluateEndpoint:
    """Tests for POST /dedup/evaluate endpoint."""

    def test_evaluate_dedup_low_signal(self):
        """Should return LOW signal for unique content."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "signal": "LOW",
            "similarity_score": 0.15,
            "similar_stories": [],
            "message": None
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.dedup_service.evaluate_dedup", new_callable=AsyncMock) as mock_eval:
                    mock_eval.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/dedup/evaluate",
                        json={
                            "template_id": "urban_horror_001",
                            "canonical_core": {
                                "setting": "subway",
                                "primary_fear": "claustrophobia"
                            }
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["signal"] == "LOW"
                    assert data["similarity_score"] == 0.15

    def test_evaluate_dedup_high_signal(self):
        """Should return HIGH signal with similar stories."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        mock_result = {
            "signal": "HIGH",
            "similarity_score": 0.85,
            "similar_stories": [
                {
                    "story_id": "123",
                    "template_id": "urban_horror_001",
                    "similarity_score": 0.85,
                    "matched_dimensions": ["setting", "primary_fear"]
                }
            ],
            "message": "High similarity detected"
        }

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.dedup_service.evaluate_dedup", new_callable=AsyncMock) as mock_eval:
                    mock_eval.return_value = mock_result

                    client = TestClient(app)
                    response = client.post(
                        "/dedup/evaluate",
                        json={
                            "template_id": "urban_horror_001",
                            "canonical_core": {
                                "setting": "apartment",
                                "primary_fear": "isolation"
                            }
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["signal"] == "HIGH"
                    assert len(data["similar_stories"]) == 1
                    assert "matched_dimensions" in data["similar_stories"][0]

    def test_evaluate_dedup_minimal_request(self):
        """Should handle request with minimal fields."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                with patch("src.api.services.dedup_service.evaluate_dedup", new_callable=AsyncMock) as mock_eval:
                    mock_eval.return_value = {"signal": "LOW", "similarity_score": 0.0, "similar_stories": []}

                    client = TestClient(app)
                    response = client.post(
                        "/dedup/evaluate",
                        json={}
                    )

                    assert response.status_code == 200


class TestOpenAPISchema:
    """Tests for OpenAPI schema generation."""

    def test_openapi_schema_exists(self):
        """Should generate OpenAPI schema."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                client = TestClient(app)
                response = client.get("/openapi.json")

                assert response.status_code == 200
                schema = response.json()
                assert schema["info"]["title"] == "Horror Story Research API"
                assert "paths" in schema

    def test_swagger_ui_available(self):
        """Should serve Swagger UI."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        with patch("src.api.main.startup_resource_manager", new_callable=AsyncMock):
            with patch("src.api.main.shutdown_resource_manager", new_callable=AsyncMock):
                client = TestClient(app)
                response = client.get("/docs")

                assert response.status_code == 200
                assert "swagger" in response.text.lower() or "html" in response.headers.get("content-type", "")
