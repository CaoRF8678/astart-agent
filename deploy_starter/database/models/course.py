from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class CourseModel(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    generation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "generation_jobs.generation_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    )

    outline: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )