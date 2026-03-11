from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VllmInstance(Base):
    __tablename__ = "vllm_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    internal_port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("stopped", "starting", "running", "error", "pulling", name="instancestatus"),
        nullable=False,
        default="stopped",
    )
    gpu_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    max_model_len: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_memory_utilization: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    tensor_parallel_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dtype: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    quantization: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    request_logs: Mapped[list["RequestLog"]] = relationship(  # noqa: F821
        "RequestLog", back_populates="instance"
    )
