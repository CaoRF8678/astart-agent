import uuid
from fastapi.responses import JSONResponse

from services.course_generation_service import CourseGenerationService,CourseGenerationServiceError
from schemas.generation import CourseGenerationRequest,CourseGenerationCancelRequest
from schemas.generation import CourseRegenerationRequest
def _service_error_response(
    exc:CourseGenerationServiceError,
):
    status_code_map = {
        "GENERATION_NOT_FOUND": 404,
        "GENERATION_ALREADY_FINISHED": 409,
        "GENERATION_CANCEL_CONFLICT": 409,

        "COURSE_NOT_FOUND":404,
        "COURSE_REGENERATION_IN_PROGRESS":409,
    }
    status_code = status_code_map.get(
        exc.code,
        500,
    )
    return JSONResponse(
        status_code = status_code,
        content={
            "request_id":exc.request_id,
            "error_code":exc.code,
            "error_message":exc.message,
        },
    )
def register_generation_routes(
        agent_app,
        service:CourseGenerationService,
):

    @agent_app.endpoint(
        "/course/generations",
        methods=["POST"],
    )
    async def create_generation(
        body: CourseGenerationRequest,
    ):
        request_id = f"req_{uuid.uuid4()}"
        try:
            response = (   #以及创建好了任务，并且在数据库中也存好了
                await service.create_generation(
                    request=body,
                    request_id=request_id,
                )
            )

            return JSONResponse(
                status_code=202,
                content=response.model_dump(
                    mode="json"
                ),
            )
        except CourseGenerationServiceError as exc:
            return _service_error_response(exc)

    @agent_app.endpoint(
        "/course/generations/{generation_id}",
        methods=["GET"],
    )
    async def query_generation(
        generation_id: str,
        user_id: str,
    ):
        request_id = f"req_{uuid.uuid4()}"
        try:

            response = await service.get_generation_status(
                generation_id=generation_id,
                user_id=user_id,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=200,
                content=response.model_dump(
                    mode="json"
                ),
            )
        except CourseGenerationServiceError as exc:
            return _service_error_response(exc)

    @agent_app.endpoint(
        "/course/generations/{generation_id}/cancel",
        methods = ["POST"],
    )
    async def cancel_generation(
        generation_id:str,
        body:CourseGenerationCancelRequest,
    ):
        request_id = f"req_{uuid.uuid4()}"
        try:
            cancel_result =await service.cancel_generation(
                request = body,
                request_id = request_id,
                generation_id= generation_id,
            )
            return JSONResponse(
                status_code= 202,
                content= cancel_result.model_dump(
                    mode = "json"
                )
            )
        except CourseGenerationServiceError as exc:
            return _service_error_response(exc)

    @agent_app.endpoint(
        "/courses/{course_id}/regenerate",
        methods=["POST"],
    )
    async def regenerate_course(
        course_id: str,
        body: CourseRegenerationRequest,
    ):
        request_id = f"req_{uuid.uuid4()}"

        try:
            response = await service.create_regeneration(
                course_id=course_id,
                request=body,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=202,
                content=response.model_dump(
                    mode="json"
                ),
            )

        except CourseGenerationServiceError as exc:
            return _service_error_response(exc)

        