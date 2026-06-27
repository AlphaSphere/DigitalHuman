"""Add custom voice prompt text

Revision ID: 20260621_0004
Revises: 20260618_0003
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0004"
down_revision = "20260618_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("custom_voice_prompt_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "custom_voice_prompt_text")
