import logging
import uuid

from fastapi import (
    File,
    Form,
    Request,
    UploadFile,
)

from fastapi.responses import JSONResponse

from schemas.common import (
    ErrorDetail,
    ErrorResponse,
)

from schemas.upload import UploadResponse


from storage.base import FileStorage

from services.upload_service import (
    MAX_FILE_SIZE,
    UploadServiceError,
    list_learning_materials,
    upload_file,
    upload_learning_source,
)
 
logger = logging.getLogger(__name__)


UPLOAD_CHUNK_SIZE = 1024 * 1024

#分块读取上传的内容

UPLOAD_ERROR_STATUS = {
    "INVALID_FILENAME": 400,
    "INVALID_USER_ID": 400,
    "EMPTY_FILE": 400,

    "FILE_TOO_LARGE": 413,

    "UNSUPPORTED_FILE_TYPE": 415,

    "INVALID_FILE_CONTENT": 422,
    "DOCUMENT_PARSE_FAILED": 422,

    "SESSION_NOT_FOUND": 404,
    "COURSE_NOT_FOUND": 404,

    "SERVICE_NOT_READY": 503,

    "FILE_STORAGE_FAILED": 500,
}

def _upload_error_response(
    *,
    request_id: str,
    exc: UploadServiceError,
) -> JSONResponse:

    error_response = ErrorResponse(
        request_id=request_id,
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
        ),
    )

    return JSONResponse(
        status_code=(
            UPLOAD_ERROR_STATUS.get(
                exc.code,
                500,
            )
        ),
        content=error_response.model_dump(
            mode="json"
        ),
    )

async def read_upload_with_limit(
    file: UploadFile,
) -> bytes:

    buffer = bytearray()

    while True:

        # 每次最多读取 1 MB
        chunk = await file.read(UPLOAD_CHUNK_SIZE)

        # 没有内容说明读取结束
        if not chunk:
            break

        # 判断加入这一块以后是否超过 20 MB
        if len(buffer) + len(chunk) > MAX_FILE_SIZE:
            raise UploadServiceError(
                code="FILE_TOO_LARGE",
                message="The uploaded file exceeds the maximum allowed size.",
            )

        # 把这一块加入内存缓冲区
        buffer.extend(chunk)

    return bytes(buffer)



def register_upload_routes(
    agent_app,
    storage: FileStorage,
) -> None:

    @agent_app.endpoint(
        "/upload",
        methods=["POST"],
    )
    async def upload(
        request: Request,

        file: UploadFile = File(...),

        user_id: str = Form(
            ...,
            min_length=1,
        ),

        session_id: str | None = Form(
            default=None,
        ),

    ) -> UploadResponse | JSONResponse:

        request_id = f"req_{uuid.uuid4()}"

        try:

            # 1. 默认没有 session_service
            session_service = None


            # 2. 如果用户传了 session_id，
            #    才需要取得 Runner 和 session_service

            if session_id:

                runner = getattr(
                    request.app.state,
                    "runner",
                    None,
                )

                if runner is None:
                    raise UploadServiceError(
                        code="SERVICE_NOT_READY",
                        message="Runner is not initialized.",
                    )

                session_service = getattr(
                    runner,
                    "session_service",
                    None,
                )

                if session_service is None:
                    raise UploadServiceError(
                        code="SERVICE_NOT_READY",
                        message="Session service is not initialized.",
                    )


            # 3. 有大小限制地读取上传文件
            
            data = await read_upload_with_limit(file)

            # 4. 调用 Service

            response = await upload_file(
                storage=storage,
                filename=file.filename,
                content_type=file.content_type,
                data=data,
                user_id=user_id,
                session_id=session_id,
                session_service=session_service,
            )

            return response


        except UploadServiceError as exc:
            return _upload_error_response(
                request_id=request_id,
                exc = exc,
            )


        except Exception:

            logger.exception(
                "Unhandled /upload error, request_id=%s",
                request_id,
            )

            # 这里你自己按照 /chat、/history
            # 的 INTERNAL_SERVER_ERROR 风格完成
            error_response = ErrorResponse(
                request_id= request_id,
                error= ErrorDetail(
                    code = "INTERNAL_SERVER_ERROR",
                    message= "An unexpected server error occurred.",
                    ),
            )
            return JSONResponse(
            status_code= 500,
            content= error_response.model_dump(mode="json"),
            )
            
        finally:

            # 无论成功还是失败，都关闭 UploadFile
           await file.close()


def register_learning_material_routes(
    agent_app,
    *,
    storage: FileStorage,
    course_repository,
    learning_source_repository,
) -> None:
    @agent_app.endpoint(
        "/courses/{course_id}/materials",
        methods=["POST"],
    )
    async def upload_learning_material(
        course_id: str,
        request: Request,
        file: UploadFile = File(...),
        user_id: str = Form(
            ...,
            min_length=1,
        ),
    ):
        request_id = (
            f"req_{uuid.uuid4()}"
        )

        try:
            data = await read_upload_with_limit(
                file
            )

            response = await upload_learning_source(
                storage=storage,
                course_repository=(
                    course_repository
                ),
                learning_source_repository=(
                    learning_source_repository
                ),
                course_id=course_id,
                filename=file.filename,
                content_type=file.content_type,
                data=data,
                user_id=user_id,
                request_id=request_id,
            )

            return JSONResponse(
                status_code=201,
                content=response.model_dump(
                    mode="json"
                ),
            )

        except UploadServiceError as exc:
            return _upload_error_response(
                request_id=request_id,
                exc=exc,
            )

        except Exception:
            logger.exception(
                "Unhandled learning material "
                "upload error, request_id=%s",
                request_id,
            )

            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message=(
                        "An unexpected server "
                        "error occurred."
                    ),
                ),
            )

            return JSONResponse(
                status_code=500,
                content=(
                    error_response.model_dump(
                        mode="json"
                    )
                ),
            )

        finally:
            await file.close()

    @agent_app.endpoint(
        "/courses/{course_id}/materials",
        methods=["GET"],
    )
    async def list_course_materials(
        course_id: str,
        user_id: str,
    ):
        request_id = (
            f"req_{uuid.uuid4()}"
        )

        try:
            response = await list_learning_materials(
                course_repository=(
                    course_repository
                ),
                learning_source_repository=(
                    learning_source_repository
                ),
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

        except UploadServiceError as exc:
            return _upload_error_response(
                request_id=request_id,
                exc=exc,
            )

        except Exception:
            logger.exception(
                "Unhandled material list error, "
                "request_id=%s",
                request_id,
            )

            error_response = ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message=(
                        "An unexpected server "
                        "error occurred."
                    ),
                ),
            )

            return JSONResponse(
                status_code=500,
                content=(
                    error_response.model_dump(
                        mode="json"
                    )
                ),
            )