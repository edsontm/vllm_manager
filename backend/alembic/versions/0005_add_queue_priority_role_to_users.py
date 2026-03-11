"""add queue priority role to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _create_enum_if_missing(bind, name: str, values: list[str]) -> None:
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": name}
    ).fetchone()
    if not exists:
        vals = ", ".join(f"'{v}'" for v in values)
        bind.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({vals})"))


def upgrade() -> None:
    bind = op.get_bind()
    _create_enum_if_missing(
        bind,
        "queuepriorityrole",
        ["high_priority", "medium_priority", "low_priority"],
    )
    op.add_column(
        "users",
        sa.Column(
            "queue_priority_role",
            sa.Enum(
                "high_priority",
                "medium_priority",
                "low_priority",
                name="queuepriorityrole",
                create_type=False,
            ),
            nullable=False,
            server_default="medium_priority",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "queue_priority_role")
    op.execute("DROP TYPE IF EXISTS queuepriorityrole")
