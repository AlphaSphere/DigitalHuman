"""
用途：应用启动时的数据种子逻辑，写入默认音色与数字人预设，保证 profiles 接口开箱可用。
"""

from sqlalchemy.orm import Session

from app.db.models import AvatarProfileModel, VoiceProfileModel


DEFAULT_VOICES = [
    VoiceProfileModel(
        id="voice_default_female",
        name="默认中文女声",
        provider="cozyvoice",
        sample_path="storage/voices/default_female.wav",
        config={"speed": 1, "volume": 1, "description": "清晰、稳定，适合知识口播。"},
    ),
    VoiceProfileModel(
        id="voice_default_male",
        name="默认中文男声",
        provider="cozyvoice",
        sample_path="storage/voices/default_male.wav",
        config={"speed": 0.96, "volume": 1, "description": "低沉、有信任感，适合讲解类内容。"},
    ),
]

DEFAULT_AVATARS = [
    AvatarProfileModel(
        id="avatar_studio_a",
        name="默认数字人 A",
        provider="heygem",
        config={
            "resolution": "1080x1920",
            "template_path": "storage/avatars/studio_a",
            "description": "竖屏半身口播，适合短视频平台。",
        },
    ),
    AvatarProfileModel(
        id="avatar_studio_b",
        name="默认数字人 B",
        provider="heygem",
        config={
            "resolution": "1920x1080",
            "template_path": "storage/avatars/studio_b",
            "description": "横屏课程讲解，适合知识视频。",
        },
    ),
]


def seed_profiles(db: Session) -> None:
    """
    用途：幂等插入默认 voice/avatar 配置，在 lifespan 启动阶段调用。

    参数：
        db: 已打开的数据库 Session

    逻辑：
        1. 遍历 DEFAULT_VOICES / DEFAULT_AVATARS，按主键 id 查询是否已存在
        2. 不存在则 add，全部检查后 commit 一次
    """
    for voice in DEFAULT_VOICES:
        if not db.get(VoiceProfileModel, voice.id):
            db.add(voice)
    for avatar in DEFAULT_AVATARS:
        if not db.get(AvatarProfileModel, avatar.id):
            db.add(avatar)
    db.commit()
