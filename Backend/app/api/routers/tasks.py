"""视频任务 HTTP 路由（流程入口与生成触发）。

对应主链路：
- POST /tasks/video：上传参考视频 → 创建任务 → 异步 ASR（transcribe_video_task）；
- POST /tasks/script：粘贴文案创建任务；
- POST .../generation-config：保存生成参数；
- POST .../generate / retry：校验后投递 Celery run_generation_pipeline。
"""

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import CreateScriptTaskRequest, SaveGenerationConfigRequest
from app.services.serializers import task_to_dict
from app.services.storage_service import save_upload
from app.services.task_service import (
    create_script_task,
    create_video_task,
    ensure_task,
    retry_task,
    save_generation_config,
    start_generate,
)
from app.workers.tasks import run_generation_pipeline, transcribe_video_task

router = APIRouter()


@router.post("/tasks/video")
def create_video(
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
    aspect_ratio: str = Form(default="9:16"),
) -> dict:
    """创建参考视频任务并触发异步 ASR。

    用途：
        用户上传本地视频或提交链接，启动「视频 → 文案」流程第一步。

    参数：
        db: 注入的数据库会话。
        file: 可选，multipart 视频文件。
        source_url: 可选，远程视频 URL。
        aspect_ratio: 画幅，表单字段，默认 9:16。

    返回：
        success_response 包裹的任务 dict（不含 progress）。

    逻辑：
        create_video_task 落库后 transcribe_video_task.delay(task.id)。
    """
    task = create_video_task(db, file, source_url, aspect_ratio)
    transcribe_video_task.delay(task.id)
    return success_response(task_to_dict(task))


@router.post("/tasks/script")
def create_script(payload: CreateScriptTaskRequest, db: Session = Depends(get_db)) -> dict:
    """通过粘贴字幕/文案创建任务。

    用途：
        跳过视频 ASR，直接进入脚本编辑与风险审核流程。

    参数：
        payload: JSON 请求体 CreateScriptTaskRequest。
        db: 数据库会话。

    返回：
        新建任务的 task dict。

    逻辑：
        调用 create_script_task，同步返回，无 Celery 投递。
    """
    return success_response(task_to_dict(create_script_task(db, payload)))


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    """查询单个任务详情。

    用途：
        前端轮询任务状态、展示生成配置与错误信息。

    参数：
        task_id: 路径参数任务 ID。
        db: 数据库会话。

    返回：
        task_to_dict 结果。

    逻辑：
        ensure_task 校验存在后序列化返回。
    """
    return success_response(task_to_dict(ensure_task(db, task_id)))


@router.post("/tasks/{task_id}/generation-config")
def save_config(
    task_id: str,
    config: str = Form(...),
    custom_voice_file: UploadFile | None = File(default=None),
    custom_video_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """保存生成配置并可选上传自定义音色/视频文件。

    用途：
        脚本与风险通过后，提交配音、形象、字幕、背景音乐等参数。

    参数：
        task_id: 任务 ID。
        config: JSON 字符串，反序列化为 SaveGenerationConfigRequest。
        custom_voice_file: 可选音色样本上传。
        custom_video_file: 可选口播视频素材上传。
        db: 数据库会话。

    返回：
        更新后的任务 dict。

    逻辑：
        save_generation_config 写库；若有上传文件则 save_upload 覆盖 path 并二次 commit。
    """
    payload = SaveGenerationConfigRequest.model_validate(json.loads(config))
    task = save_generation_config(db, task_id, payload)
    if custom_voice_file:
        task.custom_voice_path = save_upload(task_id, custom_voice_file, "custom_voice")
    if custom_video_file:
        task.custom_video_path = save_upload(task_id, custom_video_file, "custom_video")
    db.commit()
    db.refresh(task)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/generate")
def generate(task_id: str, db: Session = Depends(get_db)) -> dict:
    """开始视频生成流水线。

    用途：
        配置就绪且内容风险已处理后，触发 Celery 配音→数字人→合成。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        status 已变为 dubbing 的任务 dict。

    逻辑：
        start_generate 校验风险状态后 run_generation_pipeline.delay(task_id)。
    """
    task = start_generate(db, task_id)
    run_generation_pipeline.delay(task_id)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/retry")
def retry(task_id: str, db: Session = Depends(get_db)) -> dict:
    """重试失败的生成流水线。

    用途：
        生成失败后清空错误并重新投递 Celery。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        status=retrying 的任务 dict。

    逻辑：
        retry_task 后 run_generation_pipeline.delay(task_id)。
    """
    task = retry_task(db, task_id)
    run_generation_pipeline.delay(task_id)
    return success_response(task_to_dict(task))
