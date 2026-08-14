import asyncio
import os
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from agentscope.pipeline import stream_printing_messages
from agentscope_runtime.engine import AgentApp, LocalDeployManager
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.tracing import TraceType, trace, TracingUtil
from opentelemetry import trace as ot_trace

from core.config import config
from core.logging_config import LOCAL_IP, logger, success_response
from core.tracing import set_custome_trace, testObservability
from agents.friday_agent import create_friday_agent
from agents.intake_agent import IntakeAnalyzer
from services.lifecycle import register_lifecycle
from api.chat import register_chat_routes
from api.history import register_history_routes
from api.intake import register_intake_routes

from api.upload import register_upload_routes  #一个负责注册 /upload 路由
from storage.local import LocalFileStorage #一个负责创建本地 Storage
from services.intake_service import IntakeService
agent_app = AgentApp(
    app_name=config.get("APP_NAME"),
    app_description="A helpful assistant",
)

file_storage = LocalFileStorage(
     root_dir="data/uploads",
)
intake_analyzer = IntakeAnalyzer()
intake_service = IntakeService(
    analyzer=intake_analyzer,
)

register_chat_routes(agent_app)
register_lifecycle(agent_app)
register_history_routes(agent_app)
register_upload_routes(agent_app,storage=file_storage)

register_intake_routes(
    agent_app,
    intake_service=intake_service,
)
@agent_app.endpoint("/")
@trace(trace_type=TraceType.LLM, trace_name="llm_func", is_root_span=True)
def read_root():
    return {"hi, i'm running"}


@agent_app.endpoint("/health")
@trace(trace_type=TraceType.LLM, trace_name="llm_func", is_root_span=True)
def health_check():
    return "OK"


@agent_app.endpoint("/createSession")
@trace(trace_type=TraceType.OTHER, trace_name="create_session", is_root_span=True)
def create_session(request: Request, body: dict):
    unique_code = str(uuid.uuid4())
    return {"uniqueCode": unique_code, **success_response()}


@agent_app.endpoint("/clearSession")
@trace(trace_type=TraceType.OTHER, trace_name="clear_session", is_root_span=True)
def clear_session(request: Request, body: dict):
    set_custome_trace(body)
    return success_response(message="session_id cleared")


@agent_app.endpoint("/abortSession")
@trace(trace_type=TraceType.OTHER, trace_name="abort_session", is_root_span=True)
def abort_session(request: Request, body: dict):
    set_custome_trace(body)
    return success_response(message="session_id aborted")


# /process/sync — synchronous wrapper around runner.stream_query.
SYNC_DEFAULT_TIMEOUT = int(os.getenv("SYNC_TIMEOUT_SECONDS", "600"))
SYNC_MAX_TIMEOUT = SYNC_DEFAULT_TIMEOUT * 5


def _parse_sync_timeout(headers) -> int:
    raw = headers.get("x-sync-timeout-seconds") or headers.get(
        "X-Sync-Timeout-Seconds"
    )
    if not raw:
        return SYNC_DEFAULT_TIMEOUT
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return SYNC_DEFAULT_TIMEOUT
    if v <= 0:
        return SYNC_DEFAULT_TIMEOUT
    return min(v, SYNC_MAX_TIMEOUT)


@agent_app.endpoint("/process/sync", methods=["POST"])
@trace(trace_type=TraceType.LLM, trace_name="process_sync", is_root_span=True)
async def process_sync(request: Request, body: dict):
    set_custome_trace(body)
    runner = getattr(request.app.state, "runner", None)
    if runner is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Service not ready", "message": "Runner not initialized"},
        )

    timeout = _parse_sync_timeout(request.headers)
    started_at = time.monotonic()
    final_response = None
    session_id = None

    try:
        async with asyncio.timeout(timeout):
            async for ev in runner.stream_query(body):
                if getattr(ev, "object", None) == "response":
                    final_response = ev
                    session_id = getattr(ev, "session_id", None) or session_id
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": "Timeout",
                "message": f"exceeded {timeout}s",
                "session_id": session_id,
            },
            headers={"X-Session-Id": session_id or ""},
        )
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"error": "Service not ready", "message": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "message": str(e)},
        )

    if final_response is None:
        return JSONResponse(
            status_code=500,
            content={"error": "No response frame produced"},
        )

    latency_ms = int((time.monotonic() - started_at) * 1000)
    payload = final_response.model_dump(mode="json")
    payload["host"] = LOCAL_IP
    return JSONResponse(
        content=payload,
        headers={
            "X-Session-Id": str(payload.get("session_id") or ""),
            "X-Sync-Latency-Ms": str(latency_ms),
        },
    )


@agent_app.query(framework="agentscope")
@trace(trace_type=TraceType.LLM, trace_name="llm_func", is_root_span=True)
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    response=None,
    **kwargs,
):
    session_id = request.session_id
    logger.info("[query_func] session_id=%s, host=%s", session_id, LOCAL_IP)
    access_source = request.model_extra.get("access_source") or "api"
    user_id = request.user_id

    current_span = ot_trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("bailian.app.session_id", session_id or "")
        current_span.set_attribute("bailian.app.metric.source", access_source or "")
        current_span.set_attribute("bailian.app.agent.ip", LOCAL_IP or "")

    TracingUtil.set_common_attributes({"bailian.app.session_id": session_id or ""})
    TracingUtil.set_common_attributes({"bailian.app.metric.source": access_source or ""})
    TracingUtil.set_common_attributes({"bailian.app.agent.ip": LOCAL_IP or ""})

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    agent = create_friday_agent(
        session_service=self.session_service,
        session_id=session_id,
        user_id=user_id,
    )

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


async def main():
    """Deploy AgentScope Runtime using LocalDeployManager."""
    deployer = LocalDeployManager(
        host=config.get("START_HOST", "127.0.0.1"),
        port=config.get("PORT", 8080),
    )
    testObservability()

    await agent_app.deploy(deployer)

    print("Service started, press Ctrl+C to stop...")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping service...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nService stopped")
