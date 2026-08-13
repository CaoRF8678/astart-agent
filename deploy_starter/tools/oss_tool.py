import os
from urllib.parse import urlparse

import aiohttp
from agentscope.tool import ToolResponse
from agentscope.tool._response import TextBlock
from agentscope_runtime.engine.tracing import TraceType, trace


@trace(
    trace_type=TraceType.TOOL,
    trace_name="download_and_read_oss_file",
    is_root_span=False,
)
async def download_and_read_oss_file(
    url: str,
    encoding: str = "utf-8",
    max_size_mb: float = 10,
    **kwargs,
) -> ToolResponse:
    """Download a text file from an OSS URL and return its content.

    Args:
        url (`str`):
            The OSS URL of the text file to download and read.
        encoding (`str`, defaults to `"utf-8"`):
            The encoding used to decode the file content.
        max_size_mb (`float`, defaults to `10`):
            Maximum allowed file size in MB. Files exceeding this limit will be rejected.

    Returns:
        `ToolResponse`:
            The response containing the file name and its text content.
    """
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path) or "unknown_file"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    return ToolResponse(
                        content=[
                            TextBlock(
                                type="text",
                                text=f"Failed to download file: HTTP {resp.status}",
                            )
                        ]
                    )

                content_length = resp.content_length
                if content_length and content_length > max_size_bytes:
                    return ToolResponse(
                        content=[
                            TextBlock(
                                type="text",
                                text=(
                                    f"File too large: {content_length} bytes "
                                    f"(max {max_size_mb}MB)"
                                ),
                            )
                        ]
                    )

                data = await resp.read()
                if len(data) > max_size_bytes:
                    return ToolResponse(
                        content=[
                            TextBlock(
                                type="text",
                                text=(
                                    f"File too large: {len(data)} bytes "
                                    f"(max {max_size_mb}MB)"
                                ),
                            )
                        ]
                    )

        text_content = data.decode(encoding)
        result = f"=== File: {filename} ===\n{text_content}"
        return ToolResponse(content=[TextBlock(type="text", text=result)])

    except aiohttp.ClientError as e:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Network error downloading file: {e}")]
        )
    except UnicodeDecodeError as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Failed to decode file with encoding '{encoding}': {e}",
                )
            ]
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error reading file: {e}")]
        )
