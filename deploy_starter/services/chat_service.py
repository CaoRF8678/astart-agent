import uuid
from schemas.chat import ChatRequest, ChatResponse



class ChatServiceError(Exception):
    """
    Chat service execution error
    """
    def __init__(
        self,
        request_id:str,
        code:str,
        message:str,        
    ):
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message


def build_agent_request(
    chat_request: ChatRequest,
    session_id:str,
)->dict:
    """
    Convert Astart /chat request into AgentScope Runtime request format.
    """

    return{
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": chat_request.message,
                    }
                ]
            }
        ],
        "session_id": session_id,
        "user_id": chat_request.user_id,
        "access_source": "astart_api"
    }

async def execute_chat(
    runner,
    chat_request:ChatRequest,
    request_id:str,    
)-> ChatResponse:
    #1如果用户有session_id，就继续使用
    #如果没有就生成新的uuid
    session_id = chat_request.session_id or str(uuid.uuid4())

    #2、转换成AgentScope Runtime请求格式
    agent_request = build_agent_request(chat_request, session_id)

    final_response = None

    async for event in runner.stream_query(agent_request):
        if(
            getattr(event,"object",None) == "response"
            and getattr(event,"status",None) == "completed"
        ):
            final_response = event
    if final_response is None:
        raise ChatServiceError(
            request_id=request_id,
            code="AGENT_NO_COMPLETED_RESPONSE",
            message="Agent did not return a completed response.",
        )
    answer = extract_answer(final_response)
    message_id = f"msg_{uuid.uuid4()}"
    return ChatResponse(
        request_id=request_id,
        message_id=message_id,
        session_id=session_id,
        status="completed",
        answer=answer,
        usage=None,
    )

def extract_answer(final_response)->str:
    payload = final_response.model_dump(mode = 'json')
    outputs = payload.get("output",[])
    answer_parts = []
    for item in outputs:
        if(item.get("type","") == "message" and item.get("role","") == "assistant"):
            contents = item.get("content") or []
            for content in contents:
                if content.get("type") == "text":
                    answer_parts.append(content.get("text",""))        
    return "".join(answer_parts).strip()