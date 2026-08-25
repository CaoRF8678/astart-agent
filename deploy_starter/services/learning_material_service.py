import asyncio
import hashlib
import logging
import uuid

from collections.abc import AsyncIterable
from pathlib import Path

from ingestion.errors import DocumentParseError
from ingestion.parsers import get_parser
from ingestion.segment_builder import build_source_segments
from schemas.learning_source import (
    LearningMaterialListResponse,
    LearningMaterialUploadResponse,
)
from services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
)
from services.upload_service import (
    MAX_FILE_SIZE,
    UploadServiceError,
    sanitize_filename,
    validate_file_content,
    validate_file_metadata,
)
from storage.base import FileStorage, FileStorageError
from core.config import config


logger = logging.getLogger(__name__)

AUDIO_FILE_TYPES = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".ogg": {"audio/ogg"},
    ".opus": {"audio/opus", "audio/ogg"},
}
GENERIC_CONTENT_TYPES = {"application/octet-stream"}
MAX_AUDIO_FILE_SIZE = int(
    config.get("MAX_AUDIO_FILE_SIZE_MB", 2048)
) * 1024 * 1024


class LearningMaterialService:
    def __init__(
        self,
        *,
        storage: FileStorage,
        course_repository,
        learning_source_repository,
        embedding_service: EmbeddingService,
    ) -> None:
        self.storage = storage
        self.course_repository = course_repository
        self.learning_source_repository = (
            learning_source_repository
        )
        self.embedding_service = embedding_service

    async def _validate_course(
        self,
        *,
        course_id: str,
        user_id: str,
    ) -> str:
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise UploadServiceError(
                code="INVALID_USER_ID",
                message="User ID must not be empty.",
            )

        course = await self.course_repository.get_course_for_user(
            course_id=course_id,
            user_id=normalized_user_id,
        )
        if course is None:
            raise UploadServiceError(
                code="COURSE_NOT_FOUND",
                message="Course not found.",
            )
        return normalized_user_id

    @staticmethod
    def _is_audio_suffix(
        suffix: str,
    ) -> bool:
        return suffix in AUDIO_FILE_TYPES

    @staticmethod
    def _validate_audio_metadata(
        *,
        suffix: str,
        content_type: str | None,
    ) -> str:
        allowed_types = AUDIO_FILE_TYPES.get(suffix)
        if allowed_types is None:
            raise UploadServiceError(
                code="UNSUPPORTED_FILE_TYPE",
                message=(
                    "The uploaded audio type is not supported."
                ),
            )

        normalized = (
            content_type
            or "application/octet-stream"
        ).lower()
        if (
            normalized not in allowed_types
            and normalized not in GENERIC_CONTENT_TYPES
        ):
            raise UploadServiceError(
                code="UNSUPPORTED_FILE_TYPE",
                message=(
                    "The uploaded audio MIME type does not match the file extension."
                ),
            )
        return normalized

    @staticmethod
    async def _collect_document_bytes(
        chunks: AsyncIterable[bytes],
    ) -> bytes:
        buffer = bytearray()   #可变字节数组
        async for chunk in chunks:
            if len(buffer) + len(chunk) > MAX_FILE_SIZE:
                raise UploadServiceError(
                    code="FILE_TOO_LARGE",
                    message=(
                        "The uploaded file exceeds the maximum allowed size."
                    ),
                )
            buffer.extend(chunk)
        return bytes(buffer)  #转换为不可变数组

    async def _upload_document(  #仅处理文档，不考虑audio
        self,
        *,
        course_id: str,
        safe_filename: str,
        content_type: str | None,
        suffix: str,
        chunks: AsyncIterable[bytes],
        request_id: str,
    ) -> LearningMaterialUploadResponse:
        data = await self._collect_document_bytes(
            chunks
        )
        size, sha256_hash = validate_file_content(
            data=data,
            suffix=suffix,
        )
        normalized_content_type = (
            content_type
            or "application/octet-stream"
        ).lower()

        try:
            parser = get_parser(suffix)
            blocks = await asyncio.to_thread(
                parser.parse,
                data,
            )
        except DocumentParseError as exc:
            raise UploadServiceError(
                code="DOCUMENT_PARSE_FAILED",
                message=str(exc),
            ) from exc

        file_id = f"file_{uuid.uuid4().hex}"
        segments = build_source_segments(
            file_id=file_id,
            blocks=blocks,
        )

        try:
            vectors = await self.embedding_service.embed_documents(
                [segment.content for segment in segments]
            )
        except EmbeddingServiceError as exc:
            raise UploadServiceError(
                code="EMBEDDING_FAILED",
                message=exc.message,
            ) from exc

        segments = [
            segment.model_copy(
                update={
                    "embedding": vector,
                    "embedding_model": (
                        self.embedding_service.model_name
                    ),
                }
            )
            for segment, vector in zip(
                segments,
                vectors,
            )
        ]

        try:
            storage_key = await self.storage.save(
                file_id=file_id,
                filename=safe_filename,
                data=data,
            )
        except FileStorageError as exc:
            raise UploadServiceError(
                code="FILE_STORAGE_FAILED",
                message="Failed to store uploaded file.",
            ) from exc

        try:
            source = await self.learning_source_repository.create_learning_source_with_segments(
                file_id=file_id,
                course_id=course_id,
                filename=safe_filename,
                content_type=normalized_content_type,
                size=size,
                sha256=sha256_hash,
                storage_key=storage_key,
                segments=segments,
            )
        except Exception:
            try:
                await self.storage.delete(storage_key)
            except FileStorageError:
                logger.exception(
                    "Failed to clean up stored document: %s",
                    storage_key,
                )
            raise

        return LearningMaterialUploadResponse(
            request_id=request_id,
            course_id=source.course_id,
            file_id=source.file_id,
            filename=source.filename,
            content_type=source.content_type,
            size=source.size,
            status=source.status,
            created_at=source.created_at,
        )

    async def _upload_audio(
        self,
        *,
        course_id: str,
        safe_filename: str,
        content_type: str | None,
        chunks: AsyncIterable[bytes],
        request_id: str,
    ) -> LearningMaterialUploadResponse:
        suffix = Path(safe_filename).suffix.lower()
        normalized_content_type = self._validate_audio_metadata(
            suffix=suffix,
            content_type=content_type,
        )

        iterator = chunks.__aiter__()
        first_chunk = await anext(iterator, None)
        if first_chunk is None:
            raise UploadServiceError(
                code="EMPTY_FILE",
                message="The uploaded file is empty.",
            )

        file_id = f"file_{uuid.uuid4().hex}"
        size = 0
        hasher = hashlib.sha256()

        async def audited_chunks():
            nonlocal size

            def accept(chunk: bytes) -> bytes:   #只是检查一下，大小，以及生成哈希值，
                nonlocal size
                if size + len(chunk) > MAX_AUDIO_FILE_SIZE:
                    raise UploadServiceError(
                        code="FILE_TOO_LARGE",
                        message=(
                            "The uploaded audio exceeds the maximum allowed size."
                        ),
                    )
                size += len(chunk)
                hasher.update(chunk)
                return chunk

            yield accept(first_chunk)   #第一块chunk执行完毕后吐出，暂停，然后下一个chunk进来之后就执行开始执行下面的程序了
            async for chunk in iterator:
                if chunk:
                    yield accept(chunk)

        try:
            storage_key = await self.storage.save_stream(
                file_id=file_id,
                filename=safe_filename,
                chunks=audited_chunks(),
            )
        except UploadServiceError:
            raise
        except FileStorageError as exc:
            raise UploadServiceError(
                code="FILE_STORAGE_FAILED",
                message="Failed to store uploaded audio.",
            ) from exc

        try:
            source = await self.learning_source_repository.create_pending_source(
                file_id=file_id,
                course_id=course_id,
                filename=safe_filename,
                content_type=normalized_content_type,
                size=size,
                sha256=hasher.hexdigest(),
                storage_key=storage_key,
            )
        except Exception:
            try:
                await self.storage.delete(storage_key)
            except FileStorageError:
                logger.exception(
                    "Failed to clean up stored audio: %s",
                    storage_key,
                )
            raise

        return LearningMaterialUploadResponse(
            request_id=request_id,
            course_id=source.course_id,
            file_id=source.file_id,
            filename=source.filename,
            content_type=source.content_type,
            size=source.size,
            status=source.status,
            created_at=source.created_at,
        )

    async def upload_material(
        self,
        *,
        course_id: str,
        filename: str | None,
        content_type: str | None,
        chunks: AsyncIterable[bytes],
        user_id: str,
        request_id: str,
    ) -> LearningMaterialUploadResponse:
        await self._validate_course(
            course_id=course_id,
            user_id=user_id,
        )
        safe_filename = sanitize_filename(filename)
        suffix = Path(safe_filename).suffix.lower()

        if self._is_audio_suffix(suffix):
            return await self._upload_audio(
                course_id=course_id,
                safe_filename=safe_filename,
                content_type=content_type,
                chunks=chunks,
                request_id=request_id,
            )

        validate_file_metadata(
            filename=safe_filename,
            content_type=content_type,
        )
        return await self._upload_document(
            course_id=course_id,
            safe_filename=safe_filename,
            content_type=content_type,
            suffix=suffix,
            chunks=chunks,
            request_id=request_id,
        )

    async def list_materials(
        self,
        *,
        course_id: str,
        user_id: str,
        request_id: str,
    ) -> LearningMaterialListResponse:
        await self._validate_course(
            course_id=course_id,
            user_id=user_id,
        )
        materials = await self.learning_source_repository.list_learning_sources_for_course(
            course_id=course_id,
        )
        return LearningMaterialListResponse(
            request_id=request_id,
            materials=materials,
        )