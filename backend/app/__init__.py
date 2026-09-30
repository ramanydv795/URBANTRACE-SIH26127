"""
SQLAlchemy ORM models for the Part 2 perception layer.

The database schema remains the source of truth. These models allow the
perception pipeline to interact with the perception tables using SQLAlchemy.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    plate_best: Mapped[str | None] = mapped_column(Text)
    plate_conf: Mapped[float | None] = mapped_column(Numeric)

    vehicle_type: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)

    is_blacklisted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    first_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    observations: Mapped[list["VehicleObservation"]] = relationship(
        back_populates="vehicle"
    )


class VehicleObservation(Base):
    __tablename__ = "vehicle_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=False,
    )

    camera_code: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
        nullable=True,
    )

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    track_id: Mapped[int | None] = mapped_column(Integer)

    bbox: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    frame_ref: Mapped[str | None] = mapped_column(Text)

    plate_text: Mapped[str | None] = mapped_column(Text)
    plate_conf: Mapped[float | None] = mapped_column(Numeric)

    vehicle_type: Mapped[str | None] = mapped_column(Text)
    type_conf: Mapped[float | None] = mapped_column(Numeric)

    color: Mapped[str | None] = mapped_column(Text)
    color_conf: Mapped[float | None] = mapped_column(Numeric)

    detection_conf: Mapped[float | None] = mapped_column(Numeric)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    vehicle: Mapped["Vehicle | None"] = relationship(
        back_populates="observations"
    )

    reid_embedding: Mapped["ReidEmbedding | None"] = relationship(
        back_populates="observation",
        uselist=False,
    )


class ReidEmbedding(Base):
    __tablename__ = "reid_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "vehicle_observations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    model_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    vector: Mapped[list[float]] = mapped_column(
        ARRAY(Numeric),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    observation: Mapped["VehicleObservation"] = relationship(
        back_populates="reid_embedding"
    )


class CameraHealthMetric(Base):
    __tablename__ = "camera_health_metrics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    camera_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    camera_code: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    fps: Mapped[float | None] = mapped_column(Numeric)
    processing_latency_ms: Mapped[float | None] = mapped_column(Numeric)
    detection_count: Mapped[int | None] = mapped_column(Integer)
    ocr_success_rate: Mapped[float | None] = mapped_column(Numeric)
    stream_health: Mapped[str | None] = mapped_column(Text)