"""任务列表与批量创建 / 一键流水线 API。"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from app.api.deps import get_db
from app.core.exceptions import ApiError, success_response
from app.schemas.domain import OneClickPipelineRequest
from app.services.pipeline_service import get_pipeline_status, list_tasks, start_one_click_pipeline
from app.services.serializers import task_to_dict
from app.services.task_enqueue import enqueue_full_pipeline, enqueue_transcribe
from app.services.task_service import create_video_task

router = APIRouter()


@router.get("/tasks")
def tasks(limit: int = 50, db=Depends(get_db)) -> dict:
    return success_response(list_tasks(db, limit))


@router.post("/tasks/batch")
def batch_tasks(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    source_urls: str = Form(...),
    aspect_ratio: str = Form(default="9:16"),
) -> dict:
    """批量创建对标链接任务（并行转写，走分步流程）。"""
    urls = [item.strip() for item in source_urls.splitlines() if item.strip()]
    created = []
    for url in urls:
        task = create_video_task(db, None, url, aspect_ratio)
        enqueue_transcribe(background_tasks, task.id)
        created.append(task_to_dict(task))
    return success_response({"tasks": created, "count": len(created)})


@router.post("/pipelines/one-click")
def one_click(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    payload: str = Form(...),
    file: UploadFile | None = File(default=None),
    custom_voice_file: UploadFile | None = File(default=None),
) -> dict:
    """创建任务并异步执行一键追爆款流水线。"""
    import json

    request = OneClickPipelineRequest.model_validate(json.loads(payload))
    task = start_one_click_pipeline(db, request, file, custom_voice_file)
    options = request.model_dump(mode="json")
    options["await_config"] = task.pipeline_stage and task.pipeline_stage.get("stage") == "await_config"
    enqueue_full_pipeline(background_tasks, task.id, options)
    return success_response(task_to_dict(task))


@router.get("/tasks/{task_id}/pipeline-status")
def pipeline_status(task_id: str, db=Depends(get_db)) -> dict:
    return success_response(get_pipeline_status(db, task_id))
