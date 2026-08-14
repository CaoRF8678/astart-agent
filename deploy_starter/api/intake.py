import uuid

from fastapi.responses import JSONResponse

from services.intake_service import IntakeServiceError,IntakeService
from schemas.intake import IntakeRequest
from schemas.common import ErrorDetail, ErrorResponse

INTAKE_ERROR_STATUS_CODES = {
    "INTAKE_SESSION_NOT_FOUND": 404,
    "INTAKE_SESSION_COMPLETED": 409,
    "INTAKE_SESSION_CANCELLED": 409,
    "INTAKE_SESSION_EXPIRED": 410,
    "INTAKE_INVALID_AGENT_OUTPUT": 502,
    "INTAKE_AGENT_FAILED": 502,
}

def register_intake_routes(
    agent_app,
    intake_service: IntakeService,
):
    @agent_app.endpoint(
        "/intake",
        methods=["POST"],
    )
    async def intake(
        body: IntakeRequest,
    ):
        request_id = f"req_{uuid.uuid4()}"
        try:
            return await intake_service.handle_turn(intake_request=body,request_id=request_id)

        except IntakeServiceError as exc:
            error_response = ErrorResponse(
                request_id= exc.request_id,
                error = ErrorDetail(
                    code = exc.code,
                    message= exc.message,
                )
            )
            return JSONResponse(
                status_code = INTAKE_ERROR_STATUS_CODES.get(
                    exc.code,
                    500,
                    ),
                content= error_response.model_dump(),
            )

        except Exception:
            error_response = ErrorResponse(
            request_id=  request_id,
            error = ErrorDetail(
                code = "INTERNAL_SERVER_ERROR", 
                message = "An unexpected server error occurred.",
            ),
            )
            return JSONResponse(
                status_code= 500,
                content= error_response.model_dump(),
            ) 
