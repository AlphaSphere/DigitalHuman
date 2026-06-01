"""initial schema

Revision ID: 20260601_0001
Revises:
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260601_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("sample_path", sa.String(512)),
        sa.Column("config", sa.JSON(), nullable=False),
    )
    op.create_table(
        "avatar_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("script_source", sa.String(32), nullable=False),
        sa.Column("script_generation_mode", sa.String(32)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_video_path", sa.String(512)),
        sa.Column("duration", sa.Float()),
        sa.Column("aspect_ratio", sa.String(16)),
        sa.Column("generation_voice_mode", sa.String(32)),
        sa.Column("custom_voice_path", sa.String(512)),
        sa.Column("generation_video_mode", sa.String(32)),
        sa.Column("custom_video_path", sa.String(512)),
        sa.Column("voice_profile_id", sa.String(64), sa.ForeignKey("voice_profiles.id")),
        sa.Column("avatar_profile_id", sa.String(64), sa.ForeignKey("avatar_profiles.id")),
        sa.Column("subtitle_style", sa.JSON()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.String(512)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "script_segments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("start_time", sa.Float()),
        sa.Column("end_time", sa.Float()),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("edited_text", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.UniqueConstraint("task_id", "index", name="uq_script_segments_task_index"),
    )
    op.create_index("ix_script_segments_task_id", "script_segments", ["task_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("path", sa.String(512)),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])
    op.create_index("ix_artifacts_type", "artifacts", ["type"])
    op.create_table(
        "risk_checks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("risk_status", sa.String(32), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("risk_types", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_risk_checks_task_id", "risk_checks", ["task_id"])
    op.create_index("ix_risk_checks_stage", "risk_checks", ["stage"])
    op.create_table(
        "risk_findings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("risk_check_id", sa.String(64), sa.ForeignKey("risk_checks.id"), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("target", sa.String(64), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("position", sa.String(255)),
        sa.Column("suggestion", sa.Text()),
    )
    op.create_index("ix_risk_findings_risk_check_id", "risk_findings", ["risk_check_id"])
    op.create_table(
        "authorization_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("authorization_note", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("task_id", "asset_type", name="uq_authorization_task_asset"),
    )
    op.create_index("ix_authorization_records_task_id", "authorization_records", ["task_id"])


def downgrade() -> None:
    op.drop_table("authorization_records")
    op.drop_table("risk_findings")
    op.drop_table("risk_checks")
    op.drop_table("artifacts")
    op.drop_table("script_segments")
    op.drop_table("tasks")
    op.drop_table("avatar_profiles")
    op.drop_table("voice_profiles")
