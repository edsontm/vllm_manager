from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "user", name="userrole"), nullable=False, default="user"
    )
    queue_priority_role: Mapped[str] = mapped_column(
        Enum("high_priority", "medium_priority", "low_priority", name="queuepriorityrole"),
        nullable=False,
        default="medium_priority",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )

    access_tokens: Mapped[list["AccessToken"]] = relationship(  # noqa: F821
        "AccessToken", back_populates="user", cascade="all, delete-orphan"
    )
    request_logs: Mapped[list["RequestLog"]] = relationship(  # noqa: F821
        "RequestLog", back_populates="user"
    )
    abac_policies: Mapped[list["AbacPolicy"]] = relationship(  # noqa: F821
        "AbacPolicy",
        foreign_keys="AbacPolicy.subject_user_id",
        back_populates="subject_user",
        cascade="all, delete-orphan",
    )
