from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import CheckConstraint
from database.base import Base
from datetime import datetime

class GenerationJobModel(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name = "ck_generation_jobs_status",
        ),
    )    

    generation_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,

    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    worker_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    learning_brief: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    research_result:Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    outline_v1:Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    critique_result:Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    final_outline:Mapped[dict |None] = mapped_column(
        JSONB,
        nullable=True,
    )   
    error_code: Mapped[str | None] = mapped_column(
        String(128),
    )
    error_message: Mapped[str |None] = mapped_column(
        Text,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime |None] = mapped_column(
        DateTime(timezone=True),
    )
    finished_at: Mapped[datetime |None] = mapped_column(
        DateTime(timezone=True),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

