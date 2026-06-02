"""视频分发（多平台发布）服务。

在 Celery 生成流水线产出 final_video 后，用户创建 DistributionRecord，
由 run_distribution_task 异步执行平台上架；本模块负责记录 CRUD 与成片路径校验。
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.db.models import ArtifactModel, DistributionRecordModel
from app.domain.enums import ArtifactType
from app.schemas.domain import CreateDistributionRequest
from app.services.id_service import create_id
from app.services.serializers import distribution_to_dict


def list_distributions(db: Session, task_id: str) -> list[dict]:
    """查询任务下全部分发记录。

    用途：
        分发历史列表 API。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        分发记录 dict 列表，按 created_at 降序。

    逻辑：
        查询 DistributionRecordModel 后 distribution_to_dict。
    """
    records = db.scalars(
        select(DistributionRecordModel)
        .where(DistributionRecordModel.task_id == task_id)
        .order_by(DistributionRecordModel.created_at.desc())
    ).all()
    return [distribution_to_dict(record) for record in records]


def create_distribution(db: Session, task_id: str, payload: CreateDistributionRequest) -> DistributionRecordModel:
    """创建待执行的分发记录。

    用途：
        POST distributions 后由 Celery run_distribution_task 异步发布。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。
        payload: 平台、标题、简介、标签等。

    返回：
        status=pending 的 DistributionRecordModel（已 commit）。

    逻辑：
        get_final_video_path 校验成片存在；raw_result 写入 final_video_path 供 worker 使用。
    """
    final_video = get_final_video_path(db, task_id)
    record = DistributionRecordModel(
        id=create_id("dist"),
        task_id=task_id,
        platform=payload.platform,
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        status="pending",
        raw_result={"final_video_path": final_video},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_distribution(db: Session, distribution_id: str) -> DistributionRecordModel:
    """按 ID 加载分发记录。

    用途：
        分发重试等需定位单条记录的场景。

    参数：
        db: 数据库会话。
        distribution_id: 分发记录 ID。

    返回：
        DistributionRecordModel 实例。

    逻辑：
        db.get，缺失抛 NOT_FOUND。
    """
    record = db.get(DistributionRecordModel, distribution_id)
    if not record:
        raise ApiError("NOT_FOUND", "分发记录不存在", 404)
    return record


def get_final_video_path(db: Session, task_id: str) -> str:
    """解析任务最终成片在存储中的路径。

    用途：
        创建分发前确保流水线已产出 final_video 类型产物。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        成片文件路径字符串。

    逻辑：
        查询 type=final_video 的 ArtifactModel，无 path 则 VALIDATION_ERROR。
    """
    artifact = db.scalar(
        select(ArtifactModel).where(ArtifactModel.task_id == task_id, ArtifactModel.type == ArtifactType.final_video.value)
    )
    if not artifact or not artifact.path:
        raise ApiError("VALIDATION_ERROR", "请先生成最终视频后再分发")
    return artifact.path
