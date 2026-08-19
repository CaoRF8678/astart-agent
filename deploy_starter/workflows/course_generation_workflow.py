#整个workflow的编排器 负责状态，顺序，取消，恢复，不负责HTTP

from schemas.generation import (
    ResearchResult,
    CritiqueResult,
)
from schemas.course import CourseOutline
from database.repositories.generation_repository import GenerationRepository
from stage.research import run_research
from stage.outline import run_outline
from stage.critique import run_critique
from stage.revision import run_revision

def _get_stage(job, stage_name: str):
    for stage in job.stages:
        if stage.stage == stage_name:
            return stage

    raise RuntimeError(
        f"Generation stage not found: "
        f"{job.generation_id}/{stage_name}"
        )
class CourseGenerationWorkflow:

    def __init__(
        self,
        *,
        repository:GenerationRepository,
        stage_runner,
    ):
        self.repository = repository
        self.stage_runner = stage_runner

    async def run(
        self,
        *,
        generation_id: str,
    ) -> None:

        # =========================
        # 1. 读取 Job
        # =========================

        job = await self.repository.get_job(
            generation_id=generation_id,
        )

        if job is None:   #GenerationJob对象
            raise RuntimeError(
                f"Generation job not found: {generation_id}"
            )

        # LearningBrief 已经在创建 Job 时
        # 保存进 PostgreSQL
        brief = job.learning_brief


        # =========================
        # 2. Research
        # =========================

        research_stage = _get_stage(job, "research")

        if research_stage.status == "completed":
            # 从数据库 Snapshot 恢复
            research_result = ResearchResult.model_validate(
                job.research_result
            )

        else:

            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="research",
            )

            try:
                research_result = await run_research(
                    runner=self.stage_runner,
                    brief=brief,
                )
                await self.repository.mark_stage_completed(
                    generation_id = generation_id,
                    stage = "research",
                    snapshot = research_result.model_dump(
                        mode = "json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)
                
                # research → failed
                await self.repository.mark_stage_failed(
                    generation_id = generation_id,
                    stage = "research",
                    error_code = error_code,
                    error_message = error_message, 
                )
                await self.repository.mark_job_failed(
                    generation_id = generation_id,
                    error_code=error_code,
                    error_message= error_message,
                )
                raise


        # =========================
        # 3. Cancellation Check
        # =========================

        current_job = await self.repository.get_job(
            generation_id=generation_id,
        )

        if current_job is None:
            raise RuntimeError(
                f"Generation job not found: {generation_id}"
            )

        if current_job.cancel_requested:
            await self.repository.mark_job_cancelled(
                generation_id=generation_id,
            )
            return

        # =========================
        # 4. Outline
        # =========================
        outline_stage = _get_stage(job, "outline")
        if outline_stage.status == "completed":
            outline_v1 = CourseOutline.model_validate(
                job.outline_v1
            )

        else:

            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="outline",
            )

            try:
                outline_v1 = await run_outline(
                    runner=self.stage_runner,
                    brief=brief,
                    research_result=research_result,
                )
                await self.repository.mark_stage_completed(
                    generation_id= generation_id,
                    stage= "outline",
                    snapshot= outline_v1.model_dump(
                        mode= "json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id= generation_id,
                    stage = "outline",
                    error_code=  error_code,
                    error_message= error_message,
                )
                await self.repository.mark_job_failed(
                    generation_id = generation_id,
                    error_code=error_code,
                    error_message= error_message,
                )
                raise


        # =========================
        # 5. Cancellation Check
        # =========================

        current_job = await self.repository.get_job(
            generation_id= generation_id,
        )
        if current_job is None:
            raise RuntimeError(
                f"Generation job not found:{generation_id}"
            )
        if current_job.cancel_requested:
            await self.repository.mark_job_cancelled(
                generation_id= generation_id,
            )
            return


        # =========================
        # 6. Critique
        # =========================
        critique_stage = _get_stage(job, "critique")
        if critique_stage.status == "completed":
            critique_result = CritiqueResult.model_validate(
                job.critique_result
            )

        else:

            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="critique",
            )

            try:
                critique_result = await run_critique(
                    runner = self.stage_runner,
                    brief= brief,
                    research_result= research_result,
                    outline_v1=outline_v1,
                )
                await self.repository.mark_stage_completed(
                    generation_id= generation_id,
                    stage= "critique",
                    snapshot= critique_result.model_dump(
                        mode= "json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id= generation_id,
                    stage = "critique",
                    error_code=  error_code,
                    error_message= error_message,
                )
                await self.repository.mark_job_failed(
                    generation_id = generation_id,
                    error_code=error_code,
                    error_message= error_message,
                )
                raise

        # =========================
        # 7. Cancellation Check
        # =========================
        current_job = await self.repository.get_job(
            generation_id= generation_id,
        )
        if current_job is None:
            raise RuntimeError(
                f"Generation job not found:{generation_id}"
            )
        if current_job.cancel_requested:
            await self.repository.mark_job_cancelled(
                generation_id= generation_id,
            )
            return


        # =========================
        # 8. Revision
        # =========================

        revision_stage = _get_stage(job, "revision")
        if revision_stage.status == "completed":
            revision_result = CourseOutline.model_validate(
                job.final_outline
            )

        else:

            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="revision",
            )

            try:
                revision_result = await run_revision(
                    runner = self.stage_runner,
                    brief= brief,
                    research_result= research_result,
                    outline_v1=outline_v1,
                    critique_result= critique_result,
                )
                await self.repository.mark_stage_completed(
                    generation_id= generation_id,
                    stage= "revision",
                    snapshot= revision_result.model_dump(
                        mode= "json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id= generation_id,
                    stage = "revision",
                    error_code=  error_code,
                    error_message= error_message,
                )
                await self.repository.mark_job_failed(
                    generation_id = generation_id,
                    error_code=error_code,
                    error_message= error_message,
                )
                raise

        #revision后再做一次检查
        current_job = await self.repository.get_job(
            generation_id= generation_id,
        )
        if current_job is None:
            raise RuntimeError(
                f"Generation job not found:{generation_id}"
            )
        if current_job.cancel_requested:
            await self.repository.mark_job_cancelled(
                generation_id= generation_id,
            )
            return
        
        # =========================
        # 9. Job Completed
        # =========================
        await self.repository.mark_job_completed(
            generation_id= generation_id,
        )
        