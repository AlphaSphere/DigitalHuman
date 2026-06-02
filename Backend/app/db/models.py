"""
用途：数字人业务核心 ORM 模型定义，映射 tasks、脚本片段、产物、风控与分发等持久化表。
"""

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TaskModel(Base, TimestampMixin):
    """用途：视频生成任务主表，承载状态、生成配置、错误信息与一对多关联实体。"""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    script_source: Mapped[str] = mapped_column(String(32), nullable=False)
    script_generation_mode: Mapped[str | None] = mapped_column(String(32), default="full_script")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_video_path: Mapped[str | None] = mapped_column(String(512))
    duration: Mapped[float | None] = mapped_column(Float)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    generation_voice_mode: Mapped[str | None] = mapped_column(String(32))
    custom_voice_path: Mapped[str | None] = mapped_column(String(512))
    generation_video_mode: Mapped[str | None] = mapped_column(String(32))
    custom_video_path: Mapped[str | None] = mapped_column(String(512))
    voice_profile_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("voice_profiles.id"))
    avatar_profile_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("avatar_profiles.id"))
    subtitle_style: Mapped[dict | None] = mapped_column(JSON)
    background_music_path: Mapped[str | None] = mapped_column(String(512))
    background_music_volume: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))

    segments: Mapped[list["ScriptSegmentModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    risk_checks: Mapped[list["RiskCheckModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    authorization_records: Mapped[list["AuthorizationRecordModel"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    distribution_records: Mapped[list["DistributionRecordModel"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class ScriptSegmentModel(Base):
    """用途：任务下的脚本/字幕片段，支持 ASR 时间轴与用户编辑文本。"""

    __tablename__ = "script_segments"
    __table_args__ = (UniqueConstraint("task_id", "index", name="uq_script_segments_task_index"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_time: Mapped[float | None] = mapped_column(Float)
    end_time: Mapped[float | None] = mapped_column(Float)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    task: Mapped[TaskModel] = relationship(back_populates="segments")


class ArtifactModel(Base):
    """用途：任务流水线产生的文件型产物记录（音视频、字幕、成片等）及元数据。"""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    path: Mapped[str | None] = mapped_column(String(512))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)

    task: Mapped[TaskModel] = relationship(back_populates="artifacts")


class VoiceProfileModel(Base):
    """用途：系统或预设 TTS 音色配置，供任务 generation 阶段引用。"""

    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_path: Mapped[str | None] = mapped_column(String(512))
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class AvatarProfileModel(Base):
    """用途：数字人形象/模板配置，关联 HeyGem 等口播提供方参数。"""

    __tablename__ = "avatar_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class RiskCheckModel(Base):
    """用途：任务在某一风控阶段的一次检查快照，含结论级别与审核主体。"""

    __tablename__ = "risk_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    risk_status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_types: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)

    task: Mapped[TaskModel] = relationship(back_populates="risk_checks")
    findings: Mapped[list["RiskFindingModel"]] = relationship(back_populates="risk_check", cascade="all, delete-orphan")


class RiskFindingModel(Base):
    """用途：单次风控检查下的具体命中项（敏感词、版权等）及修改建议。"""

    __tablename__ = "risk_findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    risk_check_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_checks.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str | None] = mapped_column(String(255))
    suggestion: Mapped[str | None] = mapped_column(Text)

    risk_check: Mapped[RiskCheckModel] = relationship(back_populates="findings")


class AuthorizationRecordModel(Base):
    """用途：用户对上传/使用素材的授权确认留痕，按任务与资产类型唯一。"""

    __tablename__ = "authorization_records"
    __table_args__ = (UniqueConstraint("task_id", "asset_type", name="uq_authorization_task_asset"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    authorization_note: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[object] = mapped_column(DateTime, nullable=False)

    task: Mapped[TaskModel] = relationship(back_populates="authorization_records")


class DistributionRecordModel(Base, TimestampMixin):
    """用途：成片向外部平台分发/upload 的任务记录与结果 URL。"""

    __tablename__ = "distribution_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    external_url: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(String(512))
    raw_result: Mapped[dict | None] = mapped_column(JSON)

    task: Mapped[TaskModel] = relationship(back_populates="distribution_records")
