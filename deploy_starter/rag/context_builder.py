#Retriever找资料
#Context Builder整理资料
#AGService 调LLM
from schemas.rag import RetrievedSegment

DEFAULT_MAX_CONTEXT_CHARS = 10000

def _format_audio_time(milliseconds: int) -> str:
    total_seconds = max(0, milliseconds) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"

def format_locator(
    locator: dict,
) -> str:

    if "start_ms" in locator:
        start = int(locator["start_ms"])
        end = int(
            locator.get("end_ms", start)
        )

        return (
            f"音频 {_format_audio_time(start)}"
            f"-{_format_audio_time(end)}"
        )
    if "page_start" in locator:
        start = locator["page_start"]
        end = locator.get(
            "page_end",
            start,
        )

        if start == end:
            return f"第 {start} 页"

        return f"第 {start}-{end} 页"

    if "slide_start" in locator:
        start = locator["slide_start"]
        end = locator.get(
            "slide_end",
            start,
        )
        title = locator.get("title")

        base = (
            f"第 {start} 页"
            if start == end
            else f"第 {start}-{end} 页"
        )

        if title:
            return f"{base}：{title}"

        return base

    heading_path = locator.get(
        "heading_path"
    )

    if heading_path:
        return " > ".join(
            str(item)
            for item in heading_path
        )

    if "paragraph_start" in locator:
        start = locator[
            "paragraph_start"
        ]
        end = locator.get(
            "paragraph_end",
            start,
        )

        if start == end:
            return f"第 {start} 段"

        return f"第 {start}-{end} 段"

    if "block_index" in locator:
        return (
            f"第 {locator['block_index']} 块"
        )

    return "未提供明确位置"


def build_context(
    segments: list[RetrievedSegment],
    *,
    max_chars: int = (
        DEFAULT_MAX_CONTEXT_CHARS
    ),
) -> tuple[
    str,
    list[RetrievedSegment],
]:
    context_parts: list[str] = []
    used_segments: list[
        RetrievedSegment
    ] = []

    current_length = 0

    for index, segment in enumerate(
        segments,
        start=1,
    ):
        locator_text = format_locator(
            segment.locator
        )

        block = (
            f"[Source {index}]\n"
            f"文件：{segment.filename}\n"
            f"位置：{locator_text}\n"
            f"内容：\n{segment.content}"
        )

        separator_length = (
            2 if context_parts else 0
        )

        next_length = (
            current_length
            + separator_length
            + len(block)
        )

        if (
            context_parts
            and next_length > max_chars
        ):
            break

        context_parts.append(block)
        used_segments.append(segment)
        current_length = next_length

    return (
        "\n\n".join(context_parts),
        used_segments,
    )