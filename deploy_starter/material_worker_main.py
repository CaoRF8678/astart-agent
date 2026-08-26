import asyncio

from asr.qwen_cloud import QwenCloudASRService
from core.config import config
from core.logging_config import logger
from database.connection import AsyncSessionLocal, engine
from database.repositories.learning_source_repository import (
    LearningSourceRepository,
)
from services.embedding_service import EmbeddingService
from storage.oss import OSSFileStorage
from workers.material_processing_worker import (
    MaterialProcessingWorker,
)
from workflows.material_processing_workflow import (
    MaterialProcessingWorkflow,
)


def create_oss_storage() -> OSSFileStorage:
    return OSSFileStorage(
        region=config.get("OSS_REGION"),
        endpoint=config.get("OSS_ENDPOINT") or None,
        bucket=config.get("OSS_BUCKET"),
        access_key_id=config.get("OSS_ACCESS_KEY_ID"),
        access_key_secret=config.get("OSS_ACCESS_KEY_SECRET"),
    )


async def main() -> None:
    repository = LearningSourceRepository(
        session_factory=AsyncSessionLocal
    )
    storage = create_oss_storage()
    embedding_service = EmbeddingService()
    asr_service = QwenCloudASRService(
        storage=storage
    )
    workflow = MaterialProcessingWorkflow(
        repository=repository,
        storage=storage,
        asr_service=asr_service,
        embedding_service=embedding_service,
    )
    worker = MaterialProcessingWorker(
        repository=repository,
        workflow=workflow,
        poll_interval_seconds=float(
            config.get("MATERIAL_WORKER_POLL_SECONDS", 2)
        ),
        heartbeat_interval_seconds=float(
            config.get("MATERIAL_HEARTBEAT_SECONDS", 60)
        ),
        stale_timeout_seconds=float(
            config.get("MATERIAL_STALE_TIMEOUT_SECONDS", 300)
        ),
        stale_check_interval_seconds=float(
            config.get("MATERIAL_STALE_CHECK_SECONDS", 60)
        ),
    )

    logger.info(
        "Material processing worker starting: %s",
        worker.worker_id,
    )

    try:
        await worker.run_forever()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(
            "Material processing worker stopped."
        )