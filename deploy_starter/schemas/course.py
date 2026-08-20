from pydantic import BaseModel, Field
from datetime import datetime

class SectionOutline(BaseModel):
    title: str
    estimated_minutes: int = Field(gt=0)


class ChapterOutline(BaseModel):
    title: str
    learning_objectives: list[str]
    sections: list[SectionOutline]


class ModuleOutline(BaseModel):
    title: str
    description: str
    chapters: list[ChapterOutline]


class CourseOutline(BaseModel):
    title: str
    description: str
    modules: list[ModuleOutline]

class CourseSection(BaseModel):
    section_id: str
    course_id: str

    module_title: str
    chapter_title: str
    title: str

    module_order: int = Field(ge=0)
    chapter_order: int = Field(ge=0)
    section_order: int = Field(ge=0)

    estimated_minutes: int = Field(gt = 0)

    created_at: datetime
    updated_at: datetime

class Course(BaseModel):
    course_id: str
    user_id: str
    generation_id: str

    outline: CourseOutline

    created_at: datetime
    updated_at: datetime

class CourseListItem(BaseModel):
    course_id: str
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
class CourseListResponse(BaseModel):
    request_id: str
    courses: list[CourseListItem]


class CourseDetailResponse(BaseModel):
    request_id: str
    course: Course