from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)


def register_lifecycle(agent_app):
    """Register the original AgentApp init/shutdown hooks."""

    @agent_app.init
    async def init_func(self):
        self.state_service = InMemoryStateService()
        self.session_service = InMemorySessionHistoryService()
        await self.state_service.start()
        await self.session_service.start()

    @agent_app.shutdown
    async def shutdown_func(self):
        await self.state_service.stop()
        await self.session_service.stop()

    return init_func, shutdown_func
