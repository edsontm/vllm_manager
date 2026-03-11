"""add token_id and error_message to request_logs

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column(
            "token_id",
            sa.Integer(),
            sa.ForeignKey("access_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "request_logs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_request_logs_token_id", "request_logs", ["token_id"])


def downgrade() -> None:
    op.drop_index("ix_request_logs_token_id", table_name="request_logs")
    op.drop_column("request_logs", "error_message")
    op.drop_column("request_logs", "token_id")
