"""
Tasks router for task management API.

Phase 3+: Scheduler-based task execution model.
Renamed from jobs.py; /jobs endpoints kept as deprecated aliases.

Endpoints:
- POST /tasks - Create task(s). Always accepts an array of TaskCreateRequest.
- GET /tasks - List tasks
- GET /tasks/{task_id} - Get task details
- PATCH /tasks/{task_id} - Update task priority
- DELETE /tasks/{task_id} - Cancel task
- GET /tasks/{task_id}/runs - Get task execution history
- POST /tasks/group - Create concurrent execution group
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..schemas.scheduler import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskResponse,
    TaskListResponse,
    TaskBatchResponse,
    TaskDeleteResponse,
    TaskRunResponse,
    TaskRunListResponse,
    TaskGroupCreateRequest,
    TaskGroupResponse,
)
from .._scheduler_state import get_scheduler_service

router = APIRouter()


def _task_to_response(task) -> TaskResponse:
    """Convert scheduler Task entity to API response."""
    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value if hasattr(task.status, 'value') else task.status,
        params=task.params,
        priority=task.priority,
        position=task.position,
        template_id=task.template_id,
        group_id=task.group_id,
        retry_of=task.retry_of,
        created_at=task.created_at,
        queued_at=task.queued_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def _task_run_to_response(task_run) -> TaskRunResponse:
    return TaskRunResponse(
        run_id=task_run.run_id,
        task_id=task_run.task_id,
        status=task_run.status.value if task_run.status and hasattr(task_run.status, 'value') else task_run.status,
        params_snapshot=task_run.params_snapshot,
        template_id=task_run.template_id,
        started_at=task_run.started_at,
        finished_at=task_run.finished_at,
        exit_code=task_run.exit_code,
        error=task_run.error,
        artifacts=task_run.artifacts,
        log_path=task_run.log_path,
    )


# POST /tasks - Create task(s). Always accepts an array.
@router.post("", response_model=TaskBatchResponse, status_code=201)
async def create_tasks(requests: List[TaskCreateRequest]):
    """
    Create task(s).

    Accepts an array of task specifications (story, research, or mixed).
    Always returns a TaskBatchResponse with the list of created tasks.

    **Single task:**
    ```json
    [{"type": "story", "params": {"topic": "Korean horror"}, "priority": 0}]
    ```

    **Multiple tasks (mixed types):**
    ```json
    [
        {"type": "story", "params": {"topic": "Apartment horror"}, "priority": 0},
        {"type": "research", "params": {"topic": "Urban legends"}, "priority": 10}
    ]
    ```
    """
    if not requests:
        raise HTTPException(status_code=422, detail="At least one task is required.")
    service = get_scheduler_service()
    try:
        created = []
        for req in requests:
            task = service.enqueue_task(
                task_type=req.type,
                params=req.params,
                priority=req.priority,
            )
            created.append(_task_to_response(task))
        return TaskBatchResponse(tasks=created, total=len(created))
    except Exception as e:
        if "validation" in str(type(e).__name__).lower():
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create tasks: {str(e)}")


# POST /tasks/group - Create concurrent execution group
@router.post("/group", response_model=TaskGroupResponse, status_code=201)
async def create_task_group(request: TaskGroupCreateRequest):
    """Create a concurrent execution group from existing QUEUED tasks."""
    service = get_scheduler_service()

    try:
        group, tasks = service.create_concurrent_group(
            task_ids=request.task_ids,
            name=request.name,
        )

        return TaskGroupResponse(
            group_id=group.group_id,
            name=group.name,
            status=group.status.value,
            execution_mode=group.execution_mode,
            tasks=[_task_to_response(t) for t in tasks],
            created_at=group.created_at,
            started_at=group.started_at,
            finished_at=group.finished_at,
        )
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        elif "invalid" in error_msg.lower() or "cannot" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=500, detail=f"Failed to create group: {error_msg}")


# GET /tasks
@router.get("", response_model=TaskListResponse)
async def list_tasks(limit: int = Query(default=50, ge=1, le=200)):
    """List all tasks with queue statistics."""
    service = get_scheduler_service()
    try:
        tasks = service.list_all_tasks(limit=limit)
        stats = service.get_queue_stats()
        return TaskListResponse(
            tasks=[_task_to_response(t) for t in tasks],
            total=len(tasks),
            queued_count=stats["queued_count"],
            running_count=stats["running_count"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


# GET /tasks/{task_id}
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task details by ID."""
    service = get_scheduler_service()
    try:
        task = service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return _task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


# PATCH /tasks/{task_id}
@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update task priority (QUEUED tasks only)."""
    service = get_scheduler_service()
    if request.priority is None:
        raise HTTPException(status_code=400, detail="No update fields provided.")
    try:
        task = service.update_task_priority(task_id, request.priority)
        return _task_to_response(task)
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        elif "cannot" in error_msg.lower() or "invalid" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=500, detail=f"Failed to update task: {error_msg}")


# DELETE /tasks/{task_id}
@router.delete("/{task_id}", response_model=TaskDeleteResponse)
async def delete_task(task_id: str):
    """Cancel a task (QUEUED tasks only)."""
    service = get_scheduler_service()
    try:
        task = service.cancel_task(task_id)
        return TaskDeleteResponse(
            task_id=task_id,
            success=True,
            message=f"Task cancelled successfully (status: {task.status.value})",
        )
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        elif "cannot cancel" in error_msg.lower() or "invalid" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {error_msg}")


# GET /tasks/{task_id}/runs
@router.get("/{task_id}/runs", response_model=TaskRunListResponse)
async def get_task_runs(task_id: str):
    """Get execution history (TaskRuns) for a task."""
    service = get_scheduler_service()
    try:
        task = service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        task_run = service.get_task_run_for_task(task_id)
        runs = [_task_run_to_response(task_run)] if task_run else []
        return TaskRunListResponse(runs=runs, total=len(runs))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task runs: {str(e)}")
