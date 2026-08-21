from ingestion.errors import (
    DocumentParseError,
)
from ingestion.parsers.base import (
    DocumentParser,
)
from ingestion.parsers.docx import DOCXParser
from ingestion.parsers.markdown import MarkdownParser
from ingestion.parsers.pdf import PDFParser
from ingestion.parsers.pptx import PPTXParser
from ingestion.parsers.text import TextParser


_PARSERS_BY_SUFFIX: dict[
    str,
    DocumentParser,
] = {
    ".pdf": PDFParser(),
    ".pptx": PPTXParser(),
    ".docx": DOCXParser(),
    ".md": MarkdownParser(),
    ".txt": TextParser(),
}


def get_parser(
    suffix: str,
) -> DocumentParser:
    parser = _PARSERS_BY_SUFFIX.get(
        suffix
    )

    if parser is None:
        raise DocumentParseError(
            "当前文件类型没有可用解析器。"
        )

    return parser