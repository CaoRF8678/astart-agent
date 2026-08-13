from pydantic import BaseModel, Field


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