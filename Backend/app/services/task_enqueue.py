"""任务异步投递：桌面 BackgroundTasks / 生产 Celery 统一入口。"""

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.workers.tasks import run_full_pipeline_task, run_generation_pipeline, transcribe_video_task


def enqueue_transcribe(background_tasks: BackgroundTasks, task_id: str) -> None:
    settings = get_settings()
    if settings.local_desktop_mode:
        background_tasks.add_task(transcribe_video_task.run, task_id)
        return
    transcribe_video_task.delay(task_id)


def enqueue_generation(background_tasks: BackgroundTasks, task_id: str) -> None:
    settings = get_settings()
    if settings.local_desktop_mode:
        background_tasks.add_task(run_generation_pipeline.run, task_id)
        return
    run_generation_pipeline.delay(task_id)


def enqueue_full_pipeline(background_tasks: BackgroundTasks, task_id: str, options: dict) -> None:
    settings = get_settings()
    if settings.local_desktop_mode:
        background_tasks.add_task(run_full_pipeline_task.run, task_id, options)
        return
    run_full_pipeline_task.delay(task_id, options)
