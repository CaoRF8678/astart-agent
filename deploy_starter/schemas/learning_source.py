from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceSegment(BaseModel): #后端内部正式资料片段
    segment_id: str
    file_id: str

    content: str = Field(min_length=1)
    segment_order: int = Field(ge=0)

    locator: dict[str, Any]


class LearningSource(BaseModel): #后端内部完整学习资料
    file_id: str
    course_id: str

    filename: str
    content_type: str
    size: int = Field(gt=0)

    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    storage_key: str
    created_at: datetime


class LearningMaterialUploadResponse(BaseModel):  #上传接口返回
    request_id: str
    course_id: str
    file_id: str
    filename: str
    content_type: str
    size: int = Field(gt=0)
    created_at: datetime


class LearningMaterialListItem(BaseModel): #资料列表接口返回
    file_id: str
    filename: str
    content_type: str
    size: int = Field(gt=0)
    created_at: datetime


class LearningMaterialListResponse(BaseModel):
    request_id: str
    materials: list[LearningMaterialListItem]