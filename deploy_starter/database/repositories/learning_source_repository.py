from sqlalchemy import select

from database.models.learning_source import (
    LearningSourceModel,
)
from database.models.source_segment import (
    SourceSegmentModel,
)
from schemas.learning_source import (
    LearningMaterialListItem,
    LearningSource,
    SourceSegment,
)


class LearningSourceRepository:

    def __init__(
        self,
        session_factory,
    ) -> None:
        self._session_factory = (
            session_factory
        )

    async def create_learning_source_with_segments(
        self,
        *,
        file_id: str,
        course_id: str,
        filename: str,
        content_type: str,
        size: int,
        sha256: str,
        storage_key: str,
        segments: list[SourceSegment],
    ) -> LearningSource:

        async with self._session_factory() as session:
            async with session.begin():

                source_model = (
                    LearningSourceModel(
                        file_id=file_id,
                        course_id=course_id,
                        filename=filename,
                        content_type=content_type,
                        size=size,
                        sha256=sha256,
                        storage_key=storage_key,
                    )
                )

                session.add(source_model)

                segment_models = [
                    SourceSegmentModel(
                        segment_id=(
                            segment.segment_id
                        ),
                        file_id=(
                            segment.file_id
                        ),
                        content=(
                            segment.content
                        ),
                        segment_order=(
                            segment.segment_order
                        ),
                        locator=(
                            segment.locator
                        ),
                    )
                    for segment in segments
                ]

                session.add_all(
                    segment_models
                )

                await session.flush()
                await session.refresh(
                    source_model
                )

                source = LearningSource(
                    file_id=(
                        source_model.file_id
                    ),
                    course_id=(
                        source_model.course_id
                    ),
                    filename=(
                        source_model.filename
                    ),
                    content_type=(
                        source_model.content_type
                    ),
                    size=source_model.size,
                    sha256=source_model.sha256,
                    storage_key=(
                        source_model.storage_key
                    ),
                    created_at=(
                        source_model.created_at
                    ),
                )

        return source

    async def list_learning_sources_for_course(
        self,
        *,
        course_id: str,
    ) -> list[LearningMaterialListItem]:

        async with self._session_factory() as session:
            stmt = (
                select(LearningSourceModel)
                .where(
                    LearningSourceModel.course_id
                    == course_id
                )
                .order_by(
                    LearningSourceModel.created_at.desc()
                )
            )

            result = await session.execute(
                stmt
            )

            source_models = list(
                result.scalars().all()
            )

            return [
                LearningMaterialListItem(
                    file_id=source.file_id,
                    filename=source.filename,
                    content_type=(
                        source.content_type
                    ),
                    size=source.size,
                    created_at=(
                        source.created_at
                    ),
                )
                for source in source_models
            ]