from sqlalchemy import (
    DateTime,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import CheckConstraint
from database.base import Base
from datetime import datetime


class GenerationStageModel(Base):
    __tablename__ = "generation_stages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name = "ck_generation_stage_status",
        ),
        CheckConstraint(
            "stage IN ('research','outline','critique','revision','draft','final_check')",
            name = "ck_generation_stage_name",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_generation_stage_attempt",
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

    stage: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable= False,
        default="pending",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable= False,
        default= 0,
    )
    started_at: Mapped[datetime |None] = mapped_column(
        DateTime(timezone=True),
    )
    finished_at: Mapped[datetime |None] = mapped_column(
        DateTime(timezone=True),
    )
    error_code: Mapped[str | None] = mapped_column(
        String(128),
    )
    error_message: Mapped[str |None] = mapped_column(
        Text,
    )
    # TODO：
    # started_at
    # finished_at
    # error_code
    # error_message