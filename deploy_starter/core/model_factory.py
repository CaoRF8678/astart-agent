import os

import httpx
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel

from core.config import config
from core.logging_config import logger


# OpenAI 兼容接口可能带有这些请求路径，
# 创建 Model 时需要的是 base_url，因此要把这些后缀去掉。
_OPENAI_PATH_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/responses",
    "/embeddings",
)


def _normalize_base_url(api_url: str | None) -> str | None:
    """清理 API 地址，只保留 base_url。"""

    if not api_url:
        return None

    api_url = api_url.rstrip("/")

    for suffix in _OPENAI_PATH_SUFFIXES:
        if api_url.endswith(suffix):
            api_url = api_url[: -len(suffix)]
            break

    return api_url.rstrip("/")


def _create_proxy_http_client(
    proxy_url: str,
) -> httpx.AsyncClient:
    """创建支持代理的 HTTP 客户端。"""

    timeout = httpx.Timeout(
        60.0,
        connect=10.0,
    )

    # 兼容不同版本的 httpx
    try:
        return httpx.AsyncClient(
            proxy=proxy_url,
            timeout=timeout,
        )
    except TypeError:
        return httpx.AsyncClient(
            proxies=proxy_url,
            timeout=timeout,
        )


def create_chat_model_and_formatter(
    *,
    stream: bool,
    generate_kwargs: dict | None = None,
) -> tuple[OpenAIChatModel, OpenAIChatFormatter]:
    """
    创建 Astart 共用的大模型和 Formatter。

    stream=True：
        用于普通流式聊天，例如后续 Tutor Agent。

    stream=False：
        用于 Intake 等需要完整结构化结果的场景。
    """

    # 1. 确定当前使用哪一种模型 Provider
    model_provider = (
        os.getenv("MODEL_PROVIDER")
        or config.get("MODEL_PROVIDER")
        or "third_party"
    ).lower()

    # 2. 百炼 AI Studio 环境
    if model_provider == "ai_studio":
        api_url = (
            os.getenv("DASHSCOPE_API_URL")
            or config.get("VPC_OPENAI_API_URL")
        )

        api_key = (
            os.getenv("DASHSCOPE_API_KEY")
            or config.get("VPC_OPENAI_API_KEY")
        )

        model_name = (
            os.getenv("DASHSCOPE_MODEL_CODE")
            or config.get("VPC_OPENAI_MODEL", "")
        )

        api_url = _normalize_base_url(api_url)

        proxy_url = (
            os.getenv("VPC_HTTP_PROXY")
            or config.get("VPC_HTTP_PROXY")
        )

        # 百炼生产环境不使用本地代理
        bailian_app_env = (
            os.getenv("BAILIAN_APP_ENV")
            or config.get("BAILIAN_APP_ENV")
            or ""
        ).lower()

        if bailian_app_env == "prod":
            proxy_url = None

        client_kwargs = {
            "base_url": api_url,
        }

        if proxy_url:
            client_kwargs["http_client"] = (
                _create_proxy_http_client(proxy_url)
            )

        logger.info(
            "[OpenAIChatModel/ai_studio] "
            "base_url=%s, model=%r, proxy=%s",
            api_url,
            model_name,
            proxy_url or "<none>",
        )

    # 3. 普通第三方 OpenAI 兼容接口
    else:
        model_name = (
            os.getenv("DASHSCOPE_MODEL_CODE")
            or config.get(
                "DASHSCOPE_MODEL_CODE",
                "qwen3.6-plus",
            )
        )

        api_key = (
            os.getenv("DASHSCOPE_API_KEY")
            or config.get("DASHSCOPE_API_KEY")
        )

        api_url = (
            os.getenv("DASHSCOPE_API_URL")
            or config.get("DASHSCOPE_API_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        api_url = _normalize_base_url(api_url)

        client_kwargs = {
            "base_url": api_url,
        }

        logger.info(
            "[OpenAIChatModel/third_party] "
            "base_url=%s, model=%s, key=%s",
            api_url,
            model_name,
            (
                api_key[:6] + "***"
                if api_key
                else "<empty>"
            ),
        )

    # 4. 创建真正的 AgentScope Model
    model = OpenAIChatModel(
        model_name=model_name,
        api_key=api_key,
        stream=stream,
        client_kwargs=client_kwargs,
        generate_kwargs=generate_kwargs or {},
    )

    # 5. 创建消息格式转换器
    formatter = OpenAIChatFormatter()

    return model, formatter