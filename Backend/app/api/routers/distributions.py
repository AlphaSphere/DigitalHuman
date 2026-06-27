"""多平台分发 HTTP 路由。

成片生成完成后创建分发记录，由 Celery run_distribution_task 异步上架；
支持查询历史与失败重试。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import BatchDistributionRequest, CreateDistributionRequest
from app.services.distribution_service import (
    create_batch_distributions,
    create_distribution,
    get_distribution,
    list_distributions,
)
from app.services.serializers import distribution_to_dict
from app.workers.tasks import run_distribution_task

router = APIRouter()


@router.get("/tasks/{task_id}/distributions")
def distributions(task_id: str, db: Session = Depends(get_db)) -> dict:
    """查询任务下全部分发记录。

    用途：
        展示各平台上架状态、外链与错误信息。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        分发记录 dict 数组。

    逻辑：
        list_distributions 按时间降序。
    """
    return success_response(list_distributions(db, task_id))


@router.post("/tasks/{task_id}/distributions")
def create(task_id: str, payload: CreateDistributionRequest, db: Session = Depends(get_db)) -> dict:
    """创建分发任务并异步执行平台上架。

    用途：
        用户提交平台、标题、标签等后进入 pending，由 worker 上传成片。

    参数：
        task_id: 任务 ID。
        payload: CreateDistributionRequest。
        db: 数据库会话。

    返回：
        新建分发记录 dict。

    逻辑：
        create_distribution 校验 final_video 存在后 run_distribution_task.delay(record.id)。
    """
    record = create_distribution(db, task_id, payload)
    run_distribution_task.delay(record.id)
    return success_response(distribution_to_dict(record))


@router.post("/tasks/{task_id}/distributions/batch")
def create_batch(task_id: str, payload: BatchDistributionRequest, db: Session = Depends(get_db)) -> dict:
    ids = create_batch_distributions(
        db,
        task_id,
        payload.platforms,
        payload.title,
        payload.description,
        payload.tags,
        payload.cover_artifact_id,
    )
    from app.workers.tasks import run_batch_distribution_task

    run_batch_distribution_task.delay(task_id, ids)
    return success_response({"distribution_ids": ids, "count": len(ids)})


@router.post("/distributions/{distribution_id}/retry")
def retry(distribution_id: str, db: Session = Depends(get_db)) -> dict:
    """重试失败或中断的分发任务。

    用途：
        将记录重置为 pending 并重新投递 Celery。

    参数：
        distribution_id: 分发记录 ID。
        db: 数据库会话。

    返回：
        更新后的分发记录 dict。

    逻辑：
        清空 error_message、status=pending、commit 后 delay 同一 distribution id。
    """
    record = get_distribution(db, distribution_id)
    record.status = "pending"
    record.error_message = None
    db.commit()
    db.refresh(record)
    run_distribution_task.delay(record.id)
    return success_response(distribution_to_dict(record))
