import logging
import uuid

from fastapi.responses import JSONResponse

from schemas.rag import (
    RAGQueryRequest,
)
from services.rag_service import (
    RAGService,
    RAGServiceError,
)


logger = logging.getLogger(__name__)


RAG_ERROR_STATUS = {
    "INVALID_USER_ID": 400,
    "INVALID_QUESTION": 400,
    "COURSE_NOT_FOUND": 404,
    "RAG_EMBEDDING_FAILED": 502,
    "RAG_GENERATION_FAILED": 502,
}


def register_rag_routes(
    agent_app,
    *,
    service: RAGService,
) -> None:
    @agent_app.endpoint(
        "/courses/{course_id}/rag/query",
        methods=["POST"],
    )
    async def query_course_rag(
        course_id: str,
        body: RAGQueryRequest,
    ):
        request_id = (
            f"req_{uuid.uuid4()}"
        )

        try:
            response = await service.query(
                course_id=course_id,
                request=body,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=200,
                content=response.model_dump(
                    mode="json"
                ),
            )

        except RAGServiceError as exc:
            return JSONResponse(
                status_code=(
                    RAG_ERROR_STATUS.get(
                        exc.code,
                        500,
                    )
                ),
                content={
                    "request_id": (
                        exc.request_id
                    ),
                    "error_code": exc.code,
                    "error_message": (
                        exc.message
                    ),
                },
            )

        except Exception:
            logger.exception(
                "Unhandled RAG error, "
                "request_id=%s",
                request_id,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "request_id": request_id,
                    "error_code": (
                        "INTERNAL_SERVER_ERROR"
                    ),
                    "error_message": (
                        "An unexpected server "
                        "error occurred."
                    ),
                },
            )