from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HFModel(Base):
    """Cached HuggingFace Hub model metadata, populated by the catalog worker."""
    __tablename__ = "hf_models"

    model_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pipeline_tag: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    downloads: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", index=True)
    likes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    last_modified: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameter_count_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    vram_required_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    supports_image: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    capabilities: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_compatible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
