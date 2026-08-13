from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class LearningBriefDraft(BaseModel):
    goal: str | None = None
    application_scenario: str | None = None
    target_outcome: str | None = None
    prior_knowledge: str | None = None

    weekly_hours: float | None = Field(
        default=None,
        gt=0,
    )
    expected_duration_weeks: int | None = Field(
        default=None,
        gt=0,
    )

    focus_areas: list[str] | None = None
    learning_preferences: list[str] | None = None
    constraints: list[str] | None = None


class LearningBriefContent(BaseModel):
    goal: str
    application_scenario: str | None = None
    target_outcome: str | None = None
    prior_knowledge: str | None = None

    weekly_hours: float | None = Field(
        default=None,
        gt=0,
    )
    expected_duration_weeks: int | None = Field(
        default=None,
        gt=0,
    )

    focus_areas: list[str] | None = None
    learning_preferences: list[str] | None = None
    constraints: list[str] | None = None

class IntakeSession(BaseModel):

    session_id: str = Field(..., min_length =1)
    user_id: str = Field(..., min_length=1)


    # active / completed / cancelled / expired
    status: Literal["active", "completed","cancelled","expired"] = "active"

    # 已经进行了多少轮问题组
    round_count: int = Field(default= 0, ge = 0, le = 6)

    # 当前学习简报草稿
    brief_draft: LearningBriefDraft


    # 哪些字段已经询问过
    asked_fields: list[str] = Field(default_factory= list)

    # 用户最后一次活动时间
    last_activity_at: datetime