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
    records = db.scalars(
        select(DistributionRecordModel)
        .where(DistributionRecordModel.task_id == task_id)
        .order_by(DistributionRecordModel.created_at.desc())
    ).all()
    return [distribution_to_dict(record) for record in records]


def create_distribution(db: Session, task_id: str, payload: CreateDistributionRequest) -> DistributionRecordModel:
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
    record = db.get(DistributionRecordModel, distribution_id)
    if not record:
        raise ApiError("NOT_FOUND", "分发记录不存在", 404)
    return record


def get_final_video_path(db: Session, task_id: str) -> str:
    artifact = db.scalar(
        select(ArtifactModel).where(ArtifactModel.task_id == task_id, ArtifactModel.type == ArtifactType.final_video.value)
    )
    if not artifact or not artifact.path:
        raise ApiError("VALIDATION_ERROR", "请先生成最终视频后再分发")
    return artifact.path
