"""Celery 异步 Worker 包。

本包定义 Celery 应用实例与具体任务函数，在 Redis 队列上执行耗时的
转写、生成、分发流水线。任务内通过 adapters 调用外部 AI 与媒体工具，
并通过 SQLAlchemy 更新 TaskModel 状态与 Artifact 记录。
"""
