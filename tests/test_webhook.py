"""Tests for webhook notification service."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from src.infra.webhook import (
    build_webhook_payload,
    send_webhook_async,
    send_webhook_sync,
    should_send_webhook,
    process_webhook_for_job,
    WEBHOOK_TIMEOUT_SECONDS,
    WEBHOOK_MAX_RETRIES,
)
from src.infra.job_manager import Job


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return Job(
        job_id="test-job-123",
        type="story_generation",
        status="completed",
        params={"template_id": "T-001"},
        created_at="2024-01-01T10:00:00",
        started_at="2024-01-01T10:00:01",
        finished_at="2024-01-01T10:05:00",
        exit_code=0,
        error=None,
        artifacts={"story_path": "/output/story.json"},
        webhook_url="https://example.com/webhook",
        webhook_events={"completed", "failed"},
        webhook_sent=False,
        webhook_error=None,
    )


class TestBuildWebhookPayload:
    """Tests for build_webhook_payload function."""

    def test_builds_complete_payload(self, sample_job):
        """Test building a complete payload from job."""
        payload = build_webhook_payload(sample_job)

        assert payload["event"] == "completed"
        assert payload["job_id"] == "test-job-123"
        assert payload["type"] == "story_generation"
        assert payload["status"] == "completed"
        assert payload["params"] == {"template_id": "T-001"}
        assert payload["created_at"] == "2024-01-01T10:00:00"
        assert payload["started_at"] == "2024-01-01T10:00:01"
        assert payload["finished_at"] == "2024-01-01T10:05:00"
        assert payload["exit_code"] == 0
        assert payload["error"] is None
        assert payload["artifacts"] == {"story_path": "/output/story.json"}
        assert "timestamp" in payload

    def test_payload_with_error(self, sample_job):
        """Test building payload when job has error."""
        sample_job.status = "failed"
        sample_job.error = "Generation failed"
        sample_job.exit_code = 1

        payload = build_webhook_payload(sample_job)

        assert payload["status"] == "failed"
        assert payload["error"] == "Generation failed"
        assert payload["exit_code"] == 1


class TestShouldSendWebhook:
    """Tests for should_send_webhook function."""

    def test_returns_false_when_no_webhook_url(self, sample_job):
        """Test returns False when no webhook URL configured."""
        sample_job.webhook_url = None
        assert should_send_webhook(sample_job) is False

    def test_returns_false_when_already_sent(self, sample_job):
        """Test returns False when webhook already sent."""
        sample_job.webhook_sent = True
        assert should_send_webhook(sample_job) is False

    def test_returns_false_when_status_not_in_events(self, sample_job):
        """Test returns False when status not in subscribed events."""
        sample_job.status = "running"
        sample_job.webhook_events = {"completed"}
        assert should_send_webhook(sample_job) is False

    def test_returns_true_when_all_conditions_met(self, sample_job):
        """Test returns True when all conditions are met."""
        sample_job.status = "completed"
        sample_job.webhook_events = {"completed"}
        sample_job.webhook_url = "https://example.com/webhook"
        sample_job.webhook_sent = False

        assert should_send_webhook(sample_job) is True


class TestSendWebhookAsync:
    """Tests for send_webhook_async function."""

    @pytest.mark.asyncio
    async def test_successful_send(self, sample_job):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = await send_webhook_async(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_http_error_response(self, sample_job):
        """Test handling HTTP error response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = await send_webhook_async(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "HTTP 500" in error

    @pytest.mark.asyncio
    async def test_timeout_error(self, sample_job):
        """Test handling timeout error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = await send_webhook_async(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Timeout" in error

    @pytest.mark.asyncio
    async def test_request_error(self, sample_job):
        """Test handling request error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = await send_webhook_async(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Request error" in error

    @pytest.mark.asyncio
    async def test_unexpected_error(self, sample_job):
        """Test handling unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = await send_webhook_async(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Unexpected error" in error

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, sample_job):
        """Test retry behavior on failure."""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Error"

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = "OK"

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return mock_response_fail
            return mock_response_success

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):
                success, error = await send_webhook_async(
                    sample_job,
                    "https://example.com/webhook",
                    timeout=5,
                    max_retries=3
                )

        assert success is True
        assert call_count == 2


class TestSendWebhookSync:
    """Tests for send_webhook_sync function."""

    def test_successful_send(self, sample_job):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = send_webhook_sync(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is True
        assert error is None

    def test_http_error_response(self, sample_job):
        """Test handling HTTP error response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = send_webhook_sync(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "HTTP 404" in error

    def test_timeout_error(self, sample_job):
        """Test handling timeout error."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = send_webhook_sync(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Timeout" in error

    def test_request_error(self, sample_job):
        """Test handling request error."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.RequestError("Connection refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = send_webhook_sync(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Request error" in error

    def test_unexpected_error(self, sample_job):
        """Test handling unexpected error."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.side_effect = ValueError("Unexpected")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, error = send_webhook_sync(
                sample_job,
                "https://example.com/webhook",
                timeout=5,
                max_retries=1
            )

        assert success is False
        assert "Unexpected error" in error

    def test_retry_with_backoff(self, sample_job):
        """Test retry with exponential backoff."""
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service Unavailable"

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = "OK"

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return mock_response_fail
            return mock_response_success

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch("time.sleep"):
                success, error = send_webhook_sync(
                    sample_job,
                    "https://example.com/webhook",
                    timeout=5,
                    max_retries=3
                )

        assert success is True
        assert call_count == 3


class TestProcessWebhookForJob:
    """Tests for process_webhook_for_job function."""

    def test_skips_when_should_not_send(self, sample_job):
        """Test that processing is skipped when should_send_webhook returns False."""
        sample_job.webhook_url = None  # No webhook URL

        with patch("src.infra.webhook.send_webhook_sync") as mock_send:
            result = process_webhook_for_job(sample_job)

        mock_send.assert_not_called()
        assert result is sample_job

    def test_sends_webhook_and_updates_job_on_success(self, sample_job):
        """Test successful webhook send updates job."""
        with patch("src.infra.webhook.send_webhook_sync", return_value=(True, None)) as mock_send:
            with patch("src.infra.webhook.save_job") as mock_save:
                result = process_webhook_for_job(sample_job)

        mock_send.assert_called_once()
        mock_save.assert_called_once_with(sample_job)
        assert result.webhook_sent is True
        assert result.webhook_error is None

    def test_sends_webhook_and_updates_job_on_failure(self, sample_job):
        """Test failed webhook send updates job with error."""
        with patch("src.infra.webhook.send_webhook_sync", return_value=(False, "Connection failed")) as mock_send:
            with patch("src.infra.webhook.save_job") as mock_save:
                result = process_webhook_for_job(sample_job)

        mock_send.assert_called_once()
        mock_save.assert_called_once_with(sample_job)
        assert result.webhook_sent is False
        assert result.webhook_error == "Connection failed"
