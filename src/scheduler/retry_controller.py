"""
Retry Controller for Job Scheduler.

From IMPLEMENTATION_PLAN.md Section 1.4 and DEC-007:
- Decides whether to create retry jobs
- Manages retry chain via retry_of field
- Automatic retry up to 3 attempts
- Manual retry always allowed via API

What RetryController MUST NOT do:
- Execute jobs
- Modify existing Jobs or JobRuns
- Override template's retry_policy
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .entities import (
    Job,
    JobRun,
    JobRunStatus,
    JobTemplate,
)
from .errors import (
    JobNotFoundError,
    JobRunNotFoundError,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager


logger = logging.getLogger(__name__)


# Default retry configuration (DEC-007)
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 10


class RetryController:
    """
    Manages automatic and manual retry logic.

    From DEC-007:
    - Failed jobs are automatically retried up to 3 attempts
    - Further retries require manual invocation
    - Retry creates NEW Job with retry_of reference

    Retry chain structure:
        Job1 (original)
          └── Job2 (retry_of: Job1)
                └── Job3 (retry_of: Job2)
                      └── Job4 (retry_of: Job3) ← max reached

    Backoff calculation:
        delay = base_delay * (2 ^ attempt_number)
        Example with 10s base: 10s → 20s → 40s
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_delay_seconds: int = DEFAULT_BASE_DELAY_SECONDS,
    ):
        """
        Initialize RetryController.

        Args:
            persistence: PersistenceAdapter for storage
            queue_manager: QueueManager for enqueueing retries
            max_attempts: Maximum automatic retry attempts
            base_delay_seconds: Base delay for exponential backoff
        """
        self.persistence = persistence
        self.queue_manager = queue_manager
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    # =========================================================================
    # Retry Evaluation
    # =========================================================================

    def on_job_failed(self, job: Job, job_run: JobRun) -> Optional[Job]:
        """
        Handle a failed job and potentially create a retry.

        Called by Dispatcher after job execution fails.

        From DEC-007:
        1. Count retry attempts in chain
        2. If attempts < max_attempts: create retry job
        3. If attempts >= max_attempts: no auto-retry

        Args:
            job: The failed job
            job_run: The failed JobRun

        Returns:
            The new retry Job if created, None otherwise
        """
        if job_run.status != JobRunStatus.FAILED:
            logger.debug(f"Job {job.job_id} is not failed, skipping retry evaluation")
            return None

        # Get retry policy from template or use default
        max_attempts = self._get_max_attempts(job)

        # Count attempts in retry chain
        attempt_count = self.persistence.count_retry_chain(job.job_id)

        logger.info(
            f"Retry evaluation for job {job.job_id}: "
            f"attempt {attempt_count + 1}/{max_attempts}"
        )

        if attempt_count >= max_attempts:
            logger.info(
                f"Job {job.job_id} has reached max retry attempts ({max_attempts}). "
                "No auto-retry. Manual retry via API still available."
            )
            return None

        # Calculate backoff delay
        delay = self._calculate_backoff(attempt_count)

        # Create retry job
        retry_job = self._create_retry_job(job, delay)

        logger.info(
            f"Created retry job {retry_job.job_id} for failed job {job.job_id} "
            f"(attempt {attempt_count + 2}/{max_attempts}, delay={delay}s)"
        )

        return retry_job

    def _get_max_attempts(self, job: Job) -> int:
        """Get max retry attempts from template or default."""
        if job.template_id is not None:
            template = self.persistence.get_template(job.template_id)
            if template is not None:
                retry_policy = template.retry_policy or {}
                return retry_policy.get("max_attempts", self.max_attempts)

        return self.max_attempts

    def _calculate_backoff(self, attempt_number: int) -> int:
        """
        Calculate exponential backoff delay.

        Formula: delay = base_delay * (2 ^ attempt_number)
        """
        return self.base_delay_seconds * (2 ** attempt_number)

    def _create_retry_job(self, original_job: Job, delay_seconds: int) -> Job:
        """
        Create a retry job from the original.

        The new job:
        - Has same template_id, params, job_type
        - Has retry_of = original_job_id
        - Is enqueued to QueueManager
        """
        # Create retry job with same parameters
        retry_job = self.queue_manager.enqueue(
            job_type=original_job.job_type,
            params=original_job.params,
            priority=original_job.priority,
            template_id=original_job.template_id,
            retry_of=original_job.job_id,
        )

        return retry_job

    # =========================================================================
    # Manual Retry
    # =========================================================================

    def manual_retry(self, run_id: str, priority: Optional[int] = None) -> Job:
        """
        Create a manual retry for a failed job run.

        From DEC-007:
        - Manual retry always allowed via POST /api/job-runs/{run_id}/retry
        - Creates new Job regardless of automatic retry count

        Args:
            run_id: The JobRun ID to retry
            priority: Optional priority for the retry job

        Returns:
            The new retry Job

        Raises:
            JobRunNotFoundError: If run_id doesn't exist
            InvalidOperationError: If JobRun is not FAILED
        """
        job_run = self.persistence.get_job_run(run_id)
        if job_run is None:
            raise JobRunNotFoundError(run_id)

        if job_run.status != JobRunStatus.FAILED:
            from .errors import InvalidOperationError
            raise InvalidOperationError(
                f"Cannot retry JobRun in {job_run.status.value} status. "
                "Only FAILED runs can be retried."
            )

        # Get the original job
        job = self.persistence.get_job(job_run.job_id)
        if job is None:
            raise JobNotFoundError(job_run.job_id)

        # Create retry job
        retry_job = self.queue_manager.enqueue(
            job_type=job.job_type,
            params=job_run.params_snapshot,  # Use snapshot from failed run
            priority=priority if priority is not None else job.priority,
            template_id=job.template_id,
            retry_of=job.job_id,
        )

        logger.info(
            f"Created manual retry job {retry_job.job_id} "
            f"for failed run {run_id} (job {job.job_id})"
        )

        return retry_job

    # =========================================================================
    # Retry Chain Queries
    # =========================================================================

    def get_retry_chain(self, job_id: str) -> list[Job]:
        """
        Get the full retry chain for a job.

        Returns jobs from original to most recent retry.
        """
        chain = []
        current = self.persistence.get_job(job_id)

        if current is None:
            return chain

        # Walk back to root
        while current is not None:
            chain.insert(0, current)
            if current.retry_of is not None:
                current = self.persistence.get_job(current.retry_of)
            else:
                break

        return chain

    def get_retry_count(self, job_id: str) -> int:
        """
        Get the number of retries for a job.

        Returns:
            Number of previous jobs in the retry chain
        """
        return self.persistence.count_retry_chain(job_id)

    def is_max_retries_reached(self, job: Job) -> bool:
        """
        Check if a job has reached maximum retry attempts.

        Args:
            job: The job to check

        Returns:
            True if max retries reached
        """
        max_attempts = self._get_max_attempts(job)
        attempt_count = self.persistence.count_retry_chain(job.job_id)
        return attempt_count >= max_attempts

    # =========================================================================
    # Recovery Support
    # =========================================================================

    def recover_orphaned_retries(self) -> list[Job]:
        """
        Create retry jobs for failed runs that don't have one.

        From RECOVERY_SCENARIOS.md Scenario 3:
        Used to recover from crash during retry creation.

        Returns:
            List of created retry jobs
        """
        created_retries = []

        # Find failed runs without retry jobs
        orphaned = self.persistence.get_failed_runs_without_retry(
            max_attempts=self.max_attempts
        )

        for job, job_run in orphaned:
            # Check if retry already exists (idempotency check)
            existing = self.persistence.get_retry_job_for(job.job_id)
            if existing is not None:
                continue

            # Calculate attempt number from chain
            attempt_count = self.persistence.count_retry_chain(job.job_id)

            if attempt_count >= self.max_attempts:
                logger.info(
                    f"Job {job.job_id} at max retries, skipping recovery retry"
                )
                continue

            # Create recovery retry
            delay = self._calculate_backoff(attempt_count)
            retry_job = self._create_retry_job(job, delay)

            logger.info(
                f"Recovery: created retry job {retry_job.job_id} "
                f"for orphaned failed job {job.job_id}"
            )

            created_retries.append(retry_job)

        return created_retries
