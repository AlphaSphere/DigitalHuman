"""KrLongAI 对齐：任务扩展字段与分发封面

Revision ID: 20260618_0003
Revises: 20260601_0002
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260618_0003"
down_revision = "20260601_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("source_url", sa.String(512), nullable=True))
    op.add_column("tasks", sa.Column("pipeline_mode", sa.String(32), nullable=True))
    op.add_column("tasks", sa.Column("pipeline_stage", sa.JSON(), nullable=True))
    op.add_column("tasks", sa.Column("voice_speed", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("background_music_mode", sa.String(32), nullable=True))
    op.add_column("tasks", sa.Column("ai_watermark_enabled", sa.Boolean(), nullable=True))
    op.add_column("tasks", sa.Column("export_without_subtitle", sa.Boolean(), nullable=True))
    op.add_column("tasks", sa.Column("avatar_engine", sa.String(32), nullable=True))
    op.add_column("distribution_records", sa.Column("cover_artifact_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("distribution_records", "cover_artifact_id")
    op.drop_column("tasks", "avatar_engine")
    op.drop_column("tasks", "export_without_subtitle")
    op.drop_column("tasks", "ai_watermark_enabled")
    op.drop_column("tasks", "background_music_mode")
    op.drop_column("tasks", "voice_speed")
    op.drop_column("tasks", "pipeline_stage")
    op.drop_column("tasks", "pipeline_mode")
    op.drop_column("tasks", "source_url")
