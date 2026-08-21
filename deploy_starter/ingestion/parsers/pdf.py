import pymupdf

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


class PDFParser(DocumentParser):

    def parse(
        self,
        data: bytes,
    ) -> list[ParsedBlock]:
        try:
            document = pymupdf.open(
                stream=data,
                filetype="pdf",
            )
        except (
            RuntimeError,
            ValueError,
        ) as exc:
            raise DocumentParseError(
                "无法解析 PDF 文档。"
            ) from exc

        parsed: list[ParsedBlock] = []

        try:
            for page_index, page in enumerate(
                document,
                start=1,
            ):
                units: list[str] = []

                blocks = page.get_text(
                    "blocks",
                    sort=True,
                )

                for block in blocks:
                    text = block[4]

                    block_type = (
                        block[6]
                        if len(block) > 6
                        else 0
                    )

                    if block_type != 0:
                        continue

                    text = normalize_text(text)

                    if not text:
                        continue

                    units.extend(
                        split_long_text(text)
                    )

                for content in merge_short_blocks(
                    units
                ):
                    block = self._make_block(
                        content=content,
                        locator={
                            "page_start": page_index,
                            "page_end": page_index,
                        },
                    )

                    if block is not None:
                        parsed.append(block)

        finally:
            document.close()

        if not parsed:
            raise DocumentParseError(
                "PDF 中没有提取到有效文本，"
                "可能是扫描版文档。"
            )

        return parsed