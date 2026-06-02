"""数字人与音色配置档案查询服务。

在「生成配置」阶段为前端提供可选的 voice_profile / avatar_profile 列表，
用户选定后写入 TaskModel 并进入 Celery 生成流水线。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AvatarProfileModel, VoiceProfileModel
from app.services.serializers import avatar_profile_to_dict, voice_profile_to_dict


def list_voice_profiles(db: Session) -> list[dict]:
    """列出全部可用音色档案。

    用途：
        生成配置页展示 TTS/克隆音色选项。

    参数：
        db: SQLAlchemy 数据库会话。

    返回：
        音色档案 dict 列表（经 voice_profile_to_dict 序列化）。

    逻辑：
        全表查询 VoiceProfileModel，逐条转为 API 友好结构。
    """
    return [voice_profile_to_dict(item) for item in db.scalars(select(VoiceProfileModel)).all()]


def list_avatar_profiles(db: Session) -> list[dict]:
    """列出全部可用数字人形象档案。

    用途：
        生成配置页展示口播数字人/形象选项。

    参数：
        db: SQLAlchemy 数据库会话。

    返回：
        形象档案 dict 列表（经 avatar_profile_to_dict 序列化）。

    逻辑：
        全表查询 AvatarProfileModel，逐条转为 API 友好结构。
    """
    return [avatar_profile_to_dict(item) for item in db.scalars(select(AvatarProfileModel)).all()]
