from abc import ABC, abstractmethod
from typing import Any

from ingestion.text_processing import (
    normalize_text,
)
from ingestion.types import ParsedBlock


class DocumentParser(ABC):

    @abstractmethod
    def parse(   #统一接口
        self,
        data: bytes,
    ) -> list[ParsedBlock]:
        raise NotImplementedError

    @staticmethod
    def _make_block(  # 统一输出前的轻量文本清理 + 空块过滤
        *,
        content: str,
        locator: dict[str, Any],
    ) -> ParsedBlock | None:
        content = normalize_text(
            content
        )

        if not content:
            return None

        return ParsedBlock(
            content=content,
            locator=locator,
        )