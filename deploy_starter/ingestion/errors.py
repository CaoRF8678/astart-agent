#第一版先只建立这一种解析异常
class DocumentParseError(Exception):
    """The uploaded document cannot be parsed into useful text."""