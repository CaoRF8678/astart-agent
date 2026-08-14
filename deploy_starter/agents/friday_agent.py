from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, execute_python_code
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

from core.model_factory import create_chat_model_and_formatter
from tools.oss_tool import download_and_read_oss_file

def create_friday_agent(session_service, session_id, user_id) -> ReActAgent:
    """Create the Friday ReActAgent using the original model/tool configuration."""
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(download_and_read_oss_file)
    model_obj, formatter_obj = create_chat_model_and_formatter(
        stream=True,
)
    
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
