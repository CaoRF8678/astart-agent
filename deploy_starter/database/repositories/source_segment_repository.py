from sqlalchemy import select

from database.models.learning_source import (
    LearningSourceModel,
)
from database.models.source_segment import (
    SourceSegmentModel,
)
from schemas.rag import RetrievedSegment

class SourceSegmentRepository:
    def __init__(
        self,
        session_factory,
    ) -> None:
        self._session_factory = (
            session_factory
        )

    async def search_similar_segments(
        self,
        *,
        course_id: str,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int,
    ) -> list[RetrievedSegment]:
        distance = (  #定义距离表达式
            SourceSegmentModel.embedding   #面向对象的写法，这里的就相当于将资料库里面的所有的资料来对比了
            .cosine_distance(
                query_embedding
            )
            .label("distance")
        )

        async with self._session_factory() as session:
            stmt = (
                select( #要查哪些字段
                    SourceSegmentModel.segment_id,
                    SourceSegmentModel.file_id,
                    LearningSourceModel.filename,
                    SourceSegmentModel.content,
                    SourceSegmentModel.locator,
                    distance,
                )
                .join( #需要把哪两张表连起来
                    LearningSourceModel,
                    SourceSegmentModel.file_id
                    == LearningSourceModel.file_id,
                )
                .where( #哪些数据才有资格参与查阅
                    LearningSourceModel.course_id
                    == course_id,
                    LearningSourceModel.status
                    == "ready",
                    SourceSegmentModel.embedding
                    .is_not(None),
                    SourceSegmentModel.embedding_model
                    == embedding_model,
                )
                .order_by(distance.asc()) #按什么顺序来查
                .limit(top_k) 
            )

            result = await session.execute(
                stmt
            )

            rows = result.all()

        retrieved: list[
            RetrievedSegment
        ] = []

        for row in rows:
            similarity = (
                1.0 - float(row.distance)
            )

            similarity = max(
                -1.0,
                min(1.0, similarity),
            )

            retrieved.append(
                RetrievedSegment(
                    segment_id=row.segment_id,
                    file_id=row.file_id,
                    filename=row.filename,
                    content=row.content,
                    locator=row.locator,
                    similarity_score=(
                        similarity
                    ),
                )
            )

        return retrieved
