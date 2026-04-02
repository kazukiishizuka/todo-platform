from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import build_task_service, get_repository
from app.schemas import ParseAndCreateResponse, TaskCreateRequest, TaskQueryResponse, TaskUpdateRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/parse-and-create", response_model=ParseAndCreateResponse)
def parse_and_create(payload: TaskCreateRequest, repository=Depends(get_repository)):
    return build_task_service(repository).parse_and_create(payload.userId, payload.channelType, payload.channelId, payload.text, payload.timezone)


@router.get("", response_model=TaskQueryResponse)
def list_tasks(user_id: str = Query(alias="userId"), scope: str | None = None, status: str | None = None, q: str | None = None, repository=Depends(get_repository)):
    from uuid import UUID

    return TaskQueryResponse(items=build_task_service(repository).list_tasks(UUID(user_id), status=status, scope=scope, q=q))


@router.patch("/{task_id}")
def update_task(task_id: str, payload: TaskUpdateRequest, repository=Depends(get_repository)):
    try:
        task = build_task_service(repository).update_task(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    return build_task_service(repository)._to_response(task)


@router.post("/{task_id}/complete")
def complete_task(task_id: str, repository=Depends(get_repository)):
    try:
        task = build_task_service(repository).complete_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    return build_task_service(repository)._to_response(task)


@router.delete("/{task_id}")
def delete_task(task_id: str, repository=Depends(get_repository)):
    try:
        task = build_task_service(repository).delete_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    return build_task_service(repository)._to_response(task)
