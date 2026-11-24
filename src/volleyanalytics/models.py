"""Feature tables, introduced one milestone at a time through Alembic migrations."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from volleyanalytics.db import Base


class Video(Base):
    """A registered source video. The file stays in storage; only its key and hash live here."""

    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("size_bytes > 0", name="positive_size"),
        CheckConstraint("width > 0 AND height > 0", name="positive_dimensions"),
        CheckConstraint("fps > 0", name="positive_fps"),
        CheckConstraint("frame_count > 0", name="positive_frame_count"),
        CheckConstraint("duration_sec > 0", name="positive_duration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    frame_count: Mapped[int] = mapped_column(Integer)
    duration_sec: Mapped[float] = mapped_column(Float)
    duration_source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
