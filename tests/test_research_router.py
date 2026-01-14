"""
Tests for research router.

Issue #2: Verify proper error propagation (502/504 instead of 200 OK).
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API."""
    from src.api.main import app
    return TestClient(app)


class TestResearchRunEndpoint:
    """Tests for POST /research/run endpoint."""

    def test_run_research_success(self, client):
        """Should return 200 with card info on success."""
        mock_result = {
            "card_id": "RC-20260115-120000",
            "status": "complete",
            "message": None,
            "output_path": "/data/research/2026/01/RC-20260115-120000.json"
        }

        with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            response = client.post(
                "/research/run",
                json={"topic": "Korean horror", "tags": ["urban"]}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["card_id"] == "RC-20260115-120000"
            assert data["status"] == "complete"

    def test_run_research_error_returns_502(self, client):
        """Should return 502 when LLM/model error occurs (Issue #2)."""
        mock_result = {
            "card_id": "",
            "status": "error",
            "message": "Gemini API error: 404 model not found",
            "output_path": None
        }

        with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            response = client.post(
                "/research/run",
                json={"topic": "Test topic", "tags": []}
            )

            assert response.status_code == 502
            data = response.json()
            assert "detail" in data
            assert "Gemini API error" in data["detail"]

    def test_run_research_timeout_returns_504(self, client):
        """Should return 504 on timeout (Issue #2)."""
        mock_result = {
            "card_id": "",
            "status": "timeout",
            "message": "Research execution timed out after 300s",
            "output_path": None
        }

        with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            response = client.post(
                "/research/run",
                json={"topic": "Test topic", "tags": [], "timeout": 300}
            )

            assert response.status_code == 504
            data = response.json()
            assert "detail" in data
            assert "timed out" in data["detail"]

    def test_run_research_ollama_error_returns_502(self, client):
        """Should return 502 when Ollama connection fails (Issue #2)."""
        mock_result = {
            "card_id": "",
            "status": "error",
            "message": "Ollama connection failed: Connection refused",
            "output_path": None
        }

        with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            response = client.post(
                "/research/run",
                json={"topic": "Test topic", "tags": [], "model": "qwen3:30b"}
            )

            assert response.status_code == 502
            data = response.json()
            assert "Ollama" in data["detail"]

    def test_run_research_requires_topic(self, client):
        """Should require topic parameter (422 validation error)."""
        response = client.post(
            "/research/run",
            json={"tags": ["test"]}  # Missing required topic
        )

        assert response.status_code == 422

    def test_run_research_default_error_message(self, client):
        """Should use default error message when none provided."""
        mock_result = {
            "card_id": "",
            "status": "error",
            "message": None,  # No message provided
            "output_path": None
        }

        with patch("src.api.services.research_service.execute_research", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            response = client.post(
                "/research/run",
                json={"topic": "Test topic", "tags": []}
            )

            assert response.status_code == 502
            data = response.json()
            assert data["detail"] == "Research generation failed"


class TestResearchValidateEndpoint:
    """Tests for POST /research/validate endpoint."""

    def test_validate_success(self, client):
        """Should return validation result."""
        mock_result = {
            "card_id": "RC-20260115-120000",
            "is_valid": True,
            "quality_score": "good",
            "message": "Validation passed"
        }

        with patch("src.api.services.research_service.validate_card", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = mock_result

            response = client.post(
                "/research/validate",
                json={"card_id": "RC-20260115-120000"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_valid"] is True
            assert data["quality_score"] == "good"


class TestResearchListEndpoint:
    """Tests for GET /research/list endpoint."""

    def test_list_success(self, client):
        """Should return list of research cards."""
        mock_result = {
            "cards": [
                {
                    "card_id": "RC-20260115-001",
                    "title": "Card One",
                    "topic": "Horror",
                    "quality_score": "good",
                    "created_at": "2026-01-15"
                }
            ],
            "total": 1,
            "limit": 10,
            "offset": 0,
            "message": None
        }

        with patch("src.api.services.research_service.list_cards", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result

            response = client.get("/research/list")

            assert response.status_code == 200
            data = response.json()
            assert len(data["cards"]) == 1
            assert data["total"] == 1


class TestResearchDedupEndpoint:
    """Tests for POST /research/dedup endpoint."""

    def test_dedup_check_success(self, client):
        """Should return dedup check result."""
        mock_result = {
            "card_id": "RC-20260115-001",
            "signal": "LOW",
            "similarity_score": 0.15,
            "nearest_card_id": None,
            "similar_cards": [],
            "index_size": 100,
            "message": None
        }

        with patch("src.api.services.research_service.check_semantic_dedup", new_callable=AsyncMock) as mock_dedup:
            mock_dedup.return_value = mock_result

            response = client.post(
                "/research/dedup",
                json={"card_id": "RC-20260115-001"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["signal"] == "LOW"
            assert data["similarity_score"] == 0.15
