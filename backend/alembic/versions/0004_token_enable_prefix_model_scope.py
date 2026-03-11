"""add is_enabled, token_prefix and scoped_model_ids to access_tokens

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "access_tokens",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "access_tokens",
        sa.Column("token_prefix", sa.String(16), nullable=False, server_default=""),
    )
    op.add_column(
        "access_tokens",
        sa.Column("scoped_model_ids", ARRAY(sa.String()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("access_tokens", "scoped_model_ids")
    op.drop_column("access_tokens", "token_prefix")
    op.drop_column("access_tokens", "is_enabled")
