#负责API业务的create get status cancel

import uuid
from datetime import datetime, timezone
from schemas.generation import CourseGenerationRequest,CourseGenerationAcceptedResponse
from schemas.generation import CourseGenerationCancelRequest,CourseGenerationCancelResponse,CourseGenerationStatusResponse
from schemas.generation import CourseRegenerationRequest
class CourseGenerationServiceError(Exception):

    def __init__(
        self,
        *,
        request_id: str,
        code: str,
        message: str,
    ):
        super().__init__(message)

        self.request_id = request_id
        self.code = code
        self.message = message

class CourseGenerationService:

    def __init__(
            self,
            repository,
            course_repository,
            ):
        self.repository = repository
        self.course_repository  = course_repository


    async def create_generation(
        self,
        *,
        request: CourseGenerationRequest,
        request_id: str,
    ) -> CourseGenerationAcceptedResponse:

        generation_id = f"gen_{uuid.uuid4()}"

        await self.repository.create_job(
            generation_id=generation_id,
            user_id=request.user_id,
            brief=request.brief,
        )   


        return CourseGenerationAcceptedResponse(
            request_id = request_id,
            generation_id = generation_id,
            status = "pending",
            created_at = datetime.now (timezone.utc)
        )
    
    async def cancel_generation(
            self,
            *,
            request: CourseGenerationCancelRequest,
            request_id: str,
            generation_id: str,
    )-> CourseGenerationCancelResponse:

        result = await self.repository.request_cancel(
            generation_id=generation_id,
            user_id=request.user_id,
        )

        if result == "not_found":
            raise CourseGenerationServiceError(
            request_id=request_id,
            code="GENERATION_NOT_FOUND",
            message="Course generation job not found.",
            )

        if result in (
            "already_completed",
            "already_failed",
            ):
            raise CourseGenerationServiceError(
            request_id=request_id,
            code="GENERATION_ALREADY_FINISHED",
            message="Course generation job has already finished.",
            )

        if result == "already_cancelled":
            raise CourseGenerationServiceError(
            request_id=request_id,
            code="GENERATION_CANCEL_CONFLICT",
            message="Course generation job has already been cancelled.",
            )

        if result == "cancelled_now":
            status = "cancelled"
        else:
        # result == "cancel_requested"
            status = "running"

        return CourseGenerationCancelResponse(
            request_id=request_id,
            generation_id=generation_id,
            status=status,
            cancel_requested=True,
        )
    async def get_generation_status(
        self,
        *,
        generation_id: str,
        user_id: str,
        request_id: str,
    ) -> CourseGenerationStatusResponse:

        # 1. 查询属于这个用户的 Job
        job = await self.repository.get_job_for_user(
            generation_id=generation_id,
            user_id=user_id,
        )

        # 2. Job 不存在
        if job is None:
            raise CourseGenerationServiceError(
                request_id=request_id,
                code="GENERATION_NOT_FOUND",
                message="Course generation job not found.",
            )

        # 3. 找当前正在执行的 Stage
        current_stage = next(
            (
                stage.stage
                for stage in job.stages
                if stage.status == "running"
            ),
            None,
        )
        course_id = None

        if job.status == "completed":
            course_id = (
                await self.course_repository
                .get_course_id_by_generation(
                    generation_id=generation_id,
                )
            )
        return CourseGenerationStatusResponse(
            request_id=request_id,
            generation_id=job.generation_id,
            status=job.status,
            course_id= course_id,
            current_stage=current_stage,
            stages=job.stages,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            final_outline=job.final_outline,
            error_code=job.error_code,
            error_message=job.error_message,
        )

    async def create_regeneration(
        self,
        *,
        course_id: str,
        request: CourseRegenerationRequest,
        request_id: str,
    ) -> CourseGenerationAcceptedResponse:

        # 1. 确认课程存在，并且属于当前用户
        course = await self.course_repository.get_course_for_user(
            course_id=course_id,
            user_id=request.user_id,
        )

        if course is None:
            raise CourseGenerationServiceError(
                request_id=request_id,
                code="COURSE_NOT_FOUND",
                message="Course not found.",
            )

        # 2. 找到这门课程最初的 Generation Job
        original_job = await self.repository.get_job_for_user(
            generation_id=course.generation_id,
            user_id=request.user_id,
        )

        if original_job is None:
            raise CourseGenerationServiceError(
                request_id=request_id,
                code="GENERATION_NOT_FOUND",
                message="Original course generation job not found.",
            )

        # 3. 检查是否已经有正在执行的 regeneration
        active_job = (
            await self.repository
            .get_active_job_for_target_course(
                target_course_id=course_id,
            )
        )

        if active_job is not None:
            raise CourseGenerationServiceError(
                request_id=request_id,
                code="COURSE_REGENERATION_IN_PROGRESS",
                message="Course regeneration is already in progress.",
            )

        # 4. 创建新的 Generation ID
        generation_id = f"gen_{uuid.uuid4()}"

        # 5. 创建新的 Generation Job
        #    复用原课程最初的 LearningBrief
        await self.repository.create_job(
            generation_id=generation_id,
            user_id=request.user_id,
            brief=original_job.learning_brief,
            target_course_id=course_id,
        )

        # 6. 返回 pending
        return CourseGenerationAcceptedResponse(
            request_id=request_id,
            generation_id=generation_id,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )