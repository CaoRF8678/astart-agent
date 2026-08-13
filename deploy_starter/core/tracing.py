import os

import agentscope
from agentscope_runtime.engine.tracing import TraceType, trace, TracingUtil
from opentelemetry import trace as ot_trace

from core.logging_config import LOCAL_IP


# Enable AgentScope built-in tracing (tool/agent/formatter etc.).
# AgentScope Runtime creates a private TracerProvider but does not make it global,
# so this block makes AgentScope and Runtime share one export pipeline.
if os.getenv("TRACE_ENABLE_REPORT", "").lower() in ("true", "1", "yes"):
    agentscope._config.trace_enabled = True

    from opentelemetry.sdk.trace import TracerProvider as _SdkTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as OTLPSpanGrpcExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPSpanHttpExporter,
    )

    if not isinstance(ot_trace.get_tracer_provider(), _SdkTracerProvider):
        _resource = Resource(
            attributes={
                SERVICE_NAME: os.getenv("SERVICE_NAME", "agentscope_runtime"),
                SERVICE_VERSION: os.getenv("SERVICE_VERSION", "1.0.0"),
                "source": "agentscope_runtime-source",
            }
        )
        _provider = _SdkTracerProvider(resource=_resource)

        _trace_endpoint = os.getenv("TRACE_ENDPOINT", "")
        if _trace_endpoint:
            _exporter = OTLPSpanGrpcExporter(
                endpoint=_trace_endpoint,
                insecure=True,
                headers=f"Authentication={os.getenv('TRACE_AUTHENTICATION', '')}",
            )
            _provider.add_span_processor(BatchSpanProcessor(_exporter))

        if os.getenv("TRACE_ENABLE_DEBUG", "").lower() in ("true", "1", "yes"):
            _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        ot_trace.set_tracer_provider(_provider)

    import agentscope_runtime.engine.tracing.wrapper as _rt_wrapper

    _rt_wrapper._otel_tracer = ot_trace.get_tracer("agentscope_runtime")


def set_custome_trace(body: dict):
    session_id = body.get("session_id")
    access_source = body.get("access_source", "api")
    user_id = body.get("user_id")

    # Directly set attributes on the current span.
    current_span = ot_trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("bailian.app.session_id", session_id or "")
        current_span.set_attribute("bailian.app.metric.source", access_source or "")
        current_span.set_attribute("bailian.app.agent.ip", LOCAL_IP or "")

    # Also apply to common attributes so child spans inherit them.
    TracingUtil.set_common_attributes({"bailian.app.session_id": session_id or ""})
    TracingUtil.set_common_attributes({"bailian.app.metric.source": access_source or ""})
    TracingUtil.set_common_attributes({"bailian.app.agent.ip": LOCAL_IP or ""})


@trace(trace_type=TraceType.OTHER, trace_name="testObservability", is_root_span=True)
def testObservability():
    print("testObservability")
