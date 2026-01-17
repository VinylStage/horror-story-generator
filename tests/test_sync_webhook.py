"""
Tests for sync endpoint webhook functionality (v1.4.3).

Tests fire-and-forget webhook support for:
- POST /research/run
- POST /story/generate
"""

import time
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.infra.webhook import (
    build_sync_webhook_payload,
    fire_and_forget_webhook,
    _send_webhook_in_thread,
)


class TestBuildSyncWebhookPayload:
    """Tests for build_sync_webhook_payload function."""

    def test_success_payload(self):
        """Test payload for successful response."""
        result = {"card_id": "RC-123", "output_path": "/path/to/card.json"}
        payload = build_sync_webhook_payload(
            endpoint="/research/run",
            status="success",
            result=result,
        )

        assert payload["event"] == "completed"
        assert payload["endpoint"] == "/research/run"
        assert payload["status"] == "success"
        assert payload["result"] == result
        assert "timestamp" in payload

    def test_error_payload(self):
        """Test payload for error response."""
        result = {"error": "Generation failed"}
        payload = build_sync_webhook_payload(
            endpoint="/story/generate",
            status="error",
            result=result,
        )

        assert payload["event"] == "error"
        assert payload["endpoint"] == "/story/generate"
        assert payload["status"] == "error"
        assert payload["result"]["error"] == "Generation failed"

    def test_timestamp_format(self):
        """Test that timestamp is ISO format."""
        payload = build_sync_webhook_payload(
            endpoint="/test",
            status="success",
            result={},
        )

        # Should be parseable as ISO timestamp
        timestamp = payload["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)


class TestFireAndForgetWebhook:
    """Tests for fire_and_forget_webhook function."""

    def test_returns_false_for_empty_url(self):
        """Test that empty URL returns False without sending."""
        result = fire_and_forget_webhook(
            url="",
            endpoint="/test",
            status="success",
            result={},
        )
        assert result is False

    def test_returns_false_for_none_url(self):
        """Test that None URL returns False without sending."""
        result = fire_and_forget_webhook(
            url=None,
            endpoint="/test",
            status="success",
            result={},
        )
        assert result is False

    @patch("src.infra.webhook.threading.Thread")
    def test_starts_background_thread(self, mock_thread_class):
        """Test that a background thread is started."""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        result = fire_and_forget_webhook(
            url="https://example.com/webhook",
            endpoint="/research/run",
            status="success",
            result={"card_id": "RC-123"},
        )

        assert result is True
        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch("src.infra.webhook.threading.Thread")
    def test_thread_is_daemon(self, mock_thread_class):
        """Test that the thread is created as daemon."""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        fire_and_forget_webhook(
            url="https://example.com/webhook",
            endpoint="/test",
            status="success",
            result={},
        )

        # Check daemon=True was passed
        call_kwargs = mock_thread_class.call_args[1]
        assert call_kwargs.get("daemon") is True


class TestSendWebhookInThread:
    """Tests for _send_webhook_in_thread function."""

    @patch("src.infra.webhook.httpx.Client")
    def test_successful_send(self, mock_client_class):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        payload = {"event": "completed", "endpoint": "/test"}
        _send_webhook_in_thread(
            url="https://example.com/webhook",
            payload=payload,
            max_retries=1,
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json"] == payload

    @patch("src.infra.webhook.httpx.Client")
    def test_retries_on_failure(self, mock_client_class):
        """Test that webhook retries on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        payload = {"event": "completed"}
        _send_webhook_in_thread(
            url="https://example.com/webhook",
            payload=payload,
            max_retries=2,
        )

        # Should have been called twice (initial + 1 retry)
        assert mock_client.post.call_count == 2

    @patch("src.infra.webhook.httpx.Client")
    def test_includes_custom_headers(self, mock_client_class):
        """Test that custom headers are included."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        payload = {"event": "completed", "endpoint": "/research/run"}
        _send_webhook_in_thread(
            url="https://example.com/webhook",
            payload=payload,
            max_retries=1,
        )

        call_kwargs = mock_client.post.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers
        assert headers["X-Webhook-Event"] == "completed"
        assert headers["X-Webhook-Endpoint"] == "/research/run"


class TestSchemaWebhookFields:
    """Tests for webhook fields in request/response schemas."""

    def test_research_request_has_webhook_url(self):
        """Test ResearchRunRequest has webhook_url field."""
        from src.api.schemas.research import ResearchRunRequest

        request = ResearchRunRequest(
            topic="test topic",
            webhook_url="https://example.com/webhook",
        )
        assert request.webhook_url == "https://example.com/webhook"

    def test_research_request_webhook_url_optional(self):
        """Test webhook_url is optional in ResearchRunRequest."""
        from src.api.schemas.research import ResearchRunRequest

        request = ResearchRunRequest(topic="test topic")
        assert request.webhook_url is None

    def test_research_response_has_webhook_triggered(self):
        """Test ResearchRunResponse has webhook_triggered field."""
        from src.api.schemas.research import ResearchRunResponse

        response = ResearchRunResponse(
            card_id="RC-123",
            status="success",
            webhook_triggered=True,
        )
        assert response.webhook_triggered is True

    def test_story_request_has_webhook_url(self):
        """Test StoryGenerateRequest has webhook_url field."""
        from src.api.schemas.story import StoryGenerateRequest

        request = StoryGenerateRequest(
            webhook_url="https://example.com/webhook",
        )
        assert request.webhook_url == "https://example.com/webhook"

    def test_story_request_webhook_url_optional(self):
        """Test webhook_url is optional in StoryGenerateRequest."""
        from src.api.schemas.story import StoryGenerateRequest

        request = StoryGenerateRequest()
        assert request.webhook_url is None

    def test_story_response_has_webhook_triggered(self):
        """Test StoryGenerateResponse has webhook_triggered field."""
        from src.api.schemas.story import StoryGenerateResponse

        response = StoryGenerateResponse(
            success=True,
            webhook_triggered=True,
        )
        assert response.webhook_triggered is True
