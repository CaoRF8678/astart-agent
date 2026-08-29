# 负责正式课程数据
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select

from database.models.course import CourseModel
from database.models.course_section import CourseSectionModel
from schemas.course import (
    Course,
    CourseListItem,
    CourseOutline,
    CourseSection,
    CourseSectionSourceReference,
)
from schemas.generation import GenerationSectionResult


class CourseRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @staticmethod
    def _final_result_map(
        section_results: list[GenerationSectionResult],
    ) -> dict[tuple[int, int, int], GenerationSectionResult]:
        result_map = {
            (
                item.module_order,
                item.chapter_order,
                item.section_order,
            ): item
            for item in section_results
        }

        for item in section_results:
            if item.final_content is None:
                raise RuntimeError(
                    "Course section final content is missing: "
                    f"{item.module_order}/"
                    f"{item.chapter_order}/"
                    f"{item.section_order}"
                )

        return result_map

    @classmethod
    def _build_section_models(
        cls,
        *,
        course_id: str,
        outline: CourseOutline,
        section_results: list[GenerationSectionResult],
    ) -> list[CourseSectionModel]:
        result_map = cls._final_result_map(
            section_results
        )
        models: list[CourseSectionModel] = []
        expected_positions: set[
            tuple[int, int, int]
        ] = set()

        for module_order, module in enumerate(
            outline.modules
        ):
            for chapter_order, chapter in enumerate(
                module.chapters
            ):
                for section_order, section in enumerate(
                    chapter.sections
                ):
                    position = (
                        module_order,
                        chapter_order,
                        section_order,
                    )
                    expected_positions.add(position)

                    result = result_map.get(position)
                    if result is None:
                        raise RuntimeError(
                            "Course section result is missing: "
                            f"{position}"
                        )

                    models.append(
                        CourseSectionModel(
                            section_id=(
                                f"sec_{uuid.uuid4()}"
                            ),
                            course_id=course_id,
                            module_title=module.title,
                            chapter_title=chapter.title,
                            title=section.title,
                            module_order=module_order,
                            chapter_order=chapter_order,
                            section_order=section_order,
                            estimated_minutes=(
                                section.estimated_minutes
                            ),
                            content=result.final_content,
                            source_references=[
                                ref.model_dump(mode="json")
                                for ref in (
                                    result.final_references
                                )
                            ],
                        )
                    )

        if set(result_map) != expected_positions:
            raise RuntimeError(
                "Generation section results do not match "
                "the final outline."
            )

        return models

    async def create_from_generation(
        self,
        *,
        generation_id: str,
        user_id: str,
        outline: CourseOutline,
        section_results: list[GenerationSectionResult],
    ) -> str:
        async with self._session_factory() as session:
            async with session.begin():
                existing_stmt = (
                    select(CourseModel)
                    .where(
                        CourseModel.generation_id
                        == generation_id
                    )
                )
                existing_result = await session.execute(
                    existing_stmt
                )
                existing_course = (
                    existing_result.scalar_one_or_none()
                )

                if existing_course is not None:
                    return existing_course.course_id

                course_id = f"course_{uuid.uuid4()}"
                course_model = CourseModel(
                    course_id=course_id,
                    user_id=user_id,
                    generation_id=generation_id,
                    outline=outline.model_dump(
                        mode="json"
                    ),
                )
                session.add(course_model)
                session.add_all(
                    self._build_section_models(
                        course_id=course_id,
                        outline=outline,
                        section_results=section_results,
                    )
                )

                return course_id

    async def replace_from_generation(
        self,
        *,
        course_id: str,
        user_id: str,
        outline: CourseOutline,
        section_results: list[GenerationSectionResult],
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(CourseModel)
                    .where(
                        CourseModel.course_id == course_id,
                        CourseModel.user_id == user_id,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                course_model = result.scalar_one_or_none()

                if course_model is None:
                    raise RuntimeError(
                        f"Course not found: {course_id}"
                    )

                new_sections = self._build_section_models(
                    course_id=course_id,
                    outline=outline,
                    section_results=section_results,
                )

                course_model.outline = outline.model_dump(
                    mode="json"
                )
                course_model.updated_at = datetime.now(
                    timezone.utc
                )

                await session.execute(
                    delete(CourseSectionModel)
                    .where(
                        CourseSectionModel.course_id
                        == course_id
                    )
                )
                session.add_all(new_sections)

    async def get_course_id_by_generation(
        self,
        *,
        generation_id: str,
    ) -> str | None:
        async with self._session_factory() as session:
            stmt = (
                select(CourseModel.course_id)
                .where(
                    CourseModel.generation_id
                    == generation_id
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_course_for_user(
        self,
        *,
        course_id: str,
        user_id: str,
    ) -> Course | None:
        async with self._session_factory() as session:
            course_stmt = (
                select(CourseModel)
                .where(
                    CourseModel.course_id == course_id,
                    CourseModel.user_id == user_id,
                )
            )
            course_result = await session.execute(
                course_stmt
            )
            course_model = (
                course_result.scalar_one_or_none()
            )

            if course_model is None:
                return None

            section_stmt = (
                select(CourseSectionModel)
                .where(
                    CourseSectionModel.course_id
                    == course_id
                )
                .order_by(
                    CourseSectionModel.module_order,
                    CourseSectionModel.chapter_order,
                    CourseSectionModel.section_order,
                )
            )
            section_result = await session.execute(
                section_stmt
            )
            section_models = list(
                section_result.scalars().all()
            )

            sections = [
                CourseSection(
                    section_id=item.section_id,
                    course_id=item.course_id,
                    module_title=item.module_title,
                    chapter_title=item.chapter_title,
                    title=item.title,
                    module_order=item.module_order,
                    chapter_order=item.chapter_order,
                    section_order=item.section_order,
                    estimated_minutes=(
                        item.estimated_minutes
                    ),
                    content=item.content,
                    source_references=[
                        CourseSectionSourceReference.model_validate(
                            ref
                        )
                        for ref in (
                            item.source_references or []
                        )
                    ],
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in section_models
            ]

            return Course(
                course_id=course_model.course_id,
                user_id=course_model.user_id,
                generation_id=course_model.generation_id,
                outline=CourseOutline.model_validate(
                    course_model.outline
                ),
                sections=sections,
                created_at=course_model.created_at,
                updated_at=course_model.updated_at,
            )

    async def list_courses_for_user(
        self,
        *,
        user_id: str,
    ) -> list[CourseListItem]:
        async with self._session_factory() as session:
            stmt = (
                select(CourseModel)
                .where(
                    CourseModel.user_id == user_id
                )
                .order_by(
                    CourseModel.created_at.desc()
                )
            )
            result = await session.execute(stmt)
            course_models = list(
                result.scalars().all()
            )

            courses: list[CourseListItem] = []
            for course_model in course_models:
                outline = CourseOutline.model_validate(
                    course_model.outline
                )
                courses.append(
                    CourseListItem(
                        course_id=course_model.course_id,
                        title=outline.title,
                        description=outline.description,
                        created_at=course_model.created_at,
                        updated_at=course_model.updated_at,
                    )
                )

            return courses