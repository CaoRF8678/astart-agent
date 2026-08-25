from ingestion.types import ParsedBlock
from schemas.asr import Transcript


def chunk_transcript(
    transcript: Transcript,
    *,
    target_chars: int = 1800,
    max_chars: int = 3000,
) -> list[ParsedBlock]:

    result: list[ParsedBlock] = []

    # 当前正在积累的若干句话
    current = []

    # 当前 Block 已经有多少字符
    current_chars = 0

    def flush():
        nonlocal current, current_chars

        if not current:
            return

        result.append(
            ParsedBlock(
                content=" ".join(
                    segment.text.strip()
                    for segment in current
                ),
                locator={
                    "start_ms": current[0].start_ms,
                    "end_ms": current[-1].end_ms,
                },
            )
        )

        current = []
        current_chars = 0

    for segment in transcript.segments:
        text = segment.text.strip()

        if not text:
            continue

        # 如果 current 已经有句子，
        # 两句话拼接时中间还会多一个空格
        separator_chars = 1 if current else 0

        next_chars = (
            current_chars
            + separator_chars
            + len(text)
        )

        # 加入这句话会超过最大长度：
        # 先把之前的内容保存成一个 Block
        if current and next_chars > max_chars:
            flush()
            separator_chars = 0

        # 当前 sentence 加入新的/已有的 Block
        current.append(segment)
        current_chars += (
            separator_chars + len(text)
        )

        # 已经达到理想大小，就保存
        if current_chars >= target_chars:
            flush()

    # 最后一块通常不足 target_chars，
    # 但也必须保存
    flush()

    return result