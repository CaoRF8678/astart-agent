from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from typing import Literal

LearningSourceStatus = Literal[
    "pending",
    "processing",
    "ready",
    "failed",
]


class SourceSegment(BaseModel): #后端内部正式资料片段
    segment_id: str
    file_id: str

    content: str = Field(min_length=1)
    segment_order: int = Field(ge=0)

    locator: dict[str, Any]
    embedding: list[float] | None = None
    embedding_model: str | None = None



class LearningSource(BaseModel):
    file_id: str
    course_id: str

    filename: str
    content_type: str
    size: int = Field(gt=0)

    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    storage_key: str

    status: LearningSourceStatus

    worker_id: str | None = None
    processing_started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None

    error_code: str | None = None
    error_message: str | None = None

    transcript_storage_key: str | None = None

    created_at: datetime


class LearningMaterialUploadResponse(BaseModel):  #上传接口返回
    request_id: str
    course_id: str
    file_id: str
    filename: str
    content_type: str
    size: int = Field(gt=0)
    created_at: datetime
    status: LearningSourceStatus 


class LearningMaterialListItem(BaseModel): #资料列表接口返回
    file_id: str
    filename: str
    content_type: str
    size: int = Field(gt=0)
    created_at: datetime
    status: LearningSourceStatus


class LearningMaterialListResponse(BaseModel):
    request_id: str
    materials: list[LearningMaterialListItem]