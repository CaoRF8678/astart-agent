#公共文本处理
import re


DEFAULT_TARGET_CHARS = 1800
DEFAULT_MAX_CHARS = 3000

"""
统一换行
去掉行尾无意义空白
压缩异常连续空行
去首尾空白
"""
def normalize_text(text: str) -> str:
    text = (
        text
        .replace("\r\n", "\n") #Windows 换行，
        .replace("\r", "\n") # MAC换行
    )

    text = "\n".join(
        line.rstrip()
        for line in text.split("\n")
    )
        #正则压缩多个空行，多个空行只保留最多1个空行
    text = re.sub(
        r"\n[ \t]*\n(?:[ \t]*\n)+",
        "\n\n",
        text,
    )

    return text.strip()

def _split_sentences(
    text: str,
) -> list[str]:
    text = normalize_text(text)

    if not text:
        return []
    #核心正则分割句子
    parts = re.split(
        r"(?<=[。！？；])|(?<=[.!?])\s+",
        text,
    )
    #后处理，每个片段去掉收尾空白，过滤掉空字符串
    return [
        part.strip()
        for part in parts
        if part.strip()  #把当前片段首尾空格、换行、tab 全部删掉。
    ]

def _hard_split(
    text: str,
    max_chars: int,
) -> list[str]:
    return [
        text[index:index + max_chars]
        for index in range(
            0,
            len(text),
            max_chars,
        )
    ]

def split_long_text(  #将一段text拆分为chunk，如果一个自然结构太长，被迫拆开的时候，会尽量保留上一块最后一个完整的句子
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    text = normalize_text(text)

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = [
        normalize_text(part) 
        for part in re.split(
            r"\n\s*\n", #**按照正则匹配到的位置，把字符串切开，返回一个列表**。
            text,
        )
    ]

    paragraphs = [  #去掉空字符
        paragraph
        for paragraph in paragraphs
        if paragraph
    ]

    units: list[str] = []
    #rag 切分文本
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue

        for sentence in _split_sentences(
            paragraph
        ):
            if len(sentence) <= max_chars:
                units.append(sentence)
            else:
                units.extend(
                    _hard_split(
                        sentence,
                        max_chars,
                    )
                )

    chunks: list[str] = []  #大块
    current: list[str] = [] #缓冲区
    current_length = 0  #缓冲区里面全部字符的总长度

    for unit in units:
        separator_length = (
            2 if current else 0
        )  #增加分割符 2个

        if (
            current
            and current_length
            + separator_length
            + len(unit)
            > max_chars
        ):  # ✅加上这个unit就超上限了！把current打包，输出一个chunk
            chunks.append(
                "\n\n".join(current)
            )

            overlap = ""  #重叠的文本字符串
            ## current重置，新的current带上overlap片段
            last_sentences = _split_sentences(
                current[-1]             #缓冲区最后一个unit切割出来的结果
            )

            if last_sentences:
                overlap = last_sentences[-1]

            if (
                len(current) == 1
                and overlap == current[-1]
            ):
                overlap = ""

            current = (
                [overlap]
                if overlap
                else []
            )

            current_length = (
                len(overlap)
                if overlap
                else 0
            )

            if (
                current
                and current_length
                + 2
                + len(unit)
                > max_chars  #每个chunk运行的最大字符上限
            ):
                current = []
                current_length = 0

        if current:
            current_length += (
                2 + len(unit)
            )
        else:
            current_length = len(unit)

        current.append(unit)

    if current:
        chunks.append(
            "\n\n".join(current)
        )

    return chunks


def merge_short_blocks(  #把一堆很短的文本块，尽量合并成更大的块
    blocks: list[str],
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,  #面分片之后产出很多很小的片段，很多块长度远远小于目标，token 利用率低，就调用这个函数把短块合并。
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    normalized = [
        normalize_text(block)
        for block in blocks
    ]

    normalized = [  #去掉空行
        block
        for block in normalized
        if block
    ]

    if not normalized:
        return []

    merged: list[str] = []
    current = normalized[0] #缓存，正在攒的当前块，初始拿第一个块
    #从第二个开始遍历
    for block in normalized[1:]:
        candidate = ( ## 尝试合并：current + "\n\n" + block，得到候选字符串
            f"{current}\n\n{block}"
        )

        if (
            len(current) < target_chars
            and len(candidate) <= max_chars
        ):
            current = candidate
        else:  ## 不能合并：把current存入结果，开启新块
            merged.append(current)
            current = block
    # for循环结束，把最后还没存进去的current补进去
    merged.append(current)

    return merged