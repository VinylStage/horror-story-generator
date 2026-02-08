"""
Recovery Manager for Task Scheduler.

From RECOVERY_SCENARIOS.md:
- Handles crash recovery on startup
- Cleans up orphaned RUNNING tasks
- Expires stale reservations
- Creates missing retry tasks

Recovery is idempotent: running multiple times produces same result.
"""

import logging
from datetime import datetime
from typing import Tuple

from .entities import (
    Task,
    TaskRun,
    TaskGroup,
    TaskStatus,
    TaskRunStatus,
    TaskGroupStatus,
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
    1. Crash during RUNNING task
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
        1. Handle orphaned RUNNING tasks
        2. Expire stale reservations
        3. Create missing retry tasks
        4. Verify queue integrity

        Returns:
            Recovery statistics
        """
        stats = {
            "running_tasks_recovered": 0,
            "reservations_expired": 0,
            "retries_created": 0,
            "task_groups_recovered": 0,
            "errors": [],
        }

        logger.info("Starting crash recovery...")

        # 1. Recover orphaned RUNNING tasks (Scenario 1)
        try:
            recovered = self._recover_running_tasks()
            stats["running_tasks_recovered"] = len(recovered)
        except Exception as e:
            logger.error(f"Error recovering RUNNING tasks: {e}")
            stats["errors"].append(f"Running tasks: {e}")

        # 2. Expire stale reservations (Scenario 2)
        try:
            expired = self._expire_stale_reservations()
            stats["reservations_expired"] = len(expired)
        except Exception as e:
            logger.error(f"Error expiring reservations: {e}")
            stats["errors"].append(f"Reservations: {e}")

        # 3. Create missing retry tasks (Scenario 3)
        try:
            retries = self.retry_controller.recover_orphaned_retries()
            stats["retries_created"] = len(retries)
        except Exception as e:
            logger.error(f"Error creating retry tasks: {e}")
            stats["errors"].append(f"Retries: {e}")

        # 4. Recover TaskGroups (DEC-012)
        try:
            groups_recovered = self._recover_task_groups()
            stats["task_groups_recovered"] = len(groups_recovered)
        except Exception as e:
            logger.error(f"Error recovering TaskGroups: {e}")
            stats["errors"].append(f"TaskGroups: {e}")

        logger.info(
            f"Recovery complete: "
            f"{stats['running_tasks_recovered']} running tasks recovered, "
            f"{stats['reservations_expired']} reservations expired, "
            f"{stats['retries_created']} retries created, "
            f"{stats['task_groups_recovered']} task groups recovered"
        )

        return stats

    def _recover_running_tasks(self) -> list[Tuple[Task, TaskRun]]:
        """
        Recover RUNNING tasks from crash.

        From RECOVERY_SCENARIOS.md Scenario 1:
        - Task RUNNING, no TaskRun -> Create FAILED TaskRun
        - Task RUNNING, TaskRun non-terminal -> Update to FAILED
        - Task RUNNING, TaskRun terminal -> Update Task.finished_at only

        Returns:
            List of (task, task_run) that were recovered
        """
        recovered = []
        now = datetime.utcnow().isoformat() + "Z"

        # Get all RUNNING tasks with their TaskRun status
        running_tasks = self.persistence.get_running_tasks_without_terminal_run()

        for task, task_run in running_tasks:
            logger.info(f"Recovering RUNNING task {task.task_id}")

            if task_run is None:
                # Crash before TaskRun creation
                logger.info(f"Task {task.task_id}: No TaskRun, creating FAILED record")

                task_run = TaskRun.create(
                    task_id=task.task_id,
                    params_snapshot=task.params,
                    template_id=task.template_id,
                )
                task_run = self.persistence.create_task_run(task_run)

                task_run = self.persistence.update_task_run(
                    task_run.run_id,
                    status=TaskRunStatus.FAILED,
                    finished_at=now,
                    error="Scheduler crash recovery",
                )

                # Update task status and finished_at
                self.persistence.update_task(
                    task.task_id, status=TaskStatus.FAILED, finished_at=now,
                )

            elif task_run.status is None or not task_run.is_terminal():
                # Crash during execution
                logger.info(
                    f"Task {task.task_id}: TaskRun non-terminal, marking FAILED"
                )

                task_run = self.persistence.update_task_run(
                    task_run.run_id,
                    status=TaskRunStatus.FAILED,
                    finished_at=now,
                    error="Scheduler crash recovery",
                )

                # Update task status and finished_at
                self.persistence.update_task(
                    task.task_id, status=TaskStatus.FAILED, finished_at=now,
                )

            else:
                # Crash after completion - update task status and finished_at
                logger.info(
                    f"Task {task.task_id}: TaskRun terminal ({task_run.status.value}), "
                    f"syncing task status"
                )

                from .dispatcher import _run_status_to_task_status
                task_status = _run_status_to_task_status(task_run.status)
                self.persistence.update_task(
                    task.task_id,
                    status=task_status,
                    finished_at=task_run.finished_at or now,
                )

            recovered.append((task, task_run))

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

    def _recover_task_groups(self) -> list[TaskGroup]:
        """
        Recover TaskGroups that may have inconsistent status.

        From DEC-012 and INV-006:
        - Recompute group status from member tasks
        - Handle groups that had tasks crash during execution

        This runs AFTER task recovery, so all RUNNING tasks have been handled.

        Returns:
            List of TaskGroups that were updated
        """
        recovered = []
        now = datetime.utcnow().isoformat() + "Z"

        # Get all non-terminal groups
        non_terminal_groups = self.persistence.get_non_terminal_groups()

        for group in non_terminal_groups:
            logger.info(f"Checking TaskGroup {group.group_id} status")

            # Recompute status from member tasks
            new_status = self.persistence.compute_group_status(group.group_id)

            if new_status != group.status:
                logger.info(
                    f"TaskGroup {group.group_id}: updating status "
                    f"{group.status.value} -> {new_status.value}"
                )

                # Update group with new status
                update_kwargs = {"status": new_status}

                # Set started_at if transitioning to RUNNING
                if group.started_at is None and new_status == TaskGroupStatus.RUNNING:
                    update_kwargs["started_at"] = now

                # Set finished_at if transitioning to terminal
                if new_status in (
                    TaskGroupStatus.COMPLETED,
                    TaskGroupStatus.PARTIAL,
                    TaskGroupStatus.CANCELLED,
                ):
                    update_kwargs["finished_at"] = now

                self.persistence.update_task_group(group.group_id, **update_kwargs)
                recovered.append(group)

            # Check for stop-on-failure: if any task failed without retry,
            # we need to cancel remaining tasks
            tasks_in_group = self.persistence.get_tasks_by_group(group.group_id)
            failed_without_retry = False

            for task in tasks_in_group:
                if task.finished_at is not None:
                    task_run = self.persistence.get_task_run_for_task(task.task_id)
                    if task_run and task_run.status == TaskRunStatus.FAILED:
                        # Check if a retry exists
                        retry_task = self.persistence.get_retry_task_for(task.task_id)
                        if retry_task is None:
                            failed_without_retry = True
                            break

            if failed_without_retry:
                # Cancel remaining QUEUED tasks
                for task in tasks_in_group:
                    if task.status == TaskStatus.QUEUED:
                        logger.info(
                            f"Recovery: cancelling task {task.task_id} "
                            f"in group {group.group_id} due to predecessor failure"
                        )
                        self.queue_manager.cancel(task.task_id)

                        # Create SKIPPED TaskRun
                        skipped_run = TaskRun.create(
                            task_id=task.task_id,
                            params_snapshot=task.params,
                            template_id=task.template_id,
                        )
                        skipped_run.status = TaskRunStatus.SKIPPED
                        skipped_run.finished_at = now
                        skipped_run.error = "Skipped: predecessor task failed (recovery)"
                        self.persistence.create_task_run(skipped_run)

                # Update group to PARTIAL
                self.persistence.update_task_group(
                    group.group_id,
                    status=TaskGroupStatus.PARTIAL,
                    finished_at=now,
                )

                if group not in recovered:
                    recovered.append(group)

        return recovered
