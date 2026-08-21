import io
import re
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from ingestion.errors import (
    DocumentParseError,
)
from ingestion.parsers.base import (
    DocumentParser,
)
from ingestion.text_processing import (
    merge_short_blocks,
    normalize_text,
    split_long_text,
)
from ingestion.types import ParsedBlock


_HEADING_RE = re.compile(
    r"^(?:Heading|标题)\s+(\d+)$",
    re.IGNORECASE,
)


class DOCXParser(DocumentParser):

    def parse(
        self,
        data: bytes,
    ) -> list[ParsedBlock]:
        try:
            document = Document(
                io.BytesIO(data)
            )
        except (
            zipfile.BadZipFile,
            ValueError,
            KeyError,
        ) as exc:
            raise DocumentParseError(
                "无法解析 DOCX 文档。"
            ) from exc

        parsed: list[ParsedBlock] = []
        heading_path: list[str] = []
        pending_units: list[str] = []

        def flush() -> None:
            nonlocal pending_units

            atomic: list[str] = []

            for unit in pending_units:
                atomic.extend(
                    split_long_text(unit)
                )

            for content in merge_short_blocks(
                atomic
            ):
                locator: dict = {
                    "block_index": (
                        len(parsed) + 1
                    )
                }

                if heading_path:
                    locator["heading_path"] = (
                        list(heading_path)
                    )

                block = self._make_block(
                    content=content,
                    locator=locator,
                )

                if block is not None:
                    parsed.append(block)

            pending_units = []

        for item in (
            document.iter_inner_content()
        ):
            if isinstance(item, Paragraph):
                text = normalize_text(
                    item.text
                )

                if not text:
                    continue

                style_name = (
                    item.style.name
                    if item.style is not None
                    else ""
                )

                match = _HEADING_RE.match(
                    style_name
                )

                if match:
                    flush()

                    level = max(
                        1,
                        int(match.group(1)),
                    )

                    heading_path = (
                        heading_path[:level - 1]
                    )
                    heading_path.append(text)

                else:
                    pending_units.append(text)

            elif isinstance(item, Table):
                rows: list[str] = []

                for row in item.rows:
                    cells = [
                        normalize_text(cell.text)
                        for cell in row.cells
                    ]

                    cells = [
                        cell
                        for cell in cells
                        if cell
                    ]

                    if cells:
                        rows.append(
                            " | ".join(cells)
                        )

                if rows:
                    pending_units.append(
                        "\n".join(rows)
                    )

        flush()

        if not parsed:
            raise DocumentParseError(
                "DOCX 中没有提取到有效文本。"
            )

        return parsed