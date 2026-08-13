import os

import httpx
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit, execute_python_code
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

from core.config import config
from core.logging_config import logger
from tools.oss_tool import download_and_read_oss_file


def create_friday_agent(session_service, session_id, user_id) -> ReActAgent:
    """Create the Friday ReActAgent using the original model/tool configuration."""
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(download_and_read_oss_file)

    # Model provider switch:
    # - ai_studio: VPC-hosted OpenAI-compatible endpoint
    # - third_party: public OpenAI-compatible endpoint (default)
    model_provider = (
        os.getenv("MODEL_PROVIDER")
        or config.get("MODEL_PROVIDER")
        or "third_party"
    ).lower()

    if model_provider == "ai_studio":
        vpc_api_url = os.getenv("DASHSCOPE_API_URL") or config.get(
            "VPC_OPENAI_API_URL"
        )
        vpc_api_key = os.getenv("DASHSCOPE_API_KEY") or config.get(
            "VPC_OPENAI_API_KEY"
        )
        vpc_model = os.getenv("DASHSCOPE_MODEL_CODE") or config.get(
            "VPC_OPENAI_MODEL", ""
        )

        # OpenAI SDK base_url must be the root path.
        for _suffix in (
            "/chat/completions",
            "/completions",
            "/responses",
            "/embeddings",
        ):
            if vpc_api_url and vpc_api_url.endswith(_suffix):
                vpc_api_url = vpc_api_url[: -len(_suffix)]
                break
        if vpc_api_url:
            vpc_api_url = vpc_api_url.rstrip("/")

        vpc_http_proxy = os.getenv("VPC_HTTP_PROXY") or config.get("VPC_HTTP_PROXY")

        bailian_app_env = (
            os.getenv("BAILIAN_APP_ENV") or config.get("BAILIAN_APP_ENV") or ""
        ).lower()
        if bailian_app_env == "prod":
            vpc_http_proxy = None

        openai_client_kwargs = {"base_url": vpc_api_url}
        if vpc_http_proxy:
            try:
                _http_client = httpx.AsyncClient(
                    proxy=vpc_http_proxy,
                    timeout=httpx.Timeout(60.0, connect=10.0),
                )
            except TypeError:
                _http_client = httpx.AsyncClient(
                    proxies=vpc_http_proxy,
                    timeout=httpx.Timeout(60.0, connect=10.0),
                )
            openai_client_kwargs["http_client"] = _http_client

        logger.info(
            "[OpenAIChatModel/third_party] base_url=%s, model=%r, proxy=%s",
            vpc_api_url,
            vpc_model,
            vpc_http_proxy or "<none>",
        )

        model_obj = OpenAIChatModel(
            model_name=vpc_model,
            api_key=vpc_api_key,
            stream=True,
            client_kwargs=openai_client_kwargs,
        )
        formatter_obj = OpenAIChatFormatter()

    else:
        model_name = os.getenv("DASHSCOPE_MODEL_CODE") or config.get(
            "DASHSCOPE_MODEL_CODE", "qwen3.6-plus"
        )
        api_key = os.getenv("DASHSCOPE_API_KEY") or config.get("DASHSCOPE_API_KEY")
        api_url = (
            os.getenv("DASHSCOPE_API_URL")
            or config.get("DASHSCOPE_API_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        for _suffix in (
            "/chat/completions",
            "/completions",
            "/responses",
            "/embeddings",
        ):
            if api_url.endswith(_suffix):
                api_url = api_url[: -len(_suffix)]
                break
        api_url = api_url.rstrip("/")

        logger.info(
            "[OpenAIChatModel/third_party] base_url=%s, model=%s, key=%s",
            api_url,
            model_name,
            (api_key[:6] + "***") if api_key else "<empty>",
        )

        model_obj = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
            client_kwargs={"base_url": api_url},
        )
        formatter_obj = OpenAIChatFormatter()

    return ReActAgent(
        name="Friday",
        model=model_obj,
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=AgentScopeSessionHistoryMemory(
            service=session_service,
            session_id=session_id,
            user_id=user_id,
        ),
        formatter=formatter_obj,
    )
