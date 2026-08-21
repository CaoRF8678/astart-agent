import re

from ingestion.errors import (
    DocumentParseError,
)
from ingestion.parsers.base import (
    DocumentParser,
)
from ingestion.text_processing import (
    DEFAULT_MAX_CHARS,
    DEFAULT_TARGET_CHARS,
    normalize_text,
    split_long_text,
)
from ingestion.types import ParsedBlock


class TextParser(DocumentParser):

    def parse(
        self,
        data: bytes,
    ) -> list[ParsedBlock]:
        try:
            text = data.decode(
                "utf-8-sig"
            )
        except UnicodeDecodeError as exc:
            raise DocumentParseError(
                "TXT 文件必须使用 UTF-8 编码。"
            ) from exc

        raw_paragraphs = re.split(
            r"\n\s*\n",  #切开空行
            text,
        )

        paragraphs = [
            (
                paragraph_index,
                normalize_text(paragraph),
            )
            for paragraph_index, paragraph
            in enumerate(
                raw_paragraphs,
                start=1,
            )
        ]

        paragraphs = [   #去掉空的item
            item
            for item in paragraphs 
            if item[1]
        ]

        parsed: list[ParsedBlock] = []  #定义了一个变量

        current_text = ""
        current_start: int | None = None
        current_end: int | None = None

        def flush() -> None:
            nonlocal current_text, current_start, current_end

            if (
                not current_text
                or current_start is None
                or current_end is None
            ):
                current_text = ""
                current_start = None
                current_end = None
                return

            block = self._make_block(
                content=current_text,
                locator={
                    "paragraph_start": (
                        current_start
                    ),
                    "paragraph_end": (
                        current_end
                    ),
                },
            )

            if block is not None:
                parsed.append(block)

            current_text = ""
            current_start = None
            current_end = None

        for (
            paragraph_index,
            paragraph,
        ) in paragraphs:

            pieces = split_long_text(
                paragraph
            )

            for piece in pieces:
                if not current_text:
                    current_text = piece
                    current_start = (
                        paragraph_index
                    )
                    current_end = (
                        paragraph_index
                    )
                    continue

                candidate = (
                    f"{current_text}\n\n{piece}"
                )

                if (
                    len(current_text)
                    < DEFAULT_TARGET_CHARS
                    and len(candidate)
                    <= DEFAULT_MAX_CHARS
                ):
                    current_text = candidate
                    current_end = (
                        paragraph_index
                    )
                else:
                    flush()
                    current_text = piece
                    current_start = (
                        paragraph_index
                    )
                    current_end = (
                        paragraph_index
                    )

        flush()

        if not parsed:
            raise DocumentParseError(
                "TXT 中没有提取到有效文本。"
            )

        return parsed


"""
[
    ParsedBlock(
        content="段落1：人工智能简介。\n\n段落2：大模型发展迅速。",
        locator={"paragraph_start":1,"paragraph_end":2}
    ),
    ParsedBlock(
        content="段落3：RAG提升问答效果。",
        locator={"paragraph_start":3,"paragraph_end":3}
    )
]
"""