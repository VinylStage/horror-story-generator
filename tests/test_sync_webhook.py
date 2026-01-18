"""
Tests for sync endpoint webhook functionality (v1.4.3).
v1.4.4: Added Discord webhook format tests.

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
    is_discord_webhook_url,
    build_discord_embed_payload,
    DISCORD_COLOR_SUCCESS,
    DISCORD_COLOR_ERROR,
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


class TestDiscordWebhookDetection:
    """Tests for Discord webhook URL detection (v1.4.4)."""

    def test_detects_discord_webhook_url(self):
        """Test detection of discord.com webhook URL."""
        url = "https://discord.com/api/webhooks/123456/abcdef"
        assert is_discord_webhook_url(url) is True

    def test_detects_discordapp_webhook_url(self):
        """Test detection of discordapp.com webhook URL."""
        url = "https://discordapp.com/api/webhooks/123456/abcdef"
        assert is_discord_webhook_url(url) is True

    def test_rejects_non_discord_url(self):
        """Test that non-Discord URLs are not detected."""
        url = "https://example.com/webhook"
        assert is_discord_webhook_url(url) is False

    def test_rejects_empty_url(self):
        """Test that empty URL returns False."""
        assert is_discord_webhook_url("") is False

    def test_rejects_none_url(self):
        """Test that None URL returns False."""
        assert is_discord_webhook_url(None) is False

    def test_rejects_partial_match(self):
        """Test that partial matches are rejected."""
        url = "https://notdiscord.com/api/webhooks/123"
        assert is_discord_webhook_url(url) is False


class TestBuildDiscordEmbedPayload:
    """Tests for Discord embed payload builder (v1.4.4)."""

    def test_success_payload_has_embeds(self):
        """Test that success payload contains embeds array."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="success",
            result={"card_id": "RC-123"},
        )

        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

    def test_success_payload_has_green_color(self):
        """Test that success payload uses green color."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        assert embed["color"] == DISCORD_COLOR_SUCCESS

    def test_error_payload_has_red_color(self):
        """Test that error payload uses red color."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="error",
            result={"error": "Something failed"},
        )

        embed = payload["embeds"][0]
        assert embed["color"] == DISCORD_COLOR_ERROR

    def test_research_success_title(self):
        """Test title for research success."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        assert "Research" in embed["title"]
        assert "Completed" in embed["title"]
        assert "✅" in embed["title"]

    def test_story_success_title(self):
        """Test title for story success."""
        payload = build_discord_embed_payload(
            endpoint="/story/generate",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        assert "Story" in embed["title"]
        assert "Completed" in embed["title"]

    def test_error_title_has_failed(self):
        """Test that error title contains 'Failed'."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="error",
            result={},
        )

        embed = payload["embeds"][0]
        assert "Failed" in embed["title"]
        assert "❌" in embed["title"]

    def test_includes_card_id_field(self):
        """Test that card_id is included in fields."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="success",
            result={"card_id": "RC-123"},
        )

        embed = payload["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Card ID" in field_names

    def test_includes_story_id_field(self):
        """Test that story_id is included in fields."""
        payload = build_discord_embed_payload(
            endpoint="/story/generate",
            status="success",
            result={"story_id": "ST-456"},
        )

        embed = payload["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Story ID" in field_names

    def test_includes_error_field(self):
        """Test that error message is included in fields."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="error",
            result={"error": "Something went wrong"},
        )

        embed = payload["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Error" in field_names

    def test_always_includes_endpoint_field(self):
        """Test that endpoint is always included."""
        payload = build_discord_embed_payload(
            endpoint="/research/run",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Endpoint" in field_names

    def test_has_timestamp(self):
        """Test that embed has timestamp."""
        payload = build_discord_embed_payload(
            endpoint="/test",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        assert "timestamp" in embed

    def test_has_footer(self):
        """Test that embed has footer."""
        payload = build_discord_embed_payload(
            endpoint="/test",
            status="success",
            result={},
        )

        embed = payload["embeds"][0]
        assert "footer" in embed
        assert "Horror Story Generator" in embed["footer"]["text"]


class TestDiscordWebhookIntegration:
    """Tests for Discord webhook integration with fire_and_forget_webhook (v1.4.4)."""

    @patch("src.infra.webhook.threading.Thread")
    def test_uses_discord_format_for_discord_url(self, mock_thread_class):
        """Test that Discord format is used for Discord URLs."""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        fire_and_forget_webhook(
            url="https://discord.com/api/webhooks/123/abc",
            endpoint="/research/run",
            status="success",
            result={"card_id": "RC-123"},
        )

        # Get the payload passed to the thread
        call_args = mock_thread_class.call_args
        thread_args = call_args[1]["args"]
        payload = thread_args[1]

        # Discord payload should have "embeds" key
        assert "embeds" in payload
        assert "event" not in payload

    @patch("src.infra.webhook.threading.Thread")
    def test_uses_standard_format_for_non_discord_url(self, mock_thread_class):
        """Test that standard format is used for non-Discord URLs."""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        fire_and_forget_webhook(
            url="https://example.com/webhook",
            endpoint="/research/run",
            status="success",
            result={"card_id": "RC-123"},
        )

        # Get the payload passed to the thread
        call_args = mock_thread_class.call_args
        thread_args = call_args[1]["args"]
        payload = thread_args[1]

        # Standard payload should have "event" key
        assert "event" in payload
        assert "embeds" not in payload

    @patch("src.infra.webhook.httpx.Client")
    def test_discord_webhook_no_custom_headers(self, mock_client_class):
        """Test that Discord webhooks don't get custom X-Webhook headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        payload = {"embeds": [{"title": "Test"}]}
        _send_webhook_in_thread(
            url="https://discord.com/api/webhooks/123/abc",
            payload=payload,
            max_retries=1,
        )

        call_kwargs = mock_client.post.call_args[1]
        headers = call_kwargs["headers"]

        # Should have Content-Type and User-Agent
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers

        # Should NOT have custom webhook headers
        assert "X-Webhook-Event" not in headers
        assert "X-Webhook-Endpoint" not in headers
