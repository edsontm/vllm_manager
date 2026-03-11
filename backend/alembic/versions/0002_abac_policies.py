"""add abac_policies table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-03 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        bind, "abac_resource_type",
        ["instance", "model", "token", "queue", "user"],
    )
    _create_enum_if_missing(
        bind, "abac_action",
        ["read", "create", "update", "delete", "start", "stop", "infer"],
    )
    _create_enum_if_missing(bind, "abac_effect", ["allow", "deny"])

    op.create_table(
        "abac_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subject_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_role",
            postgresql.ENUM("admin", "user", name="userrole", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "resource_type",
            postgresql.ENUM(
                "instance", "model", "token", "queue", "user",
                name="abac_resource_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(
                "read", "create", "update", "delete", "start", "stop", "infer",
                name="abac_action", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "effect",
            postgresql.ENUM("allow", "deny", name="abac_effect", create_type=False),
            nullable=False,
            server_default="allow",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_abac_policies_subject_user_id",
        "abac_policies",
        ["subject_user_id"],
    )
    op.create_index(
        "ix_abac_policies_resource",
        "abac_policies",
        ["subject_user_id", "resource_type", "action"],
    )
    op.create_index(
        "ix_abac_policies_role_resource",
        "abac_policies",
        ["subject_role", "resource_type", "action"],
    )


def downgrade() -> None:
    op.drop_index("ix_abac_policies_role_resource", "abac_policies")
    op.drop_index("ix_abac_policies_resource", "abac_policies")
    op.drop_index("ix_abac_policies_subject_user_id", "abac_policies")
    op.drop_table("abac_policies")
    op.execute("DROP TYPE IF EXISTS abac_effect")
    op.execute("DROP TYPE IF EXISTS abac_action")
    op.execute("DROP TYPE IF EXISTS abac_resource_type")
