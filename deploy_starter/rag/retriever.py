from schemas.rag import RetrievedSegment


class Retriever:
    def __init__(
        self,
        *,
        embedding_service,
        repository,
        top_k: int = 5,
        min_similarity: float | None = None,
    ) -> None:
        if top_k <= 0:
            raise ValueError(
                "top_k must be positive."
            )

        self._embedding_service = (
            embedding_service
        )
        self._repository = repository
        self._top_k = top_k
        self._min_similarity = (
            min_similarity
        )

    async def retrieve(
        self,
        *,
        course_id: str,
        query: str,
    ) -> list[RetrievedSegment]:
        normalized_query = query.strip()

        if not normalized_query:
            return []

        query_embedding = await (
            self._embedding_service.embed_query(
                normalized_query
            )
        )

        results = await (
            self._repository
            .search_similar_segments(
                course_id=course_id,
                query_embedding=(
                    query_embedding
                ),
                embedding_model=(
                    self._embedding_service
                    .model_name
                ),
                top_k=self._top_k,
            )
        )

        if self._min_similarity is None:
            return results

        return [
            result
            for result in results
            if (
                result.similarity_score
                >= self._min_similarity
            )
        ]