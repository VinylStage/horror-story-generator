"""
Webhook notification service for job completion callbacks.

v1.3.0: Sends HTTP POST notifications when jobs reach terminal states.
v1.4.3: Fire-and-forget webhook support for sync endpoints.
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, Optional
import httpx

from src.infra.job_manager import Job, WebhookEvent, save_job

logger = logging.getLogger(__name__)

# Webhook configuration
WEBHOOK_TIMEOUT_SECONDS = 30
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_BASE_DELAY = 1.0  # seconds
WEBHOOK_RETRY_MAX_DELAY = 10.0  # seconds


def build_webhook_payload(job: Job) -> dict:
    """
    Build webhook payload from job data.

    Args:
        job: Job instance

    Returns:
        Dictionary payload for webhook POST
    """
    return {
        "event": job.status,
        "job_id": job.job_id,
        "type": job.type,
        "status": job.status,
        "params": job.params,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "exit_code": job.exit_code,
        "error": job.error,
        "artifacts": job.artifacts,
        "timestamp": datetime.now().isoformat(),
    }


async def send_webhook_async(
    job: Job,
    url: str,
    timeout: float = WEBHOOK_TIMEOUT_SECONDS,
    max_retries: int = WEBHOOK_MAX_RETRIES,
) -> tuple[bool, Optional[str]]:
    """
    Send webhook notification asynchronously with retry logic.

    Args:
        job: Job instance to send notification for
        url: Webhook URL to POST to
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    payload = build_webhook_payload(job)
    last_error: Optional[str] = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "HorrorStoryGenerator/1.3",
                        "X-Job-ID": job.job_id,
                        "X-Job-Event": job.status,
                    },
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook sent successfully for job {job.job_id} "
                        f"(attempt {attempt + 1}/{max_retries}, status={response.status_code})"
                    )
                    return True, None

                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    f"Webhook failed for job {job.job_id} "
                    f"(attempt {attempt + 1}/{max_retries}): {last_error}"
                )

        except httpx.TimeoutException:
            last_error = f"Timeout after {timeout}s"
            logger.warning(
                f"Webhook timeout for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries})"
            )

        except httpx.RequestError as e:
            last_error = f"Request error: {str(e)}"
            logger.warning(
                f"Webhook request error for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(
                f"Webhook unexpected error for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        # Exponential backoff before retry
        if attempt < max_retries - 1:
            delay = min(
                WEBHOOK_RETRY_BASE_DELAY * (2 ** attempt),
                WEBHOOK_RETRY_MAX_DELAY
            )
            logger.debug(f"Retrying webhook in {delay}s...")
            await asyncio.sleep(delay)

    logger.error(
        f"Webhook failed after {max_retries} attempts for job {job.job_id}: {last_error}"
    )
    return False, last_error


def send_webhook_sync(
    job: Job,
    url: str,
    timeout: float = WEBHOOK_TIMEOUT_SECONDS,
    max_retries: int = WEBHOOK_MAX_RETRIES,
) -> tuple[bool, Optional[str]]:
    """
    Send webhook notification synchronously with retry logic.

    Args:
        job: Job instance to send notification for
        url: Webhook URL to POST to
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    payload = build_webhook_payload(job)
    last_error: Optional[str] = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "HorrorStoryGenerator/1.3",
                        "X-Job-ID": job.job_id,
                        "X-Job-Event": job.status,
                    },
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook sent successfully for job {job.job_id} "
                        f"(attempt {attempt + 1}/{max_retries}, status={response.status_code})"
                    )
                    return True, None

                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    f"Webhook failed for job {job.job_id} "
                    f"(attempt {attempt + 1}/{max_retries}): {last_error}"
                )

        except httpx.TimeoutException:
            last_error = f"Timeout after {timeout}s"
            logger.warning(
                f"Webhook timeout for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries})"
            )

        except httpx.RequestError as e:
            last_error = f"Request error: {str(e)}"
            logger.warning(
                f"Webhook request error for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(
                f"Webhook unexpected error for job {job.job_id} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        # Exponential backoff before retry (blocking)
        if attempt < max_retries - 1:
            import time
            delay = min(
                WEBHOOK_RETRY_BASE_DELAY * (2 ** attempt),
                WEBHOOK_RETRY_MAX_DELAY
            )
            logger.debug(f"Retrying webhook in {delay}s...")
            time.sleep(delay)

    logger.error(
        f"Webhook failed after {max_retries} attempts for job {job.job_id}: {last_error}"
    )
    return False, last_error


def should_send_webhook(job: Job) -> bool:
    """
    Determine if webhook should be sent for this job.

    Args:
        job: Job instance

    Returns:
        True if webhook should be sent
    """
    # No webhook URL configured
    if not job.webhook_url:
        return False

    # Already sent
    if job.webhook_sent:
        return False

    # Check if current status is in the subscribed events
    if job.status not in job.webhook_events:
        return False

    return True


def process_webhook_for_job(job: Job) -> Job:
    """
    Process webhook notification for a job if applicable.

    This function checks if a webhook should be sent, sends it,
    and updates the job's webhook_sent and webhook_error fields.

    Args:
        job: Job instance (will be modified in place)

    Returns:
        Updated Job instance
    """
    if not should_send_webhook(job):
        return job

    logger.info(
        f"Sending webhook for job {job.job_id} "
        f"(status={job.status}, url={job.webhook_url})"
    )

    success, error = send_webhook_sync(job, job.webhook_url)

    job.webhook_sent = success
    if error:
        job.webhook_error = error

    # Save updated job state
    save_job(job)

    return job


# =============================================================================
# Fire-and-Forget Webhook for Sync Endpoints (v1.4.3)
# =============================================================================


def build_sync_webhook_payload(
    endpoint: str,
    status: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build webhook payload for sync endpoint notifications.

    Args:
        endpoint: The API endpoint path (e.g., "/research/run")
        status: Result status ("success" or "error")
        result: The response data to include

    Returns:
        Dictionary payload for webhook POST
    """
    return {
        "event": "completed" if status == "success" else "error",
        "endpoint": endpoint,
        "status": status,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    }


def _send_webhook_in_thread(
    url: str,
    payload: Dict[str, Any],
    timeout: float = WEBHOOK_TIMEOUT_SECONDS,
    max_retries: int = WEBHOOK_MAX_RETRIES,
) -> None:
    """
    Internal function to send webhook in a background thread.

    This runs in a separate thread for fire-and-forget behavior.
    """
    last_error: Optional[str] = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "HorrorStoryGenerator/1.4",
                        "X-Webhook-Event": payload.get("event", "completed"),
                        "X-Webhook-Endpoint": payload.get("endpoint", "unknown"),
                    },
                )

                if 200 <= response.status_code < 300:
                    logger.info(
                        f"Sync webhook sent successfully to {url} "
                        f"(attempt {attempt + 1}/{max_retries}, status={response.status_code})"
                    )
                    return

                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    f"Sync webhook failed to {url} "
                    f"(attempt {attempt + 1}/{max_retries}): {last_error}"
                )

        except httpx.TimeoutException:
            last_error = f"Timeout after {timeout}s"
            logger.warning(
                f"Sync webhook timeout to {url} "
                f"(attempt {attempt + 1}/{max_retries})"
            )

        except httpx.RequestError as e:
            last_error = f"Request error: {str(e)}"
            logger.warning(
                f"Sync webhook request error to {url} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(
                f"Sync webhook unexpected error to {url} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        # Exponential backoff before retry
        if attempt < max_retries - 1:
            import time
            delay = min(
                WEBHOOK_RETRY_BASE_DELAY * (2 ** attempt),
                WEBHOOK_RETRY_MAX_DELAY
            )
            time.sleep(delay)

    logger.error(
        f"Sync webhook failed after {max_retries} attempts to {url}: {last_error}"
    )


def fire_and_forget_webhook(
    url: str,
    endpoint: str,
    status: str,
    result: Dict[str, Any],
) -> bool:
    """
    Send a webhook notification in fire-and-forget mode.

    This function returns immediately after spawning a background thread
    to send the webhook. The webhook is sent asynchronously and any
    errors are logged but do not affect the caller.

    Args:
        url: Webhook URL to POST to
        endpoint: The API endpoint path (e.g., "/research/run")
        status: Result status ("success" or "error")
        result: The response data to include in the webhook

    Returns:
        True if the webhook thread was started, False if url was empty
    """
    if not url:
        return False

    payload = build_sync_webhook_payload(endpoint, status, result)

    logger.info(f"Triggering fire-and-forget webhook to {url} for {endpoint}")

    # Start webhook in background thread
    thread = threading.Thread(
        target=_send_webhook_in_thread,
        args=(url, payload),
        daemon=True,  # Daemon thread won't prevent process exit
    )
    thread.start()

    return True
