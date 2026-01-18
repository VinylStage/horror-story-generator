"""
Recovery Manager for Job Scheduler.

From RECOVERY_SCENARIOS.md:
- Handles crash recovery on startup
- Cleans up orphaned RUNNING jobs
- Expires stale reservations
- Creates missing retry jobs

Recovery is idempotent: running multiple times produces same result.
"""

import logging
from datetime import datetime
from typing import Tuple

from .entities import (
    Job,
    JobRun,
    JobStatus,
    JobRunStatus,
    ReservationStatus,
)
from .persistence import PersistenceAdapter
from .queue_manager import QueueManager
from .retry_controller import RetryController


logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Handles crash recovery and startup cleanup.

    Recovery scenarios from RECOVERY_SCENARIOS.md:
    1. Crash during RUNNING job
    2. Crash during Direct API reservation
    3. Crash during retry creation

    All recovery operations are idempotent.
    """

    def __init__(
        self,
        persistence: PersistenceAdapter,
        queue_manager: QueueManager,
        retry_controller: RetryController,
    ):
        """
        Initialize RecoveryManager.

        Args:
            persistence: PersistenceAdapter for storage
            queue_manager: QueueManager for queue operations
            retry_controller: RetryController for retry creation
        """
        self.persistence = persistence
        self.queue_manager = queue_manager
        self.retry_controller = retry_controller

    def recover_on_startup(self) -> dict:
        """
        Perform full recovery on scheduler startup.

        From DEC-008 and RECOVERY_SCENARIOS.md:
        1. Handle orphaned RUNNING jobs
        2. Expire stale reservations
        3. Create missing retry jobs
        4. Verify queue integrity

        Returns:
            Recovery statistics
        """
        stats = {
            "running_jobs_recovered": 0,
            "reservations_expired": 0,
            "retries_created": 0,
            "errors": [],
        }

        logger.info("Starting crash recovery...")

        # 1. Recover orphaned RUNNING jobs (Scenario 1)
        try:
            recovered = self._recover_running_jobs()
            stats["running_jobs_recovered"] = len(recovered)
        except Exception as e:
            logger.error(f"Error recovering RUNNING jobs: {e}")
            stats["errors"].append(f"Running jobs: {e}")

        # 2. Expire stale reservations (Scenario 2)
        try:
            expired = self._expire_stale_reservations()
            stats["reservations_expired"] = len(expired)
        except Exception as e:
            logger.error(f"Error expiring reservations: {e}")
            stats["errors"].append(f"Reservations: {e}")

        # 3. Create missing retry jobs (Scenario 3)
        try:
            retries = self.retry_controller.recover_orphaned_retries()
            stats["retries_created"] = len(retries)
        except Exception as e:
            logger.error(f"Error creating retry jobs: {e}")
            stats["errors"].append(f"Retries: {e}")

        logger.info(
            f"Recovery complete: "
            f"{stats['running_jobs_recovered']} running jobs recovered, "
            f"{stats['reservations_expired']} reservations expired, "
            f"{stats['retries_created']} retries created"
        )

        return stats

    def _recover_running_jobs(self) -> list[Tuple[Job, JobRun]]:
        """
        Recover RUNNING jobs from crash.

        From RECOVERY_SCENARIOS.md Scenario 1:
        - Job RUNNING, no JobRun → Create FAILED JobRun
        - Job RUNNING, JobRun non-terminal → Update to FAILED
        - Job RUNNING, JobRun terminal → Update Job.finished_at only

        Returns:
            List of (job, job_run) that were recovered
        """
        recovered = []
        now = datetime.utcnow().isoformat() + "Z"

        # Get all RUNNING jobs with their JobRun status
        running_jobs = self.persistence.get_running_jobs_without_terminal_run()

        for job, job_run in running_jobs:
            logger.info(f"Recovering RUNNING job {job.job_id}")

            if job_run is None:
                # Crash before JobRun creation
                logger.info(f"Job {job.job_id}: No JobRun, creating FAILED record")

                job_run = JobRun.create(
                    job_id=job.job_id,
                    params_snapshot=job.params,
                    template_id=job.template_id,
                )
                job_run = self.persistence.create_job_run(job_run)

                job_run = self.persistence.update_job_run(
                    job_run.run_id,
                    status=JobRunStatus.FAILED,
                    finished_at=now,
                    error="Scheduler crash recovery",
                )

                # Update job finished_at
                self.persistence.update_job(job.job_id, finished_at=now)

            elif job_run.status is None or not job_run.is_terminal():
                # Crash during execution
                logger.info(
                    f"Job {job.job_id}: JobRun non-terminal, marking FAILED"
                )

                job_run = self.persistence.update_job_run(
                    job_run.run_id,
                    status=JobRunStatus.FAILED,
                    finished_at=now,
                    error="Scheduler crash recovery",
                )

                # Update job finished_at
                self.persistence.update_job(job.job_id, finished_at=now)

            else:
                # Crash after completion - just update job finished_at
                logger.info(
                    f"Job {job.job_id}: JobRun terminal, updating finished_at only"
                )

                self.persistence.update_job(
                    job.job_id,
                    finished_at=job_run.finished_at or now,
                )

            recovered.append((job, job_run))

        return recovered

    def _expire_stale_reservations(self) -> list[str]:
        """
        Expire ACTIVE reservations from crash.

        From RECOVERY_SCENARIOS.md Scenario 2:
        All ACTIVE reservations on startup are stale (crash means no handler).

        Returns:
            List of expired reservation IDs
        """
        expired_ids = []

        active_reservations = self.persistence.get_active_reservations_for_recovery()

        for reservation in active_reservations:
            logger.info(
                f"Expiring stale reservation {reservation.reservation_id} "
                f"(reserved by: {reservation.reserved_by})"
            )

            self.queue_manager.expire_reservation(reservation.reservation_id)
            expired_ids.append(reservation.reservation_id)

        return expired_ids
