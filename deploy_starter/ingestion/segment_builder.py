import uuid

from ingestion.types import ParsedBlock
from schemas.learning_source import SourceSegment


def build_source_segments(
    *,
    file_id: str,
    blocks: list[ParsedBlock],
) -> list[SourceSegment]:
    return [
        SourceSegment(
            segment_id=f"seg_{uuid.uuid4().hex}",
            file_id=file_id,
            content=block.content,
            segment_order=segment_order,
            locator=block.locator,
        )
        for segment_order, block in enumerate(blocks)
    ]