#负责所有的 Generation Job数据库的读写
from datetime import datetime, timezone
from typing import Literal
from sqlalchemy import select
from schemas.intake import LearningBriefContent
from database.models.generation_job import GenerationJobModel
from database.models.generation_stage import GenerationStageModel
from database.models.generation_section_result import (
    GenerationSectionResultModel,
)
from schemas.generation import (
    GenerationJob,
    GenerationStage,
    ResearchResult,
    CritiqueResult,
    GenerationSectionResult,
    SectionContentResult,
)
from schemas.course import (
    CourseOutline,
    CourseSectionSourceReference,
)


CancelResult = Literal[
    "not_found",
    "cancelled_now",
    "cancel_requested",
    "already_completed",
    "already_failed",
    "already_cancelled",
]
STAGE_ORDER = {
    "research": 0,
    "outline": 1,
    "critique": 2,
    "revision": 3,
    "draft": 4,
    "final_check": 5,
}
STAGE_SNAPSHOT_FIELDS = {
    "research": "research_result",
    "outline": "outline_v1",
    "critique": "critique_result",
    "revision": "final_outline",
}
class GenerationRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory    
    async def create_job( #创建job，1条job+4个stage
        self,
        *,
        generation_id: str,
        user_id:str,
        brief: LearningBriefContent,
        target_course_id: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():

                job = GenerationJobModel(
                    generation_id = generation_id,
                    user_id = user_id,
                    status = "pending",
                    target_course_id = target_course_id,
                    learning_brief = brief.model_dump(
                        mode = "json"
                    ),
                )

                session.add(job)

                for stage_name in(
                    "research",
                    "outline",
                    "critique",
                    "revision",
                    "draft",
                    "final_check",
                ):
                    stage = GenerationStageModel(
                        generation_id = generation_id,
                        stage  = stage_name,
                        status = "pending",
                    )
                    session.add(stage)

    async def claim_next_pending_job(
            self,
            *,
            worker_id:str,
    ):  #领取job
        async with self._session_factory() as session:
            async with session.begin():
                #statement,声明，一般指SQL 语句对象
                stmt = (   
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.status == "pending"
                    )
                    .order_by(
                        GenerationJobModel.created_at
                    )
                    .with_for_update(
                        skip_locked= True
                    )
                    .limit(1)
                )

                result = await session.execute(stmt)

                job = result.scalar_one_or_none()

                if job is None:
                    return None
                job.status = "running"
                job.worker_id = worker_id
                if job.started_at is None:
                    job.started_at = datetime.now(timezone.utc)

                job.updated_at = datetime.now(timezone.utc)
                return job.generation_id  
            
    async def _get_job(
        self,
        *,
        generation_id: str,
        user_id: str | None = None,
    ) -> GenerationJob | None:

        async with self._session_factory() as session:

            # 1. 查询 Job
            conditions = [
                GenerationJobModel.generation_id
                == generation_id
            ]
            if user_id is not None:
                conditions.append(
                    GenerationJobModel.user_id == user_id
                )
            job_stmt = (
                select(GenerationJobModel)
                .where(
                    *conditions
                )
            )

            job_result = await session.execute(job_stmt)
            job_model = job_result.scalar_one_or_none()

            if job_model is None:
                return None

            # 2. 查询这个 Job 的所有 Stage
            stage_stmt = (
                select(GenerationStageModel)
                .where(
                    GenerationStageModel.generation_id
                    == generation_id
                )
            )

            stage_result = await session.execute(stage_stmt)

            stage_models = list(
                stage_result.scalars().all()
            )
            stage_models.sort(
                key = lambda stage: STAGE_ORDER.get(
                    stage.stage,
                    999,
                )
            )
            # 3. ORM Model → Pydantic Schema
            stages = [
                GenerationStage(
                    stage=stage.stage,
                    status=stage.status,
                    attempt_count=stage.attempt_count,
                    started_at=stage.started_at,
                    finished_at=stage.finished_at,
                    error_code=stage.error_code,
                    error_message=stage.error_message,
                )
                for stage in stage_models
            ]

            return GenerationJob(
                generation_id=job_model.generation_id,
                user_id=job_model.user_id,
                target_course_id= job_model.target_course_id,
                status=job_model.status,
                stages=stages,

                learning_brief=(
                    LearningBriefContent.model_validate(
                        job_model.learning_brief
                    )
                ),

                research_result=(
                    ResearchResult.model_validate(
                        job_model.research_result
                    )
                    if job_model.research_result
                    is not None
                    else None
                ),

                outline_v1=(
                    CourseOutline.model_validate(
                        job_model.outline_v1
                    )
                    if job_model.outline_v1
                    is not None
                    else None
                ),

                critique_result=(
                    CritiqueResult.model_validate(
                        job_model.critique_result
                    )
                    if job_model.critique_result
                    is not None
                    else None
                ),

                final_outline=(
                    CourseOutline.model_validate(
                        job_model.final_outline
                    )
                    if job_model.final_outline
                    is not None
                    else None
                ),

                cancel_requested=job_model.cancel_requested,

                created_at=job_model.created_at,
                started_at=job_model.started_at,
                finished_at=job_model.finished_at,
                updated_at=job_model.updated_at,

                error_code=job_model.error_code,
                error_message=job_model.error_message,
            )
    async def get_job(
        self,
        *,
        generation_id:str,
    )-> GenerationJob | None:
        return await self._get_job(
            generation_id = generation_id,
        )
    async def get_job_for_user(
        self,
        *,
        generation_id:str,
        user_id:str,
    )->GenerationJob | None:
        return await self._get_job(
            generation_id= generation_id,
            user_id=user_id,
        )

    async def get_active_job_for_target_course(
        self,
        *,
        target_course_id: str,
    ) -> GenerationJob | None:

        async with self._session_factory() as session:

            stmt = (
                select(GenerationJobModel)
                .where(
                    GenerationJobModel.target_course_id
                    == target_course_id,
                    GenerationJobModel.status.in_(
                        ["pending", "running"]
                    ),
                )
                .order_by(
                    GenerationJobModel.created_at.desc()
                )
                .limit(1)
            )

            result = await session.execute(stmt)
            job_model = result.scalar_one_or_none()

            if job_model is None:
                return None

            return await self._get_job(
                generation_id=job_model.generation_id,
            )

    async def request_cancel(
    self,
    *,
    generation_id: str,
    user_id: str,
    ) -> CancelResult:

        async with self._session_factory() as session:
            async with session.begin():

                stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id
                        == generation_id,
                        GenerationJobModel.user_id
                        == user_id,
                    )
                    .with_for_update()
                )

                result = await session.execute(stmt)

                job = result.scalar_one_or_none()

                if job is None:
                    return "not_found"

                now = datetime.now(timezone.utc)

                # 还没有被 Worker 领取
                if job.status == "pending":
                    job.status = "cancelled"
                    job.cancel_requested = True
                    job.finished_at = now
                    job.updated_at = now
                    return "cancelled_now"
                # Worker 正在执行
                elif job.status == "running":
                    job.cancel_requested = True
                    job.updated_at = now
                    return "cancel_requested"
                elif job.status == "completed":
                    return "already_completed"
                elif job.status == "failed":
                    return "already_failed"

                return "already_cancelled"
        

    async def mark_stage_running(
        self,
        *,
        generation_id: str,
        stage: str,
    ):   
        async with self._session_factory() as session:
            async with session.begin():

                stmt = (
                    select(GenerationStageModel)
                    .where(
                        GenerationStageModel.generation_id
                        == generation_id,
                        GenerationStageModel.stage
                        ==stage,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                stage_model = result.scalar_one_or_none()

                if stage_model is None:
                    raise RuntimeError(
                        f"Generation stage not found:"
                        f"{generation_id}/{stage}"
                    )
                now = datetime.now(timezone.utc)

                stage_model.status = "running"
                stage_model.attempt_count += 1
                stage_model.started_at = now
                
                stage_model.finished_at = None
                stage_model.error_code = None
                stage_model.error_message = None
                #更新job开始的活跃时间
                job_stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id == generation_id
                    )
                    .with_for_update()
                )
                job_result = await session.execute(job_stmt)
                job = job_result.scalar_one()

                job.updated_at = now

    async def mark_stage_completed(
        self,
        *,
        generation_id: str,
        stage: str,
        snapshot: dict | None = None,
    ):
        snapshot_field = STAGE_SNAPSHOT_FIELDS.get(stage)

        if (
            snapshot_field is None
            and stage not in {"draft", "final_check"}
        ):
            raise ValueError(
                f"Unsupported stage: {stage}"
            )

        if (
            snapshot_field is not None
            and snapshot is None
        ):
            raise ValueError(
                f"Snapshot is required for stage: {stage}"
            )

        async with self._session_factory() as session:
            async with session.begin():
                stage_stmt = (
                    select(GenerationStageModel)
                    .where(
                        GenerationStageModel.generation_id
                        == generation_id,
                        GenerationStageModel.stage == stage,
                    )
                    .with_for_update()
                )
                stage_result = await session.execute(
                    stage_stmt
                )
                stage_model = (
                    stage_result.scalar_one_or_none()
                )

                if stage_model is None:
                    raise RuntimeError(
                        f"Generation stage not found: "
                        f"{generation_id}/{stage}"
                    )

                job_stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id
                        == generation_id
                    )
                    .with_for_update()
                )
                job_result = await session.execute(
                    job_stmt
                )
                job_model = job_result.scalar_one_or_none()

                if job_model is None:
                    raise RuntimeError(
                        f"Generation job not found: "
                        f"{generation_id}"
                    )

                now = datetime.now(timezone.utc)

                if snapshot_field is not None:
                    setattr(
                        job_model,
                        snapshot_field,
                        snapshot,
                    )

                stage_model.status = "completed"
                stage_model.finished_at = now
                stage_model.error_code = None
                stage_model.error_message = None
                job_model.updated_at = now


        

    async def mark_stage_failed(
        self,
        *,
        generation_id: str,
        stage: str,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():

                # 1. 锁 Stage
                stage_stmt = (
                    select(GenerationStageModel)
                    .where(
                        GenerationStageModel.generation_id == generation_id,
                        GenerationStageModel.stage == stage,
                    )
                    .with_for_update()
                )

                stage_result = await session.execute(stage_stmt)
                stage_model = stage_result.scalar_one_or_none()

                if stage_model is None:
                    raise RuntimeError(
                        f"Generation stage not found: "
                        f"{generation_id}/{stage}"
                    )

                # 2. 锁 Job
                job_stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id == generation_id
                    )
                    .with_for_update()
                )

                job_result = await session.execute(job_stmt)
                job_model = job_result.scalar_one_or_none()

                if job_model is None:
                    raise RuntimeError(
                        f"Generation job not found: {generation_id}"
                    )

                now = datetime.now(timezone.utc)

                # 3. Stage 标记失败
                stage_model.status = "failed"
                stage_model.finished_at = now
                stage_model.error_code = error_code
                stage_model.error_message = error_message

                # 4. 更新 Job 活跃时间
                job_model.updated_at = now

    async def mark_job_completed(
        self,
        *,
        generation_id: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():

                stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id == generation_id
                    )
                    .with_for_update()
                )

                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if job is None:
                    raise RuntimeError(
                        f"Generation job not found: {generation_id}"
                    )

                now = datetime.now(timezone.utc)

                job.status = "completed"
                job.finished_at = now
                job.updated_at = now
                job.worker_id = None

    async def mark_job_failed(
        self,
        *,
        generation_id: str,
        error_code:str,
        error_message:str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():

                stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id == generation_id
                    )
                    .with_for_update()
                )

                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if job is None:
                    raise RuntimeError(
                        f"Generation job not found: {generation_id}"
                    )

                now = datetime.now(timezone.utc)

                job.status = "failed"
                
                job.error_code = error_code
                job.error_message = error_message

                job.finished_at = now
                job.updated_at = now
                job.worker_id = None

    async def mark_job_cancelled(
        self,
        *,
        generation_id: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():

                stmt = (
                    select(GenerationJobModel)
                    .where(
                        GenerationJobModel.generation_id
                        == generation_id
                    )
                    .with_for_update()
                )

                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if job is None:
                    raise RuntimeError(
                        f"Generation job not found: {generation_id}"
                    )

                if job.status == "cancelled":
                    return

                if job.status != "running":
                    raise RuntimeError(
                        f"Cannot cancel generation job "
                        f"{generation_id} from status {job.status}"
                    )

                now = datetime.now(timezone.utc)

                job.status = "cancelled"
                job.cancel_requested = True
                job.finished_at = now
                job.updated_at = now
                job.worker_id = None

    async def mark_stage_cancelled(
        self,
        *,
        generation_id: str,
        stage: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(GenerationStageModel)
                    .where(
                        GenerationStageModel.generation_id
                        == generation_id,
                        GenerationStageModel.stage == stage,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                stage_model = result.scalar_one_or_none()

                if stage_model is None:
                    raise RuntimeError(
                        f"Generation stage not found: "
                        f"{generation_id}/{stage}"
                    )

                now = datetime.now(timezone.utc)
                stage_model.status = "cancelled"
                stage_model.finished_at = now
                stage_model.error_code = None
                stage_model.error_message = None

    async def list_section_results(
        self,
        *,
        generation_id: str,
    ) -> list[GenerationSectionResult]:
        async with self._session_factory() as session:
            stmt = (
                select(GenerationSectionResultModel)
                .where(
                    GenerationSectionResultModel.generation_id
                    == generation_id
                )
                .order_by(
                    GenerationSectionResultModel.module_order,
                    GenerationSectionResultModel.chapter_order,
                    GenerationSectionResultModel.section_order,
                )
            )
            result = await session.execute(stmt)
            models = list(result.scalars().all())

        return [
            self._to_section_result(model)
            for model in models
        ]

    @staticmethod
    def _to_section_result(
        model: GenerationSectionResultModel,
    ) -> GenerationSectionResult:
        return GenerationSectionResult(
            generation_id=model.generation_id,
            module_order=model.module_order,
            chapter_order=model.chapter_order,
            section_order=model.section_order,
            retrieval_queries=list(
                model.retrieval_queries or []
            ),
            retrieved_context=(
                model.retrieved_context or ""
            ),
            retrieved_references=[
                CourseSectionSourceReference.model_validate(
                    item
                )
                for item in (
                    model.retrieved_references or []
                )
            ],
            draft_content=model.draft_content,
            draft_cited_source_numbers=list(
                model.draft_cited_source_numbers or []
            ),
            final_content=model.final_content,
            final_references=[
                CourseSectionSourceReference.model_validate(
                    item
                )
                for item in (
                    model.final_references or []
                )
            ],
        )


    async def save_section_draft(
        self,
        *,
        generation_id: str,
        module_order: int,
        chapter_order: int,
        section_order: int,
        retrieval_queries: list[str],
        retrieved_context: str,
        retrieved_references: list[
            CourseSectionSourceReference
        ],
        draft_result: SectionContentResult,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(GenerationSectionResultModel)
                    .where(
                        GenerationSectionResultModel.generation_id
                        == generation_id,
                        GenerationSectionResultModel.module_order
                        == module_order,
                        GenerationSectionResultModel.chapter_order
                        == chapter_order,
                        GenerationSectionResultModel.section_order
                        == section_order,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if model is None:
                    model = GenerationSectionResultModel(
                        generation_id=generation_id,
                        module_order=module_order,
                        chapter_order=chapter_order,
                        section_order=section_order,
                    )
                    session.add(model)

                model.retrieval_queries = list(
                    retrieval_queries
                )
                model.retrieved_context = retrieved_context
                model.retrieved_references = [
                    item.model_dump(mode="json")
                    for item in retrieved_references
                ]
                model.draft_content = draft_result.content
                model.draft_cited_source_numbers = list(
                    draft_result.cited_source_numbers
                )

                # 如果未来真的重写 Draft，旧 Final 不能继续有效
                model.final_content = None
                model.final_references = []

                model.updated_at = datetime.now(
                    timezone.utc
                )

    async def save_section_final(
        self,
        *,
        generation_id: str,
        module_order: int,
        chapter_order: int,
        section_order: int,
        final_result: SectionContentResult,
        final_references: list[
            CourseSectionSourceReference
        ],
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(GenerationSectionResultModel)
                    .where(
                        GenerationSectionResultModel.generation_id
                        == generation_id,
                        GenerationSectionResultModel.module_order
                        == module_order,
                        GenerationSectionResultModel.chapter_order
                        == chapter_order,
                        GenerationSectionResultModel.section_order
                        == section_order,
                    )
                    .with_for_update()
                )
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if (
                    model is None
                    or model.draft_content is None
                ):
                    raise RuntimeError(
                        "Section draft result not found: "
                        f"{generation_id}/"
                        f"{module_order}/"
                        f"{chapter_order}/"
                        f"{section_order}"
                    )

                model.final_content = final_result.content
                model.final_references = [
                    item.model_dump(mode="json")
                    for item in final_references
                ]
                model.updated_at = datetime.now(
                    timezone.utc
                )