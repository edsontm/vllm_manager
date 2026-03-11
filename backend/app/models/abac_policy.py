from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AbacPolicy(Base):
    __tablename__ = "abac_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Subject: at least one must be non-NULL (enforced at service layer)
    subject_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_role: Mapped[str | None] = mapped_column(
        Enum("admin", "user", name="userrole", create_type=False), nullable=True
    )

    # Resource
    resource_type: Mapped[str] = mapped_column(
        Enum("instance", "model", "token", "queue", "user", name="abac_resource_type"),
        nullable=False,
    )
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = wildcard

    # Action & effect
    action: Mapped[str] = mapped_column(
        Enum("read", "create", "update", "delete", "start", "stop", "infer", name="abac_action"),
        nullable=False,
    )
    effect: Mapped[str] = mapped_column(
        Enum("allow", "deny", name="abac_effect"), nullable=False, default="allow"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    subject_user: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[subject_user_id], back_populates="abac_policies"
    )
    created_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by_id]
    )
