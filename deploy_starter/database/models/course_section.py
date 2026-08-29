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
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from database.base import Base


class CourseSectionModel(Base):
    __tablename__ = "course_sections"

    __table_args__ = (
        CheckConstraint(
            "module_order >= 0",
            name="ck_course_sections_module_order",
        ),
        CheckConstraint(
            "chapter_order >= 0",
            name="ck_course_sections_chapter_order",
        ),
        CheckConstraint(
            "section_order >= 0",
            name="ck_course_sections_section_order",
        ),
        CheckConstraint(
            "estimated_minutes > 0",
            name="ck_course_sections_estimated_minutes",
        ),
        UniqueConstraint(
            "course_id",
            "module_order",
            "chapter_order",
            "section_order",
            name="uq_course_sections_position",
        ),
    )

    section_id: Mapped[str] = mapped_column(
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

    module_title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    chapter_title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    module_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chapter_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    section_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    )

    source_references: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
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