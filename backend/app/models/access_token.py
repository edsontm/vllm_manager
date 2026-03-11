from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hashed_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    raw_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # First 8 chars of the raw token stored for display purposes ("see token again")
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scoped_instance_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    # Model IDs (e.g. "meta-llama/Llama-3-8B") that the token is allowed to call.
    # Empty list = all models allowed.
    scoped_model_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="access_tokens")  # noqa: F821
