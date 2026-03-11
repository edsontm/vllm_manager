"""backfill queue priority role from user role

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET queue_priority_role = CASE
                WHEN role = 'admin' THEN 'high_priority'::queuepriorityrole
                WHEN role = 'user' THEN 'low_priority'::queuepriorityrole
                ELSE queue_priority_role
            END
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET queue_priority_role = 'medium_priority'::queuepriorityrole
            """
        )
    )
