RAG_SYSTEM_PROMPT = """
你是 Astart 的课程资料问答模块。

必须遵守：
1. 只能依据本次提供的课程资料回答。
2. 不得使用课程资料之外的事实进行补充。
3. 如果资料不足以支持结论，明确说明资料不足。
4. 引用资料时使用 [Source N]。
5. 不得伪造不存在的 Source 编号。
""".strip()

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from core.model_factory import (
    create_chat_model_and_formatter,
)
from rag.context_builder import (
    build_context,
)
from schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
)
from services.embedding_service import (
    EmbeddingServiceError,
)


RAG_SYSTEM_PROMPT = """
你是 Astart 的课程资料问答模块。

必须遵守：
1. 只能依据本次提供的课程资料回答。
2. 不得使用课程资料之外的事实进行补充。
3. 如果资料不足以支持结论，明确说明资料不足。
4. 引用资料时使用 [Source N]。
5. 不得伪造不存在的 Source 编号。
""".strip()


NO_RELEVANT_MATERIALS_ANSWER = (
    "当前课程资料中没有检索到"
    "足够相关的信息。"
)


class RAGServiceError(Exception):
    def __init__(
        self,
        *,
        request_id: str,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message


class RAGService:
    def __init__(
        self,
        *,
        course_repository,
        retriever,
        max_context_chars: int,
    ) -> None:
        self._course_repository = (
            course_repository
        )
        self._retriever = retriever
        self._max_context_chars = (
            max_context_chars
        )

        self._model, self._formatter = (
            create_chat_model_and_formatter(
                stream=False,
                generate_kwargs={
                    "extra_body": {
                        "thinking": {
                            "type": "disabled",
                        }
                    }
                },
            )
        )

    async def query(
        self,
        *,
        course_id: str,
        request: RAGQueryRequest,
        request_id: str,
    ) -> RAGQueryResponse:
        user_id = request.user_id.strip()
        question = request.question.strip()

        if not user_id:
            raise RAGServiceError(
                request_id=request_id,
                code="INVALID_USER_ID",
                message=(
                    "User ID must not be empty."
                ),
            )

        if not question:
            raise RAGServiceError(
                request_id=request_id,
                code="INVALID_QUESTION",
                message=(
                    "Question must not be empty."
                ),
            )

        course = await (
            self._course_repository
            .get_course_for_user(
                course_id=course_id,
                user_id=user_id,
            )
        )

        if course is None:
            raise RAGServiceError(
                request_id=request_id,
                code="COURSE_NOT_FOUND",
                message="Course not found.",
            )

        try:
            retrieved = await (
                self._retriever.retrieve(
                    course_id=course_id,
                    query=question,
                )
            )
        except EmbeddingServiceError as exc:
            raise RAGServiceError(
                request_id=request_id,
                code="RAG_EMBEDDING_FAILED",
                message=exc.message,
            ) from exc

        if not retrieved:
            return RAGQueryResponse(
                request_id=request_id,
                course_id=course_id,
                answer=(
                    NO_RELEVANT_MATERIALS_ANSWER
                ),
                sources=[],
            )

        context, used_segments = (
            build_context(
                retrieved,
                max_chars=(
                    self._max_context_chars
                ),
            )
        )

        try:
            answer = await self._generate_answer(
                question=question,
                context=context,
            )
        except Exception as exc:
            raise RAGServiceError(
                request_id=request_id,
                code="RAG_GENERATION_FAILED",
                message=(
                    "Failed to generate "
                    "RAG answer."
                ),
            ) from exc

        sources = [
            RAGSource(
                segment_id=(
                    segment.segment_id
                ),
                file_id=segment.file_id,
                filename=segment.filename,
                locator=segment.locator,
                similarity_score=(
                    segment.similarity_score
                ),
            )
            for segment in used_segments
        ]

        return RAGQueryResponse(
            request_id=request_id,
            course_id=course_id,
            answer=answer,
            sources=sources,
        )

    async def _generate_answer(
        self,
        *,
        question: str,
        context: str,
    ) -> str:
        agent = ReActAgent(
            name="CourseRAG",
            model=self._model,
            sys_prompt=RAG_SYSTEM_PROMPT,
            formatter=self._formatter,
            memory=InMemoryMemory(),
        )

        prompt = (
            "以下是当前课程中检索到的资料：\n\n"
            f"{context}\n\n"
            "用户问题：\n"
            f"{question}"
        )

        result = await agent(
            Msg(
                name="user",
                role="user",
                content=prompt,
            )
        )


        answer = result.get_text_content().strip()

        if not answer:
            raise RuntimeError(
                "RAG model returned "
                "an empty answer."
            )

        return answer