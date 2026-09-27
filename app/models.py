import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_api_key() -> str:
    return "hub_" + secrets.token_urlsafe(24)


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(200))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    input_params: Mapped[str] = mapped_column(Text, default="[]")
    output_schema: Mapped[str] = mapped_column(Text, default="{}")
    api_key: Mapped[str] = mapped_column(String(120), default=new_api_key)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    logs: Mapped[list["UsageLog"]] = relationship(back_populates="connector", cascade="all, delete-orphan")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    connector: Mapped[Connector] = relationship(back_populates="logs")


class ModelCache(Base):
    __tablename__ = "model_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), unique=True)
    models_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
