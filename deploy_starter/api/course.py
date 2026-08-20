import uuid

from fastapi.responses import JSONResponse

from services.course_service import (
    CourseService,
    CourseServiceError,
)


def _service_error_response(
    exc: CourseServiceError,
):
    status_code_map = {
        "COURSE_NOT_FOUND": 404,
    }

    return JSONResponse(
        status_code=status_code_map.get(
            exc.code,
            500,
        ),
        content={
            "request_id": exc.request_id,
            "error_code": exc.code,
            "error_message": exc.message,
        },
    )

def register_course_routes(
    agent_app,
    service: CourseService,
):

    @agent_app.endpoint(
        "/courses",
        methods=["GET"],
    )
    async def list_courses(
        user_id: str,
    ):
        request_id = f"req_{uuid.uuid4()}"

        try:
            response = await service.list_courses(
                user_id=user_id,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=200,
                content=response.model_dump(
                    mode="json"
                ),
            )

        except CourseServiceError as exc:
            return _service_error_response(exc)
        
    @agent_app.endpoint(
        "/courses/{course_id}",
        methods=["GET"],
    )
    async def get_course(
        course_id: str,
        user_id: str,
    ):
        request_id = f"req_{uuid.uuid4()}"

        try:
            response = await service.get_course(
                course_id=course_id,
                user_id=user_id,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=200,
                content=response.model_dump(
                    mode="json"
                ),
            )

        except CourseServiceError as exc:
            return _service_error_response(exc)