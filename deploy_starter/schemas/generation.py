from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


GenerationStatus  = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]


GenerationStageName = Literal[
    "research",
    "outline",
    "critique",
    "revision",
    "draft",
    "final_check",
]


class GenerationStage(BaseModel):
    stage: GenerationStageName
    status: GenerationStatus = "pending"

    attempt_count: int = Field(default=0,ge =0)

    started_at: datetime | None = None
    finished_at: datetime | None =None

    error: str | None = None


class GenerationJob(BaseModel):
    status: GenerationStatus = "pending"
    stages: list[GenerationStage]