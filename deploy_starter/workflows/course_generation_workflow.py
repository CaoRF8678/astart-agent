# 整个workflow的编排器 负责状态，顺序，取消，恢复，不负责HTTP

from schemas.generation import (
    CritiqueResult,
    ResearchResult,
    SectionGenerationTarget,
)

from schemas.course import (
    CourseOutline,
    CourseSectionSourceReference,
)

from database.repositories.generation_repository import GenerationRepository
from database.repositories.course_repository import CourseRepository
from stage.research import run_research
from stage.outline import run_outline
from stage.critique import run_critique
from stage.revision import run_revision
from stage.draft import (
    plan_section_retrieval_queries,
    run_section_draft,
)
from stage.final_check import (
    run_section_final_check,
)
from rag.context_builder import build_context


def _flatten_section_targets(
    outline: CourseOutline,
) -> list[SectionGenerationTarget]:
    targets: list[SectionGenerationTarget] = []

    for module_order, module in enumerate(
        outline.modules
    ):
        for chapter_order, chapter in enumerate(
            module.chapters
        ):
            for section_order, section in enumerate(
                chapter.sections
            ):
                targets.append(
                    SectionGenerationTarget(
                        module_title=module.title,
                        chapter_title=chapter.title,
                        chapter_learning_objectives=(
                            chapter.learning_objectives
                        ),
                        section_title=section.title,
                        module_order=module_order,
                        chapter_order=chapter_order,
                        section_order=section_order,
                        estimated_minutes=(
                            section.estimated_minutes
                        ),
                    )
                )

    return targets


def _validate_cited_source_numbers(
    numbers: list[int],
    *,
    source_count: int,
) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()

    for number in numbers:
        if number < 1 or number > source_count:
            raise ValueError(
                "Invalid cited source number: "
                f"{number}; source_count={source_count}"
            )

        if number in seen:
            continue

        seen.add(number)
        normalized.append(number)

    return normalized


def _position_key(
    target: SectionGenerationTarget,
) -> tuple[int, int, int]:
    return (
        target.module_order,
        target.chapter_order,
        target.section_order,
    )


def _build_previous_section_context(
    previous: list[tuple[str, str]],
    *,
    max_chars: int = 4000,
) -> str:
    selected: list[str] = []
    current_length = 0

    for title, content in reversed(previous):
        block = (
            f"小节：{title}\n"
            f"正文：\n{content}"
        )
        separator = 2 if selected else 0
        remaining = (
            max_chars
            - current_length
            - separator
        )

        if remaining <= 0:
            break

        if len(block) > remaining:
            if not selected:
                selected.append(block[:remaining])
            break

        selected.append(block)
        current_length += (
            separator + len(block)
        )

    selected.reverse()
    return "\n\n".join(selected)


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
        repository: GenerationRepository,
        course_repository: CourseRepository,
        stage_runner,
        multi_query_retriever,
        rag_max_context_chars: int,
    ):
        self.repository = repository
        self.course_repository = course_repository
        self.stage_runner = stage_runner
        self.multi_query_retriever = multi_query_retriever
        self.rag_max_context_chars = rag_max_context_chars

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

        if job is None:
            raise RuntimeError(
                f"Generation job not found: {generation_id}"
            )

        # LearningBrief 已经在创建 Job 时
        # 保存进 PostgreSQL
        brief = job.learning_brief

        # =========================
        # 2. Research
        # =========================

        research_stage = _get_stage(
            job,
            "research",
        )

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
                    course_id=job.target_course_id,
                    multi_query_retriever=(
                        self.multi_query_retriever
                    ),
                    max_context_chars=(
                        self.rag_max_context_chars
                    ),
                )

                await self.repository.mark_stage_completed(
                    generation_id=generation_id,
                    stage="research",
                    snapshot=research_result.model_dump(
                        mode="json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="research",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
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

        outline_stage = _get_stage(
            job,
            "outline",
        )

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
                    generation_id=generation_id,
                    stage="outline",
                    snapshot=outline_v1.model_dump(
                        mode="json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="outline",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise

        # =========================
        # 5. Cancellation Check
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
        # 6. Critique
        # =========================

        critique_stage = _get_stage(
            job,
            "critique",
        )

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
                    runner=self.stage_runner,
                    brief=brief,
                    research_result=research_result,
                    outline_v1=outline_v1,
                )

                await self.repository.mark_stage_completed(
                    generation_id=generation_id,
                    stage="critique",
                    snapshot=critique_result.model_dump(
                        mode="json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="critique",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise

        # =========================
        # 7. Cancellation Check
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
        # 8. Revision
        # =========================

        revision_stage = _get_stage(
            job,
            "revision",
        )

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
                    runner=self.stage_runner,
                    brief=brief,
                    research_result=research_result,
                    outline_v1=outline_v1,
                    critique_result=critique_result,
                )

                await self.repository.mark_stage_completed(
                    generation_id=generation_id,
                    stage="revision",
                    snapshot=revision_result.model_dump(
                        mode="json"
                    ),
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="revision",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise

        # Revision 后再做一次取消检查
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

        # Final Outline 展平成逐 Section 任务列表
        targets = _flatten_section_targets(
            revision_result
        )

        # =========================
        # 9. Draft
        # =========================

        draft_stage = _get_stage(
            job,
            "draft",
        )

        if draft_stage.status != "completed":
            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="draft",
            )

            try:
                existing_results = (
                    await self.repository
                    .list_section_results(
                        generation_id=generation_id
                    )
                )

                result_by_position = {
                    (
                        item.module_order,
                        item.chapter_order,
                        item.section_order,
                    ): item
                    for item in existing_results
                }

                for target in targets:

                    # 每生成下一个 Section 前，
                    # 都重新检查用户是否请求取消
                    current_job = await self.repository.get_job(
                        generation_id=generation_id
                    )

                    if current_job is None:
                        raise RuntimeError(
                            "Generation job not found: "
                            f"{generation_id}"
                        )

                    if current_job.cancel_requested:
                        await self.repository.mark_stage_cancelled(
                            generation_id=generation_id,
                            stage="draft",
                        )

                        await self.repository.mark_job_cancelled(
                            generation_id=generation_id,
                        )
                        return

                    position = _position_key(target)

                    existing = result_by_position.get(
                        position
                    )

                    if (
                        existing is not None
                        and existing.draft_content is not None
                    ):
                        continue

                    # 当前 Section 自己的 RAG 数据
                    queries: list[str] = []
                    retrieved_context = ""

                    references: list[
                        CourseSectionSourceReference
                    ] = []

                    # Regeneration 才存在已有 Course，
                    # 因此才执行课程资料 RAG
                    if job.target_course_id is not None:

                        queries = (
                            await plan_section_retrieval_queries(
                                runner=self.stage_runner,
                                brief=brief,
                                research_result=research_result,
                                course_title=(
                                    revision_result.title
                                ),
                                course_description=(
                                    revision_result.description
                                ),
                                target=target,
                            )
                        )

                        retrieved = await (
                            self.multi_query_retriever
                            .retrieve_many(
                                course_id=(
                                    job.target_course_id
                                ),
                                queries=queries,
                            )
                        )

                        (
                            retrieved_context,
                            used_segments,
                        ) = build_context(
                            retrieved,
                            max_chars=(
                                self.rag_max_context_chars
                            ),
                        )

                        references = [
                            CourseSectionSourceReference(
                                segment_id=item.segment_id,
                                file_id=item.file_id,
                                filename=item.filename,
                                locator=item.locator,
                                similarity_score=(
                                    item.similarity_score
                                ),
                            )
                            for item in used_segments
                        ]

                    module = revision_result.modules[
                        target.module_order
                    ]

                    chapter = module.chapters[
                        target.chapter_order
                    ]

                    sibling_titles = [
                        item.title
                        for item in chapter.sections
                    ]

                    draft_result = await run_section_draft(
                        runner=self.stage_runner,
                        brief=brief,
                        research_result=research_result,
                        course_title=revision_result.title,
                        course_description=(
                            revision_result.description
                        ),
                        target=target,
                        sibling_section_titles=(
                            sibling_titles
                        ),
                        retrieved_material_context=(
                            retrieved_context
                        ),
                    )

                    # 校验 LLM 返回的 Source 编号
                    draft_numbers = (
                        _validate_cited_source_numbers(
                            draft_result.cited_source_numbers,
                            source_count=len(references),
                        )
                    )

                    draft_result = draft_result.model_copy(
                        update={
                            "cited_source_numbers": (
                                draft_numbers
                            )
                        }
                    )

                    # 保存当前 Section 的 Draft Snapshot
                    await self.repository.save_section_draft(
                        generation_id=generation_id,
                        module_order=target.module_order,
                        chapter_order=target.chapter_order,
                        section_order=target.section_order,
                        retrieval_queries=queries,
                        retrieved_context=retrieved_context,
                        retrieved_references=references,
                        draft_result=draft_result,
                    )

                await self.repository.mark_stage_completed(
                    generation_id=generation_id,
                    stage="draft",
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="draft",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise

        # =========================
        # 10. Final Check
        # =========================

        final_check_stage = _get_stage(
            job,
            "final_check",
        )

        if final_check_stage.status != "completed":
            await self.repository.mark_stage_running(
                generation_id=generation_id,
                stage="final_check",
            )

            try:
                section_results = (
                    await self.repository
                    .list_section_results(
                        generation_id=generation_id
                    )
                )

                result_by_position = {
                    (
                        item.module_order,
                        item.chapter_order,
                        item.section_order,
                    ): item
                    for item in section_results
                }

                # 保存已经完成 Final Check 的前文，
                # 后面用于判断当前 Section 是否重复
                previous_final_sections: list[
                    tuple[str, str]
                ] = []

                for target in targets:

                    # 每检查下一个 Section 前，
                    # 都重新检查用户是否请求取消
                    current_job = await self.repository.get_job(
                        generation_id=generation_id
                    )

                    if current_job is None:
                        raise RuntimeError(
                            "Generation job not found: "
                            f"{generation_id}"
                        )

                    if current_job.cancel_requested:
                        await self.repository.mark_stage_cancelled(
                            generation_id=generation_id,
                            stage="final_check",
                        )

                        await self.repository.mark_job_cancelled(
                            generation_id=generation_id,
                        )
                        return

                    position = _position_key(target)

                    item = result_by_position.get(
                        position
                    )

                    # Final Check 必须建立在已有 Draft 上
                    if (
                        item is None
                        or item.draft_content is None
                    ):
                        raise RuntimeError(
                            "Section draft result is missing: "
                            f"{position}"
                        )

                    # 如果这一节以前已经完成 Final Check，
                    # 就把它加入前文，然后跳过重新生成
                    if item.final_content is not None:
                        previous_final_sections.append(
                            (
                                target.section_title,
                                item.final_content,
                            )
                        )
                        continue

                    previous_context = (
                        _build_previous_section_context(
                            previous_final_sections
                        )
                    )

                    final_result = (
                        await run_section_final_check(
                            runner=self.stage_runner,
                            brief=brief,
                            research_result=research_result,
                            course_title=(
                                revision_result.title
                            ),
                            target=target,
                            draft_content=(
                                item.draft_content
                            ),
                            retrieved_material_context=(
                                item.retrieved_context
                            ),
                            previous_section_context=(
                                previous_context
                            ),
                        )
                    )

                    # 校验 Final Check 返回的 Source 编号
                    final_numbers = (
                        _validate_cited_source_numbers(
                            final_result.cited_source_numbers,
                            source_count=len(
                                item.retrieved_references
                            ),
                        )
                    )

                    final_result = final_result.model_copy(
                        update={
                            "cited_source_numbers": (
                                final_numbers
                            )
                        }
                    )

                    # build_context()：
                    #
                    # Source 1
                    # → retrieved_references[0]
                    #
                    # Source 2
                    # → retrieved_references[1]
                    #
                    # 所以 LLM 返回 Source N，
                    # Python 需要取 list[N - 1]
                    final_references = [
                        item.retrieved_references[
                            number - 1
                        ]
                        for number in final_numbers
                    ]

                    await self.repository.save_section_final(
                        generation_id=generation_id,
                        module_order=target.module_order,
                        chapter_order=target.chapter_order,
                        section_order=target.section_order,
                        final_result=final_result,
                        final_references=final_references,
                    )

                    # 当前 Section 已经成为最终正文，
                    # 后面的 Section 可以用它检查重复
                    previous_final_sections.append(
                        (
                            target.section_title,
                            final_result.content,
                        )
                    )

                await self.repository.mark_stage_completed(
                    generation_id=generation_id,
                    stage="final_check",
                )

            except Exception as exc:
                error_code = type(exc).__name__
                error_message = str(exc)

                await self.repository.mark_stage_failed(
                    generation_id=generation_id,
                    stage="final_check",
                    error_code=error_code,
                    error_message=error_message,
                )

                await self.repository.mark_job_failed(
                    generation_id=generation_id,
                    error_code=error_code,
                    error_message=error_message,
                )
                raise

        # =========================
        # 11. Publish Course
        # =========================

        # 到这里说明所有 Section 的 Final Check
        # 都已经完成。
        section_results = (
            await self.repository.list_section_results(
                generation_id=generation_id
            )
        )

        try:
            if job.target_course_id is None:

                # 第一次生成：
                # 创建新的正式 Course
                await (
                    self.course_repository
                    .create_from_generation(
                        generation_id=generation_id,
                        user_id=job.user_id,
                        outline=revision_result,
                        section_results=section_results,
                    )
                )

            else:

                # Regeneration：
                # 一次性替换原 Course 的 Outline + Sections
                await (
                    self.course_repository
                    .replace_from_generation(
                        course_id=job.target_course_id,
                        user_id=job.user_id,
                        outline=revision_result,
                        section_results=section_results,
                    )
                )

        except Exception as exc:
            error_code = type(exc).__name__
            error_message = str(exc)

            await self.repository.mark_job_failed(
                generation_id=generation_id,
                error_code=error_code,
                error_message=error_message,
            )
            raise
        # =========================
        # 12. Job Completed
        # =========================

        await self.repository.mark_job_completed(
            generation_id=generation_id,
        )