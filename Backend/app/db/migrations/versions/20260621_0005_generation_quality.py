"""Add generation quality and tuilionnx sync offset

Revision ID: 20260621_0005
Revises: 20260621_0004
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0005"
down_revision = "20260621_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("generation_quality", sa.String(length=32), nullable=True, server_default="full"))
    op.add_column("tasks", sa.Column("tuilionnx_sync_offset", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("tasks", "tuilionnx_sync_offset")
    op.drop_column("tasks", "generation_quality")
