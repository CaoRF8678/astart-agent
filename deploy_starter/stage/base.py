import asyncio
import json

import httpx
from pydantic import ValidationError

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from core.model_factory import (
    create_chat_model_and_formatter,
)

def _is_transient_error(exc: Exception) -> bool:
    # Pydantic 校验错误：确定性错误，不重试
    if isinstance(exc, ValidationError):
        return False

    # 某些模型 SDK 异常直接提供 status_code
    status_code = getattr(
        exc,
        "status_code",
        None,
    )

    # httpx.HTTPStatusError 的状态码在 response 上
    if (
        status_code is None
        and isinstance(exc, httpx.HTTPStatusError)
    ):
        status_code = exc.response.status_code

    # 429：限流
    if status_code == 429:
        return True

    # 5xx：服务器临时错误
    if (
        isinstance(status_code, int)
        and 500 <= status_code < 600
    ):
        return True

    # 网络/传输类临时错误
    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            httpx.TransportError,
        ),
    ):
        return True

    return False

class StructuredStageRunner:

    def __init__(self):
        self.model, self.formatter = (
            create_chat_model_and_formatter(
                stream=False,
                generate_kwargs={
                    "extra_body": {
                        "thinking": {
                            "type": "disabled",
                        }
                    }
                },
            )
        )


    async def run(
        self,
        *,
        name: str,
        system_prompt: str,
        payload: dict,
        structured_model,
    ):
        payload_text = json.dumps(
            payload,
            ensure_ascii= False,)
        max_attempts = 3
        for attempt in range(max_attempts):
            #每次技术重试都创建新的agent + Memory
            #避免上一次失败留下部分状态
            agent = ReActAgent(
                name=name,
                model=self.model,
                sys_prompt=system_prompt,
                formatter=self.formatter,
                memory=InMemoryMemory(),
            )
            try:
                 
                result = await agent(
                    Msg(
                    name = "user",
                    role = "user",
                    content= payload_text
                ),
                    structured_model = structured_model
                )
                structured_result = structured_model.model_validate(
                result.metadata
                    )
                return structured_result
            except Exception as exc:
                 if not _is_transient_error(exc):
                      raise
                 if attempt == max_attempts -1:
                      raise
                 delay_seconds = 2 **attempt
                 await asyncio.sleep(
                      delay_seconds
                 )
