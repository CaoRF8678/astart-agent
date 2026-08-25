from datetime import datetime, timezone

from sqlalchemy import select, update

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
        self._session_factory = session_factory

    @staticmethod
    def _to_source(
        model: LearningSourceModel,
    ) -> LearningSource:
        return LearningSource(
            file_id=model.file_id,
            course_id=model.course_id,
            filename=model.filename,
            content_type=model.content_type,
            size=model.size,
            sha256=model.sha256,
            storage_key=model.storage_key,
            status=model.status,
            worker_id=model.worker_id,
            processing_started_at=(
                model.processing_started_at
            ),
            heartbeat_at=model.heartbeat_at,
            finished_at=model.finished_at,
            error_code=model.error_code,
            error_message=model.error_message,
            transcript_storage_key=(
                model.transcript_storage_key
            ),
            created_at=model.created_at,
        )

    @staticmethod
    def _segment_models(
        segments: list[SourceSegment],
    ) -> list[SourceSegmentModel]:
        return [
            SourceSegmentModel(
                segment_id=segment.segment_id,
                file_id=segment.file_id,
                content=segment.content,
                segment_order=segment.segment_order,
                locator=segment.locator,
                embedding=segment.embedding,
                embedding_model=(
                    segment.embedding_model
                ),
            )
            for segment in segments
        ]

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
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            async with session.begin():
                source_model = LearningSourceModel(
                    file_id=file_id,
                    course_id=course_id,
                    filename=filename,
                    content_type=content_type,
                    size=size,
                    sha256=sha256,
                    storage_key=storage_key,
                    status="ready",
                    finished_at=now,
                )
                session.add(source_model)
                session.add_all(
                    self._segment_models(segments)
                )

                await session.flush()
                await session.refresh(source_model)
                return self._to_source(source_model)

    async def create_pending_source(
        self,
        *,
        file_id: str,
        course_id: str,
        filename: str,
        content_type: str,
        size: int,
        sha256: str,
        storage_key: str,
    ) -> LearningSource:
        async with self._session_factory() as session:
            async with session.begin():
                source_model = LearningSourceModel(
                    file_id=file_id,
                    course_id=course_id,
                    filename=filename,
                    content_type=content_type,
                    size=size,
                    sha256=sha256,
                    storage_key=storage_key,
                    status="pending",
                )
                session.add(source_model)
                await session.flush()
                await session.refresh(source_model)
                return self._to_source(source_model)

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
            result = await session.execute(stmt)
            source_models = list(
                result.scalars().all()
            )

            return [
                LearningMaterialListItem(
                    file_id=source.file_id,
                    filename=source.filename,
                    content_type=source.content_type,
                    size=source.size,
                    status=source.status,
                    created_at=source.created_at,
                )
                for source in source_models
            ]

    async def claim_next_pending_source(
        self,
        *,
        worker_id: str,
    ) -> LearningSource | None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(LearningSourceModel)
                    .where(
                        LearningSourceModel.status
                        == "pending"
                    )
                    .order_by(
                        LearningSourceModel.created_at
                    )
                    .with_for_update(
                        skip_locked=True
                    )
                    .limit(1)
                )
                result = await session.execute(stmt)
                source_model = (
                    result.scalar_one_or_none()
                )

                if source_model is None:
                    return None

                now = datetime.now(timezone.utc)
                source_model.status = "processing"
                source_model.worker_id = worker_id
                source_model.processing_started_at = now
                source_model.heartbeat_at = now
                source_model.finished_at = None
                source_model.error_code = None
                source_model.error_message = None

                await session.flush()
                return self._to_source(source_model)

    async def update_heartbeat(
        self,
        *,
        file_id: str,
        worker_id: str,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    update(LearningSourceModel)
                    .where(
                        LearningSourceModel.file_id
                        == file_id,
                        LearningSourceModel.status
                        == "processing",
                        LearningSourceModel.worker_id
                        == worker_id,
                    )
                    .values(
                        heartbeat_at=datetime.now(
                            timezone.utc
                        )
                    )
                )
                result = await session.execute(stmt)
                return result.rowcount == 1

    async def mark_source_ready_with_segments(
        self,
        *,
        file_id: str,
        worker_id: str,
        segments: list[SourceSegment],
        transcript_storage_key: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(LearningSourceModel)
                    .where(
                        LearningSourceModel.file_id
                        == file_id,
                        LearningSourceModel.status
                        == "processing",
                        LearningSourceModel.worker_id
                        == worker_id,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                source_model = (
                    result.scalar_one_or_none()
                )

                if source_model is None:
                    raise RuntimeError(
                        "Learning source is no longer owned by this worker."
                    )

                session.add_all(
                    self._segment_models(segments)
                )

                now = datetime.now(timezone.utc)
                source_model.status = "ready"
                source_model.finished_at = now
                source_model.transcript_storage_key = (
                    transcript_storage_key
                )
                source_model.worker_id = None
                source_model.heartbeat_at = None
                source_model.error_code = None
                source_model.error_message = None

    async def mark_source_failed(
        self,
        *,
        file_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    update(LearningSourceModel)
                    .where(
                        LearningSourceModel.file_id
                        == file_id,
                        LearningSourceModel.status
                        == "processing",
                        LearningSourceModel.worker_id
                        == worker_id,
                    )
                    .values(
                        status="failed",
                        worker_id=None,
                        heartbeat_at=None,
                        finished_at=datetime.now(
                            timezone.utc
                        ),
                        error_code=error_code,
                        error_message=error_message,
                    )
                )
                result = await session.execute(stmt)
                return result.rowcount == 1

    async def requeue_stale_sources(
        self,
        *,
        stale_before: datetime,
    ) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    update(LearningSourceModel)
                    .where(
                        LearningSourceModel.status
                        == "processing",
                        LearningSourceModel.heartbeat_at
                        < stale_before,     #代表5min没有上报心跳-> worker已经失联，任务过期卡死
                    )
                    .values(
                        status="pending",
                        worker_id=None,
                        processing_started_at=None,
                        heartbeat_at=None,
                        finished_at=None,
                        error_code=None,
                        error_message=None,
                    )
                )
                result = await session.execute(stmt)
                return result.rowcount or 0