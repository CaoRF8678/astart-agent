#这个管正式课程
import uuid

from sqlalchemy import select, delete
from datetime import datetime, timezone
from database.models.course import CourseModel
from database.models.course_section import CourseSectionModel
from schemas.course import (
    Course,
    CourseListItem,
    CourseOutline,
    CourseSection,
)


class CourseRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def create_from_outline(
        self,
        *,
        generation_id: str,
        user_id: str,
        outline: CourseOutline,
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
                for module_order, module in enumerate(
                    outline.modules
                ):
                    for chapter_order, chapter in enumerate(
                        module.chapters
                    ):
                        for section_order, section in enumerate(
                            chapter.sections
                        ):

                            section_model = CourseSectionModel(
                                section_id=f"sec_{uuid.uuid4()}",
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
                            )

                            session.add(section_model)

                return course_id

    async def replace_outline(
        self,
        *,
        course_id: str,
        user_id: str,
        outline: CourseOutline,
    ) -> None:

        async with self._session_factory() as session:
            async with session.begin():

                # 1. 找到并锁住要更新的 Course
                stmt = (
                    select(CourseModel)
                    .where(
                        CourseModel.course_id == course_id,
                        CourseModel.user_id == user_id,
                    )
                    .with_for_update()
                )

                result = await session.execute(stmt)

                course_model = (
                    result.scalar_one_or_none()
                )

                if course_model is None:
                    raise RuntimeError(
                        f"Course not found: {course_id}"
                    )

                # 2. 更新 Course 的完整 Outline
                course_model.outline = (
                    outline.model_dump(
                        mode="json"
                    )
                )

                course_model.updated_at = (
                    datetime.now(timezone.utc)
                )

                # 3. 删除这门课程原来的所有 Section
                await session.execute(
                    delete(CourseSectionModel)
                    .where(
                        CourseSectionModel.course_id
                        == course_id
                    )
                )

                # 4. 根据新的 Outline 重新创建 Section
                for module_order, module in enumerate(
                    outline.modules
                ):
                    for chapter_order, chapter in enumerate(
                        module.chapters
                    ):
                        for section_order, section in enumerate(
                            chapter.sections
                        ):

                            section_model = CourseSectionModel(
                                section_id=f"sec_{uuid.uuid4()}",
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
                            )

                            session.add(section_model)

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
    #根据 course_id + user_id，查询某个用户拥有的一门课程，并把数据库里的数据转换成 Pydantic 的 Course 对象返回。
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

            return Course(
                course_id=course_model.course_id,
                user_id=course_model.user_id,
                generation_id=course_model.generation_id,
                outline=CourseOutline.model_validate(
                    course_model.outline
                ),
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