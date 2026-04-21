"""add hf model catalog table

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hf_models" in inspector.get_table_names():
        return

    op.create_table(
        "hf_models",
        sa.Column("model_id", sa.String(length=255), primary_key=True),
        sa.Column("author", sa.String(length=128), nullable=True),
        sa.Column("pipeline_tag", sa.String(length=64), nullable=True),
        sa.Column("downloads", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("likes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_modified", sa.String(length=64), nullable=True),
        sa.Column("parameter_count_b", sa.Float(), nullable=True),
        sa.Column("vram_required_gb", sa.Float(), nullable=True),
        sa.Column("supports_image", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_compatible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hf_models_pipeline_tag", "hf_models", ["pipeline_tag"])
    op.create_index("ix_hf_models_downloads", "hf_models", ["downloads"])
    op.create_index("ix_hf_models_is_compatible", "hf_models", ["is_compatible"])

    # Trigram index for fast substring search on search_text.
    # Fall back silently if pg_trgm is not available.
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_hf_models_search_trgm "
            "ON hf_models USING gin (search_text gin_trgm_ops)"
        )
    except Exception:
        pass


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_hf_models_search_trgm")
    op.drop_index("ix_hf_models_is_compatible", table_name="hf_models")
    op.drop_index("ix_hf_models_downloads", table_name="hf_models")
    op.drop_index("ix_hf_models_pipeline_tag", table_name="hf_models")
    op.drop_table("hf_models")
