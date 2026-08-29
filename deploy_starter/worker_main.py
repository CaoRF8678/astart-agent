import asyncio

from core.config import config
from core.logging_config import logger

from rag.retriever import Retriever
from rag.multi_query_retriever import (
    MultiQueryRetriever,
)

from services.embedding_service import (
    EmbeddingService,
)


from database.connection import (
    AsyncSessionLocal,
    engine,
)
from database.repositories.generation_repository import (
    GenerationRepository,
)
from database.repositories.source_segment_repository import (
    SourceSegmentRepository,
)
from database.repositories.course_repository import (
    CourseRepository,
)
from stage.base import StructuredStageRunner

from workflows.course_generation_workflow import (
    CourseGenerationWorkflow,
)

from workers.course_generation_worker import (
    CourseGenerationWorker,
)


async def main() -> None:
    # ==========================================
    # 1. 创建 Repository
    # ==========================================
    # AsyncSessionLocal 是 SQLAlchemy 的
    # Async Session Factory（异步数据库会话工厂）
    #
    # Repository 后面所有数据库操作：
    # create_job()
    # get_job()
    # claim_next_pending_job()
    # mark_stage_running()
    # ...
    #
    # 都通过它创建数据库 Session。

    repository = GenerationRepository(
        session_factory=AsyncSessionLocal,
    )
    course_repository = CourseRepository(
        session_factory=AsyncSessionLocal,
    )
    source_segment_repository = (
    SourceSegmentRepository(
        session_factory=AsyncSessionLocal,
    )
    )
    embedding_service = EmbeddingService()
    rag_min_similarity = config.get(
    "RAG_MIN_SIMILARITY"
    )   
    retriever = Retriever(
    embedding_service=embedding_service,
    repository=source_segment_repository,

    top_k=int(
        config.get(
            "RAG_TOP_K",
            5,
        )
    ),

    min_similarity=(
        float(rag_min_similarity)
        if rag_min_similarity is not None
        else None
    ),
    )
    multi_query_retriever = (
    MultiQueryRetriever(
        retriever=retriever,
    )
    )   
    # ==========================================
    # 2. 创建 StructuredStageRunner
    # ==========================================
    # 负责真正调用 LLM。
    #
    # Research / Outline / Critique / Revision
    # 最终都会通过这个 runner 执行。

    stage_runner = StructuredStageRunner()
    # ==========================================
    # 3. 创建 CourseGenerationWorkflow
    # ==========================================
    # Workflow 负责：
    #
    # Research
    # ↓
    # Outline
    # ↓
    # Critique
    # ↓
    # Revision
    #
    # 同时负责：
    # - Stage 状态
    # - Cancel Check
    # - Snapshot 恢复
    # - Job completed / failed

    workflow = CourseGenerationWorkflow(
        repository=repository,
        course_repository=course_repository,
        stage_runner=stage_runner,

        multi_query_retriever=(
            multi_query_retriever
        ),

        rag_max_context_chars=int(
            config.get(
                "RAG_MAX_CONTEXT_CHARS",
                10000,
            )
        ),
    )
    # ==========================================
    # 4. 创建 Worker
    # ==========================================
    # Worker 自己不执行具体业务逻辑。
    #
    # 它只负责：
    # PostgreSQL 中领取 Job
    # ↓
    # 调用 workflow.run()
    # ↓
    # 再领取下一个 Job

    worker = CourseGenerationWorker(
        repository=repository,
        workflow=workflow,
        poll_interval_seconds=2,
    )
    # ==========================================
    # 5. 启动 Worker
    # ==========================================

    logger.info(
        "Course generation worker starting: %s",
        worker.worker_id,
    )

    try:

        await worker.run_forever()

    finally:
        # Worker 退出时关闭 SQLAlchemy Engine
        # 和该进程自己的数据库连接池
        await engine.dispose()

        logger.info(
            "Course generation worker resources released."
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info(
            "Course generation worker stopped."
        )