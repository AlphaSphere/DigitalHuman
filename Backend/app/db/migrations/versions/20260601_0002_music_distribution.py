"""add music and distribution records

Revision ID: 20260601_0002
Revises: 20260601_0001
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260601_0002"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("background_music_path", sa.String(512), nullable=True))
    op.add_column("tasks", sa.Column("background_music_volume", sa.Float(), nullable=True))
    op.create_table(
        "distribution_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("external_url", sa.String(512)),
        sa.Column("error_message", sa.String(512)),
        sa.Column("raw_result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_distribution_records_task_id", "distribution_records", ["task_id"])


def downgrade() -> None:
    op.drop_table("distribution_records")
    op.drop_column("tasks", "background_music_volume")
    op.drop_column("tasks", "background_music_path")
