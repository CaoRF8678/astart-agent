import asyncio
from http import HTTPStatus

from dashscope import TextEmbedding

from core.config import config


MAX_EMBEDDING_BATCH_SIZE = 20


class EmbeddingServiceError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EmbeddingService:
    def __init__(self) -> None:
        self.api_key = config.get(
            "EMBEDDING_API_KEY"
        )

        self.model_name = (
            config.get(
                "EMBEDDING_MODEL",
                "qwen3.7-text-embedding",
            )
        )

        self.dimension = int(
            config.get(
                "EMBEDDING_DIMENSION",
                1024,
            )
        )

        if not self.api_key:
            raise EmbeddingServiceError(
                code="EMBEDDING_API_KEY_MISSING",
                message=(
                    "EMBEDDING_API_KEY "
                    "is not configured."
                ),
            )

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return await self._embed_many(
            texts=texts,
            text_type="document",
        )

    async def embed_query(
        self,
        query: str,
    ) -> list[float]:
        vectors = await self._embed_many(
            texts=[query],
            text_type="query",
        )

        return vectors[0]

    async def _embed_many(
        self,
        *,
        texts: list[str],
        text_type: str,
    ) -> list[list[float]]:
        normalized_texts = [
            text.strip()
            for text in texts
        ]

        if not normalized_texts:
            raise EmbeddingServiceError(
                code="EMPTY_EMBEDDING_INPUT",
                message=(
                    "Embedding input "
                    "must not be empty."
                ),
            )

        if any(
            not text
            for text in normalized_texts
        ):
            raise EmbeddingServiceError(
                code="EMPTY_EMBEDDING_TEXT",
                message=(
                    "Embedding text "
                    "must not be empty."
                ),
            )

        vectors: list[list[float]] = []

        for start in range(
            0,
            len(normalized_texts),
            MAX_EMBEDDING_BATCH_SIZE,
        ):
            batch = normalized_texts[
                start:
                start + MAX_EMBEDDING_BATCH_SIZE
            ]

            batch_vectors = (
                await self._embed_batch(
                    texts=batch,
                    text_type=text_type,
                )
            )

            vectors.extend(
                batch_vectors
            )

        if len(vectors) != len(
            normalized_texts
        ):
            raise EmbeddingServiceError(
                code="EMBEDDING_COUNT_MISMATCH",
                message=(
                    "Embedding result count "
                    "does not match input count."
                ),
            )

        return vectors

    async def _embed_batch(
        self,
        *,
        texts: list[str],
        text_type: str,
    ) -> list[list[float]]:
        try:
            response = await asyncio.to_thread(  #我们没有消除阻塞，而是把阻塞从 Event Loop 线程搬到了工作线程。
                TextEmbedding.call,  #“把同步阻塞工作移出 Event Loop 线程，然后以异步方式等待工作线程的结果
                model=self.model_name,
                input=texts,
                dimension=self.dimension,
                output_type="dense",
                text_type=text_type,
                api_key=self.api_key,
            )
        except Exception as exc:
            raise EmbeddingServiceError(
                code="EMBEDDING_API_FAILED",
                message=(
                    "Embedding API request failed."
                ),
            ) from exc

        if (
            response.status_code
            != HTTPStatus.OK
        ):
            raise EmbeddingServiceError(
                code="EMBEDDING_API_FAILED",
                message=(
                    f"Embedding API failed: "
                    f"{response.code}: "
                    f"{response.message}"
                ),
            )

        items = list(
            response.output["embeddings"]
        )

        items.sort(
            key=lambda item: item[
                "text_index"
            ]
        )

        vectors = [
            item["embedding"]
            for item in items
        ]

        if len(vectors) != len(texts):
            raise EmbeddingServiceError(
                code="EMBEDDING_COUNT_MISMATCH",
                message=(
                    "Embedding result count "
                    "does not match batch size."
                ),
            )

        for vector in vectors:
            if len(vector) != self.dimension:  #检查是否是1024维
                raise EmbeddingServiceError(
                    code=(
                        "EMBEDDING_DIMENSION_MISMATCH"
                    ),
                    message=(
                        "Embedding dimension "
                        "does not match configuration."
                    ),
                )

        return vectors