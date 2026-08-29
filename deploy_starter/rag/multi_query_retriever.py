from rag.retriever import Retriever
from schemas.rag import RetrievedSegment


class MultiQueryRetriever:
    def __init__(
        self,
        *,
        retriever: Retriever,
    ) -> None:
        self._retriever = retriever

    async def retrieve_many(
        self,
        *,
        course_id: str,
        queries: list[str],
    ) -> list[RetrievedSegment]:

        best_by_segment: dict[
            str,
            RetrievedSegment,
        ] = {}

        # 每一个 Query 分别调用现有 Retriever
        for query in queries:
            results = await self._retriever.retrieve(
                course_id=course_id,
                query=query,
            )

            # 合并并去重
            for result in results:
                current = best_by_segment.get(
                    result.segment_id
                )

                # 第一次出现，或者这一次相似度更高
                if (
                    current is None
                    or result.similarity_score
                    > current.similarity_score
                ):
                    best_by_segment[
                        result.segment_id
                    ] = result

        # 按相似度从高到低排序
        return sorted(
            best_by_segment.values(),
            key=lambda item: item.similarity_score,
            reverse=True,
        )