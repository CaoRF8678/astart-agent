from schemas.course import (
    CourseDetailResponse,
    CourseListResponse,
)


class CourseServiceError(Exception):
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


class CourseService:
    def __init__(self, repository):
        self.repository = repository
    async def list_courses(
        self,
        *,
        user_id: str,
        request_id: str,
    ) -> CourseListResponse:

        courses = await self.repository.list_courses_for_user(
            user_id=user_id,
        )

        return CourseListResponse(
            request_id=request_id,
            courses=courses,
        )
    
    async def get_course(
        self,
        *,
        course_id: str,
        user_id: str,
        request_id: str,
    ) -> CourseDetailResponse:

        course = await self.repository.get_course_for_user(
            course_id=course_id,
            user_id=user_id,
        )

        if course is None:
            raise CourseServiceError(
                request_id=request_id,
                code="COURSE_NOT_FOUND",
                message="Course not found.",
            )

        return CourseDetailResponse(
            request_id=request_id,
            course=course,
        )