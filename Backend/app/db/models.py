from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TaskModel(Base, TimestampMixin):
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
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))

    segments: Mapped[list["ScriptSegmentModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    risk_checks: Mapped[list["RiskCheckModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    authorization_records: Mapped[list["AuthorizationRecordModel"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class ScriptSegmentModel(Base):
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
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    path: Mapped[str | None] = mapped_column(String(512))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)

    task: Mapped[TaskModel] = relationship(back_populates="artifacts")


class VoiceProfileModel(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_path: Mapped[str | None] = mapped_column(String(512))
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class AvatarProfileModel(Base):
    __tablename__ = "avatar_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class RiskCheckModel(Base):
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
