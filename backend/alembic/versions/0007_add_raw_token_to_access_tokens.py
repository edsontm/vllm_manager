"""add raw token column to access_tokens

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("access_tokens")}
    if "raw_token" not in columns:
        op.add_column("access_tokens", sa.Column("raw_token", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("access_tokens", "raw_token")
