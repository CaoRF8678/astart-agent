import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from services.chat_service import ChatServiceError, execute_chat

from schemas.chat import ChatRequest
from schemas.common import ErrorDetail, ErrorResponse

def register_chat_routes(agent_app):
    @agent_app.endpoint("/chat", methods=["POST"])
    async def chat(
        request: Request,
        body: ChatRequest
    ):
        request_id = f"req_{uuid.uuid4()}"
        #1、获取runner
        runner = getattr(request.app.state,"runner",None)
        #2\如果runner为none
        if runner is None:
            error_response = ErrorResponse(
                request_id = request_id,
                error = ErrorDetail(
                    code = "SERVICE_NOT_READY",
                    message = "Runner is not initialized."
                )
            )
            return JSONResponse(
                status_code= 503,
                content= error_response.model_dump(), #转换为python字典

            )
        #3、调用service
        try:
            response = await execute_chat(
                runner = runner,
                chat_request= body,
                request_id= request_id,
            )
            return response
        #4、ChatServiceError
        except ChatServiceError as exc:
            error_response = ErrorResponse(
                request_id = exc.request_id,
                error = ErrorDetail(
                    code = exc.code, 
                    message = exc.message,
                ),
            )
            return JSONResponse(
                status_code= 502,
                content= error_response.model_dump(),
            )
        #未知异常
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




