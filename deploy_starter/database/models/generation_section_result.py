from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class GenerationSectionResultModel(Base):
    __tablename__ = "generation_section_results"

    __table_args__ = (
        CheckConstraint(
            "module_order >= 0",
            name=(
                "ck_generation_section_results_"
                "module_order"
            ),
        ),
        CheckConstraint(
            "chapter_order >= 0",
            name=(
                "ck_generation_section_results_"
                "chapter_order"
            ),
        ),
        CheckConstraint(
            "section_order >= 0",
            name=(
                "ck_generation_section_results_"
                "section_order"
            ),
        ),
    )

    generation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "generation_jobs.generation_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    module_order: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    chapter_order: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    section_order: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    retrieval_queries: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    retrieved_context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    retrieved_references: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    draft_content: Mapped[str | None] = mapped_column(
        Text,
    )
    draft_cited_source_numbers: Mapped[list] = (
        mapped_column(
            JSONB,
            nullable=False,
            default=list,
        )
    )

    final_content: Mapped[str | None] = mapped_column(
        Text,
    )
    final_references: Mapped[list] = mapped_column(
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