import logging
import uuid

from fastapi import Query, Request
from fastapi.responses import JSONResponse

from schemas.common import ErrorDetail, ErrorResponse
from schemas.history import HistoryResponse
from services.history_service import (
    HistoryServiceError,
    get_history,
)


logger = logging.getLogger(__name__)


def register_history_routes(agent_app):

    @agent_app.endpoint(
        "/history",
        methods=["GET"],
    )
    async def history(
        request: Request,
        user_id: str = Query(
            ...,
            min_length=1,
            description="The identifier of the user.",
        ),
        session_id: str = Query(
            ...,
            min_length=1,
            description="The identifier of the session.",
        ),
    ) -> HistoryResponse | JSONResponse:

        request_id = f"req_{uuid.uuid4()}"

        # 1. 获取 Runtime Runner
        runner = getattr(
            request.app.state,
            "runner",
            None,
        )

        # 2. Runner 尚未初始化
        if runner is None:
            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="SERVICE_NOT_READY",
                    message="Runner is not initialized.",
                ),
            )

            return JSONResponse(
                status_code=503,
                content=error_response.model_dump(mode="json"),
            )

        # 3. 从 Runner 获取 session_service
        session_service = getattr(
            runner,
            "session_service",
            None,
        )

        if session_service is None:
            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="SERVICE_NOT_READY",
                    message="Session service is not initialized.",
                ),
            )

            return JSONResponse(
                status_code=503,
                content=error_response.model_dump(mode="json"),
            )

        try:
            # 4. 调用业务 Service
            response = await get_history(
                session_service=session_service,
                user_id=user_id,
                session_id=session_id,
            )

            return response

        except HistoryServiceError as exc:
            # 5. 业务异常
            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                ),
            )

            status_code = {
                "SESSION_NOT_FOUND": 404,
            }.get(
                exc.code,
                500,
            )

            return JSONResponse(
                status_code=status_code,
                content=error_response.model_dump(mode="json"),
            )

        except Exception:
            # 6. 未知异常只写入服务器日志，
            # 不把真实异常详情暴露给客户端
            logger.exception(
                "Unhandled /history error, request_id=%s",
                request_id,
            )

            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected server error occurred.",
                ),
            )

            return JSONResponse(
                status_code=500,
                content=error_response.model_dump(mode="json"),
            )