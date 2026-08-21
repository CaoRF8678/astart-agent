from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class SourceSegmentModel(Base):
    __tablename__ = "source_segments"

    __table_args__ = (
        CheckConstraint(
            "segment_order >= 0",
            name="ck_source_segments_order",
        ),
        UniqueConstraint(
            "file_id",
            "segment_order",
            name="uq_source_segments_file_order",
        ),      #两个组合在一起必须唯一
    )

    segment_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    file_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "learning_sources.file_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    segment_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    locator: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )