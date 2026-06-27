"""Celery 应用配置与实例。

用途：
    创建全局 celery_app，供 tasks 模块注册 @celery_app.task 装饰的任务。
    Broker 与 Result Backend 均使用 Redis，与 FastAPI 主进程解耦。

参数（来自 Settings）：
    redis_url: Redis 连接串，同时作为 message broker 与结果存储。

逻辑：
    1. 读取配置，实例化 Celery("digital_human")。
    2. include 指定任务模块 app.workers.tasks，Worker 启动时自动加载。
    3. 开启 task_track_started、JSON 序列化，便于前端轮询任务进度。
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "digital_human",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_conf = {
    "task_track_started": True,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
}
# 本地桌面模式：任务在 API 进程内同步执行，省去 Redis 与 Celery Worker
if settings.local_desktop_mode:
    celery_conf.update(task_always_eager=True, task_eager_propagates=True)
celery_app.conf.update(**celery_conf)
