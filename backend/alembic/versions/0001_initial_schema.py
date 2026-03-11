"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
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

    # ── enum types (idempotent) ────────────────────────────────────────────────
    _create_enum_if_missing(bind, "userrole", ["admin", "user"])
    _create_enum_if_missing(bind, "instancestatus", ["stopped", "starting", "running", "error", "pulling"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", postgresql.ENUM("admin", "user", name="userrole", create_type=False), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── vllm_instances ────────────────────────────────────────────────────────
    op.create_table(
        "vllm_instances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("container_id", sa.String(128), nullable=True),
        sa.Column("internal_port", sa.Integer(), nullable=False, unique=True),
        sa.Column(
            "status",
            postgresql.ENUM("stopped", "starting", "running", "error", "pulling", name="instancestatus", create_type=False),
            nullable=False,
            server_default="stopped",
        ),
        sa.Column("gpu_ids", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("max_model_len", sa.Integer(), nullable=True),
        sa.Column("gpu_memory_utilization", sa.Float(), nullable=False, server_default="0.9"),
        sa.Column("tensor_parallel_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("dtype", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("quantization", sa.String(32), nullable=True),
        sa.Column("extra_args", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── access_tokens ─────────────────────────────────────────────────────────
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("hashed_token", sa.String(255), nullable=False, unique=True),
        sa.Column("scoped_instance_ids", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_access_tokens_user_id", "access_tokens", ["user_id"])

    # ── request_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "request_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.Integer(), sa.ForeignKey("vllm_instances.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_code", sa.SmallInteger(), nullable=False, server_default="200"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_request_logs_instance_created", "request_logs", ["instance_id", "created_at"])
    op.create_index("ix_request_logs_user_created", "request_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("request_logs")
    op.drop_table("access_tokens")
    op.drop_table("vllm_instances")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS instancestatus")
    op.execute("DROP TYPE IF EXISTS userrole")
