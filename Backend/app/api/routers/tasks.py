"""视频任务 HTTP 路由（流程入口与生成触发）。

对应主链路：
- POST /tasks/video：上传参考视频 → 创建任务 → 异步 ASR（transcribe_video_task）；
- POST /tasks/script：粘贴文案创建任务；
- POST .../generation-config：保存生成参数；
- POST .../generate / retry：校验后投递 Celery run_generation_pipeline。
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import ApiError, success_response
from app.schemas.domain import CreateScriptTaskRequest, GeneratePublishMetadataRequest, RewriteScriptRequest, SaveGenerationConfigRequest
from app.domain.enums import GenerationVideoMode, GenerationVoiceMode, TaskStatus
from app.services.rewrite_service import generate_publish_metadata, rewrite_script
from app.services.serializers import task_to_dict
from app.services.storage_service import save_upload
from app.services.task_enqueue import enqueue_transcribe, enqueue_generation
from app.services.task_service import (
    create_script_task,
    create_video_task,
    ensure_task,
    mark_generation_started,
    prepare_for_generation,
    resolve_source_video_file,
    retry_task,
    save_generation_config,
)
from app.services.task_guards import assert_not_in_generation

router = APIRouter()


@router.post("/tasks/video")
def create_video(
    background_tasks: BackgroundTasks,
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
        create_video_task 落库后立即返回；transcribe_video_task 在后台执行。
    """
    task = create_video_task(db, file, source_url, aspect_ratio)
    enqueue_transcribe(background_tasks, task.id)
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


@router.post("/tasks/{task_id}/retranscribe")
def retranscribe(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """重新下载/识别参考视频文案。"""
    task = ensure_task(db, task_id)
    if task.script_source != "video_asr":
        raise ApiError("VALIDATION_ERROR", "仅视频任务支持重新识别")
    assert_not_in_generation(task, "重新识别")
    task.status = TaskStatus.uploaded.value
    task.error_code = None
    task.error_message = None
    db.commit()
    enqueue_transcribe(background_tasks, task_id)
    task = ensure_task(db, task_id)
    return success_response(task_to_dict(task))


@router.get("/tasks/{task_id}/source-video")
def source_video_preview(task_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """流式返回任务参考视频（本地转存后），供文案页预览。"""
    task = ensure_task(db, task_id)
    video_path = resolve_source_video_file(task)
    if not video_path:
        raise ApiError("NOT_FOUND", "参考视频尚未就绪或仍为远程链接", 404)
    return FileResponse(video_path, media_type="video/mp4", filename=video_path.name)


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
    try:
        payload = SaveGenerationConfigRequest.model_validate(json.loads(config))
    except json.JSONDecodeError as exc:
        raise ApiError("VALIDATION_ERROR", "配置 JSON 格式无效", 400) from exc
    task = save_generation_config(db, task_id, payload)
    if custom_voice_file and payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value:
        task.custom_voice_path = save_upload(task_id, custom_voice_file, "custom_voice")
    if custom_video_file and payload.generation_video_mode == GenerationVideoMode.uploaded_video.value:
        task.custom_video_path = save_upload(task_id, custom_video_file, "custom_video")
    db.commit()
    db.refresh(task)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/generate")
def generate(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """开始视频生成流水线。

    用途：
        配置就绪且内容风险已处理后，触发 Celery 配音→数字人→合成。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        status 已变为 dubbing 的任务 dict。

    逻辑：
        start_generate 校验风险状态后异步投递 run_generation_pipeline。
    """
    task = prepare_for_generation(db, task_id)
    enqueue_generation(background_tasks, task_id)
    task = mark_generation_started(db, task_id)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/retry")
def retry(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """重试失败的生成流水线。

    用途：
        生成失败后清空错误并重新投递 Celery。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        status=retrying 的任务 dict。

    逻辑：
        retry_task 后异步投递 run_generation_pipeline。
    """
    task = retry_task(db, task_id)
    enqueue_generation(background_tasks, task_id)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/rewrite-script")
def rewrite(task_id: str, payload: RewriteScriptRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(
        rewrite_script(db, task_id, payload.mode, payload.instruction, payload.style)
    )


@router.post("/tasks/{task_id}/generate-publish-metadata")
def publish_metadata(task_id: str, payload: GeneratePublishMetadataRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(generate_publish_metadata(db, task_id, payload.platform, payload.tone))
