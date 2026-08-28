from __future__ import annotations
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from schemas.intake import LearningBriefContent
from schemas.course import CourseOutline

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

ResearchTopicRole = Literal[
    "core",
    "prerequisite",
    "supporting",
    "optional",
]

ResearchTopicTreatment = Literal[
    "deep",
    "standard",
    "compressed",
    "skip",
]

ResearchSourceType = Literal[
    "official_document",
    "paper",
    "book",
    "course",
    "article",
    "other",
]

ResearchCredibility = Literal[
    "high",
    "medium",
    "low",
]


class GenerationStage(BaseModel):
    stage: GenerationStageName
    status: GenerationStatus = "pending"

    attempt_count: int = Field(default=0,ge =0)

    started_at: datetime | None = None
    finished_at: datetime | None =None

    error_code: str | None = None
    error_message: str | None = None


class GenerationJob(BaseModel):
    generation_id: str = Field(
        ...,
        min_length=1,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    status: GenerationStatus = "pending"

    stages: list[GenerationStage]

    learning_brief: LearningBriefContent

    research_result: ResearchResult | None = None

    outline_v1: CourseOutline | None = None

    critique_result: CritiqueResult | None = None

    final_outline: CourseOutline | None = None

    cancel_requested: bool = False

    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime

    error_code: str | None = None
    error_message: str | None = None
    target_course_id: str | None = None


class ResearchTopic(BaseModel):
    topic: str = Field(..., min_length=1)

    role: ResearchTopicRole

    treatment: ResearchTopicTreatment

    prerequisites: list[str] = Field(
        default_factory= list
    )

    rationale: str = Field(
        ...,
        min_length=1,
    )

class ResearchSource(BaseModel):
    source_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)

    url: str | None = None

    source_type: ResearchSourceType

    publisher: str | None = None

    credibility: ResearchCredibility

class ResearchEvidence(BaseModel):
    evidence_id: str = Field(..., min_length=1)

    source_id: str = Field(..., min_length=1)

    topic: str = Field(..., min_length=1)

    claim: str = Field(..., min_length=1) #支撑的claim是什么

    locator: str | None = None  #原始位置在哪里

class ResearchResult(BaseModel):
    summary: str = Field(..., min_length=1)

    personalization_summary: str = Field(  #个性化摘要
        ...,
        min_length=1,
    )

    topics: list[ResearchTopic] = Field(
        min_length=1,
    )

    learning_sequence: list[str] = Field(  #学习序列
        min_length=1,
    )

    time_budget_minutes: int | None = Field( #总预算，分钟
        default=None,
        ge = 0,
    )

    time_strategy: str = Field( #时间策略
        ...,
        min_length=1,
    )

    sources: list[ResearchSource] = Field(
        default_factory= list
    )

    evidence: list[ResearchEvidence] = Field(
        default_factory= list
    )

CritiqueCategory = Literal[
    "coverage",
    "ordering",
    "difficulty",
    "personalization",
    "time_budget",
    "redundancy",
    "objective",
    "other",
]

CritiqueSeverity = Literal[  #严重程度
    "high",
    "medium",
    "low",
]


class CritiqueIssue(BaseModel):
    category: CritiqueCategory

    severity: CritiqueSeverity

    location: str | None = None

    description: str = Field(
        ...,
        min_length=1,
    )

    suggestion: str = Field(
        ...,
        min_length=1,
    )

class CritiqueResult(BaseModel):
    overall_score: int = Field(
        ge= 0,
        le = 100,
    )

    passed: bool

    strengths: list[str] = Field(
        default_factory=list,
    )

    issues: list[CritiqueIssue] = Field(
        default_factory=list,
    )

    revision_summary: str = Field(
        ...,
        min_length=1,
    )

#course请求
class CourseGenerationRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    brief: LearningBriefContent

class CourseGenerationAcceptedResponse(BaseModel):
    request_id: str
    generation_id: str
    status: Literal["pending"]
    created_at: datetime

class CourseGenerationStatusResponse(BaseModel):
    request_id: str

    generation_id: str
    status: GenerationStatus

    current_stage: GenerationStageName | None

    stages: list[GenerationStage]
    course_id: str | None = None

    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    final_outline: CourseOutline | None = None

    error_code: str | None = None
    error_message: str | None = None

class CourseGenerationCancelRequest(BaseModel):
    user_id: str = Field(..., min_length=1)

class CourseGenerationCancelResponse(BaseModel):
    request_id: str
    generation_id: str
    status: GenerationStatus
    cancel_requested: bool

class CourseRegenerationRequest(BaseModel):
    user_id: str = Field(..., min_length=1)

class RetrievalQueryPlan(BaseModel):
    queries: list[str] = Field(
        min_length=1,
        max_length=5,
    )