from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class LearningSourceModel(Base):
    __tablename__ = "learning_sources"

    __table_args__ = (
        CheckConstraint(
            "size > 0",
            name="ck_learning_sources_size",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_learning_sources_status",
        ),
    )

    file_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    course_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "courses.course_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable= False,
        default= "ready",
        server_default="ready",
    )

    worker_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    heartbeat_at: Mapped[datetime | None] =mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] =mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable= True,
    )

    transcript_storage_key: Mapped[str | None] = mapped_column(
        Text,
        nullable= True,
    )
