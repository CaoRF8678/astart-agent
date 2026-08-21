#解析文本块

from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedBlock:
    content: str
    locator: dict[str, Any]