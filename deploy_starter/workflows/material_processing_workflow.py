import json
import logging

from asr.base import ASRService, ASRServiceError
from ingestion.audio_chunking import chunk_transcript
from ingestion.segment_builder import build_source_segments
from schemas.learning_source import LearningSource
from services.embedding_service import EmbeddingService, EmbeddingServiceError
from storage.base import FileStorage, FileStorageError


logger = logging.getLogger(__name__)


class MaterialProcessingError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MaterialProcessingWorkflow:
    def __init__(
        self,
        *,
        repository,
        storage: FileStorage,
        asr_service: ASRService,
        embedding_service: EmbeddingService,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.asr_service = asr_service
        self.embedding_service = embedding_service

    async def run(
        self,
        *,
        source: LearningSource,
        worker_id: str,
    ) -> None:
        transcript_storage_key: str | None = None
        finalized = False

        try:
            try:
                transcript = await self.asr_service.transcribe(   #调用传入的ASR的函数转换音频
                    storage_key=source.storage_key
                )
            except ASRServiceError as exc:
                raise MaterialProcessingError(
                    code=exc.code,
                    message=exc.message,
                ) from exc

            transcript_bytes = json.dumps(  #json格式保存
                transcript.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")

            try:
                transcript_storage_key = await self.storage.save(
                    file_id=f"{source.file_id}_transcript",
                    filename="transcript.json",
                    data=transcript_bytes,
                )
            except FileStorageError as exc:
                raise MaterialProcessingError(
                    code="TRANSCRIPT_STORAGE_FAILED",
                    message=(
                        "Failed to store normalized transcript."
                    ),
                ) from exc

            blocks = chunk_transcript(transcript)
            segments = build_source_segments(
                file_id=source.file_id,
                blocks=blocks,
            )

            try:
                vectors = await self.embedding_service.embed_documents(
                    [segment.content for segment in segments]
                )
            except EmbeddingServiceError as exc:
                raise MaterialProcessingError(
                    code="EMBEDDING_FAILED",
                    message=exc.message,
                ) from exc

            segments = [
                segment.model_copy(  #实例复制方法
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

            await self.repository.mark_source_ready_with_segments(
                file_id=source.file_id,
                worker_id=worker_id,
                segments=segments,
                transcript_storage_key=(
                    transcript_storage_key
                ),
            )
            finalized = True

        except MaterialProcessingError:
            raise
        except Exception as exc:
            raise MaterialProcessingError(
                code="MATERIAL_PROCESSING_FAILED",
                message=(
                    "Unexpected material processing failure."
                ),
            ) from exc
        finally:
            if (
                transcript_storage_key is not None
                and not finalized
            ):
                try:
                    await self.storage.delete(
                        transcript_storage_key
                    )
                except FileStorageError:
                    logger.exception(
                        "Failed to clean up transcript artifact: %s",
                        transcript_storage_key,
                    )