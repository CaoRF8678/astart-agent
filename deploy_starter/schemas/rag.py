from typing import Any

from pydantic import BaseModel, Field


class RetrievedSegment(BaseModel):
    segment_id: str
    file_id: str
    filename: str

    content: str
    locator: dict[str, Any]

    similarity_score: float = Field(
        ge=-1.0,
        le=1.0,
    )

class RAGQueryRequest(BaseModel):
    user_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class RAGSource(BaseModel):
    segment_id: str
    file_id: str
    filename: str
    locator: dict[str, Any]
    similarity_score: float


class RAGQueryResponse(BaseModel):
    request_id: str
    course_id: str
    answer: str
    sources: list[RAGSource]


    