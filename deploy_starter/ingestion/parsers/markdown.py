from markdown_it import MarkdownIt

from ingestion.errors import (
    DocumentParseError,
)
from ingestion.parsers.base import (
    DocumentParser,
)
from ingestion.text_processing import (
    DEFAULT_MAX_CHARS,
    merge_short_blocks,
    normalize_text,
    split_long_text,
)
from ingestion.types import ParsedBlock


class MarkdownParser(DocumentParser):

    def __init__(self) -> None:
        self._markdown = (
            MarkdownIt("commonmark")
            .enable("table")
        )

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
                "Markdown 文件必须使用 UTF-8 编码。"
            ) from exc

        tokens = self._markdown.parse(
            text
        )

        parsed: list[ParsedBlock] = []
        heading_path: list[str] = []
        pending_units: list[str] = []

        def current_locator() -> dict:
            locator = {
                "block_index": (
                    len(parsed) + 1
                )
            }

            if heading_path:
                locator["heading_path"] = (
                    list(heading_path)
                )

            return locator

        def flush_text() -> None:
            nonlocal pending_units

            atomic: list[str] = []

            for unit in pending_units:
                atomic.extend(
                    split_long_text(unit)
                )

            for content in merge_short_blocks(
                atomic
            ):
                block = self._make_block(
                    content=content,
                    locator=current_locator(),
                )

                if block is not None:
                    parsed.append(block)

            pending_units = []

        index = 0

        while index < len(tokens):
            token = tokens[index]

            if token.type == "heading_open":
                flush_text()

                level = int(
                    token.tag[1:]
                )

                title = ""

                if (
                    index + 1 < len(tokens)
                    and tokens[index + 1].type
                    == "inline"
                ):
                    title = normalize_text(
                        tokens[index + 1].content
                    )

                if title:
                    heading_path = (
                        heading_path[:level - 1]
                    )
                    heading_path.append(title)

                index += 3
                continue

            if token.type == "fence":
                flush_text()

                language = (
                    token.info.strip()
                )

                code_content = (
                    token.content.rstrip()
                )

                fenced = (
                    f"```{language}\n"
                    f"{code_content}\n"
                    "```"
                )

                if len(fenced) <= DEFAULT_MAX_CHARS:
                    code_parts = [fenced]
                else:
                    code_parts = (
                        self._split_long_code(
                            code_content,
                            language=language,
                            fenced=True,
                        )
                    )

                for code_part in code_parts:
                    block = self._make_block(
                        content=code_part,
                        locator=current_locator(),
                    )

                    if block is not None:
                        parsed.append(block)

                index += 1
                continue

            if token.type == "code_block":
                flush_text()

                code_content = (
                    token.content.rstrip()
                )

                code_parts = (
                    [code_content]
                    if len(code_content)
                    <= DEFAULT_MAX_CHARS
                    else self._split_long_code(
                        code_content,
                        language="",
                        fenced=False,
                    )
                )

                for code_part in code_parts:
                    block = self._make_block(
                        content=code_part,
                        locator=current_locator(),
                    )

                    if block is not None:
                        parsed.append(block)

                index += 1
                continue

            if token.type == "inline":
                content = normalize_text(
                    token.content
                )

                if content:
                    pending_units.append(
                        content
                    )

            index += 1

        flush_text()

        if not parsed:
            raise DocumentParseError(
                "Markdown 中没有提取到有效文本。"
            )

        return parsed

    @staticmethod
    def _split_long_code(
        content: str,
        *,
        language: str,
        fenced: bool,
    ) -> list[str]:
        lines = content.splitlines()

        parts: list[str] = []
        current: list[str] = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1

            if (
                current
                and current_length + line_length
                > DEFAULT_MAX_CHARS
            ):
                body = "\n".join(current)

                parts.append(
                    (
                        f"```{language}\n"
                        f"{body}\n"
                        "```"
                    )
                    if fenced
                    else body
                )

                current = []
                current_length = 0

            current.append(line)
            current_length += line_length

        if current:
            body = "\n".join(current)

            parts.append(
                (
                    f"```{language}\n"
                    f"{body}\n"
                    "```"
                )
                if fenced
                else body
            )

        return parts